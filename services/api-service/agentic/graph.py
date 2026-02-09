"""
LangGraph workflow for Agentic RAG
"""
import os
import asyncio
from typing import Dict, Any, List
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
import logging
import httpx

from .state import ConversationState
from .prompts import ROUTER_PROMPT, build_answer_system_prompt, build_refine_prompt
from .tools import RAG_TOOLS, semantic_search_tool, session_history_tool, user_memories_tool

logger = logging.getLogger(__name__)


# Initialize the reasoning LLM
def get_reasoning_llm():
    """Get the LLM used for agent reasoning"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")
    
    return ChatOpenAI(
        model="gpt-4o",  # Use GPT-4o for reasoning
        temperature=0.1,  # Low temperature for consistent reasoning
        api_key=api_key
    )


def should_continue(state: ConversationState) -> str:
    """Determine if the agent should continue iterating or finish"""
    
    # Check iteration limit
    if state["iteration_count"] >= state["max_iterations"]:
        logger.info("Max iterations reached, generating final answer")
        return "generate_answer"
    
    # If we have a final answer, we're done
    if state.get("final_answer"):
        logger.info("Final answer generated, ending workflow")
        return END
    
    # If we should retrieve context, do it
    if state.get("should_retrieve", False):
        logger.info("Agent decided to retrieve context")
        return "retrieve_context"
    
    # Otherwise, generate the answer
    logger.info("Agent ready to generate answer")
    return "generate_answer"


async def route_query_node(state: ConversationState) -> ConversationState:
    """Initial routing: decide if we need to retrieve context"""
    
    llm = get_reasoning_llm()
    
    # Build the prompt for routing decision
    system_prompt = ROUTER_PROMPT
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Query: {state['current_query']}")
    ]
    
    response = await llm.ainvoke(messages)
    decision = response.content.strip().upper()
    
    # Update state from LLM decision
    state["should_retrieve"] = "RETRIEVE" in decision

    # Safety: if we already have conversation history, force retrieval so follow-ups use context
    if not state["should_retrieve"] and len(state.get("messages", [])) > 1:
        state["should_retrieve"] = True
        decision = f"{decision} → FORCE_RETRIEVE (has history)"
    
    state["agent_thoughts"].append(f"Routing decision: {decision}")
    state["iteration_count"] += 1
    
    logger.info(f"Routing decision for query '{state['current_query']}': {decision}")
    
    return state


async def refine_query_node(state: ConversationState) -> ConversationState:
    """Refine the user's query when retrieval returned little/no context."""
    llm = get_reasoning_llm()
    prompt = build_refine_prompt(state["current_query"], state["iteration_count"])
    
    response = await llm.ainvoke([HumanMessage(content=prompt)])
    refined = response.content.strip()
    
    original = state["current_query"]
    state["current_query"] = refined
    state["retrieved_context"] = []
    state["agent_thoughts"].append(f"Refined query from: '{original}' -> '{refined}'")
    state["iteration_count"] += 1
    state["should_retrieve"] = True
    
    logger.info(f"Refined query (iter {state['iteration_count']}): '{original}' -> '{refined}'")
    return state


async def retrieve_context_node(state: ConversationState) -> ConversationState:
    """Retrieve relevant context using RAG tools"""
    
    query = state["current_query"]
    session_id = state["session_id"]
    user_id = state["user_id"]
    
    # Retrieve from multiple sources in parallel
    import asyncio
    
    # Semantic search in vector DB
    semantic_results_raw = await semantic_search_tool.ainvoke({"query": query, "limit": 5})
    
    # Filter out low-value/apology hits that pollute retrieval
    def _is_informative(text: str) -> bool:
        t = (text or "").lower()
        noise_markers = [
            "don't have a record",
            "do not have a record",
            "no record",
            "don't have enough information",
            "cannot find",
            "couldn't find",
            "i'm sorry, but i don't have"
        ]
        return not any(marker in t for marker in noise_markers)
    
    semantic_results = [
        r for r in semantic_results_raw
        if _is_informative(r.get("content", "") or r.get("text", ""))
    ]
    
    # Get recent session history (if this is a multi-turn conversation)
    history_results = await session_history_tool.ainvoke({"session_id": session_id, "limit": 10})
    
    # Get user's past memories/Q&A from PostgreSQL (across all sessions)
    user_memories = await user_memories_tool.ainvoke({"user_id": user_id, "limit": 10})
    
    # Combine all context
    all_context = []
    
    # Add semantic search results
    for result in semantic_results:
        all_context.append({
            "source": "vector_search",
            "content": result.get("content", result.get("text", "")),
            "score": result.get("score", 0.0)
        })
    
    # Add user memories from PostgreSQL (past Q&A across all sessions)
    for memory in user_memories:
        # Skip if content is too similar to current query (avoid self-reference)
        if memory.get("query", "").lower().strip() != query.lower().strip():
            all_context.append({
                "source": "user_memory",
                "query": memory.get("query", ""),
                "summary": memory.get("summary", ""),
                "created_at": memory.get("created_at", "")
            })
    
    # Add session history (excluding the current query)
    for msg in history_results[:-1]:  # Exclude last message (the current query)
        all_context.append({
            "source": "session_history",
            "role": msg["role"],
            "content": msg["content"]
        })
    
    state["retrieved_context"] = all_context
    state["agent_thoughts"].append(f"Retrieved {len(all_context)} pieces of context (vector: {len(semantic_results)}, memories: {len(user_memories)}, history: {max(0, len(history_results)-1)})")
    
    logger.info(f"Retrieved {len(all_context)} context items for query: {query}")
    
    return state


# --- New: call selected LLMs before synthesis --------------------------------
def _build_conversation_prompt(state: ConversationState, include_history: int = 6) -> str:
    """Inject retrieved context and session history so model answers remain contextual."""
    parts = []
    
    # Add retrieved context (vector search + user memories)
    if state.get("retrieved_context"):
        context_lines = ["## Retrieved Context from your past conversations:\n"]
        for idx, ctx in enumerate(state["retrieved_context"][:8], 1):  # Limit to 8 items
            if ctx.get("source") == "vector_search":
                content = ctx.get("content", "")[:300]
                context_lines.append(f"{idx}. [Past Knowledge] {content}")
            elif ctx.get("source") == "user_memory":
                query = ctx.get("query", "")[:100]
                summary = ctx.get("summary", "")[:200]
                context_lines.append(f"{idx}. [Past Q&A] Q: {query}... A: {summary}...")
            elif ctx.get("source") == "session_history":
                role = ctx.get("role", "user")
                content = ctx.get("content", "")[:200]
                context_lines.append(f"{idx}. [Session] {role}: {content}")
        parts.append("\n".join(context_lines))
    
    # Add recent session history
    history_lines = []
    for msg in state.get("messages", [])[-include_history:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")[:400]
        history_lines.append(f"{role}: {content}")
    if history_lines:
        parts.append("## Recent conversation:\n" + "\n".join(history_lines))
    
    # Add the current question
    parts.append(f"## Current question:\n{state['current_query']}")
    
    # Add instruction
    parts.append("\nPlease answer based on the retrieved context above. If the context contains relevant past discussions, use that information to answer.")
    
    return "\n\n".join(parts)


async def _call_openai(query: str):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return "OpenAI not configured"
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    enhanced_query = query
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": enhanced_query}],
        "temperature": 0,
    }

    async def _do_call(payload_model: str):
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={**payload, "model": payload_model},
            )

    try:
        resp = await _do_call(model)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        if resp.status_code == 429:
            return {
                "error": "rate_limited",
                "status": 429,
                "retry_after": resp.headers.get("retry-after") or resp.headers.get("retry-after-ms"),
                "provider": "OpenAI",
            }
        # Fallback once if model is invalid/unsupported
        if resp.status_code in (400, 404) and model != "gpt-4o-mini":
            resp = await _do_call("gpt-4o-mini")
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"]
            if resp.status_code == 429:
                return {
                    "error": "rate_limited",
                    "status": 429,
                    "retry_after": resp.headers.get("retry-after") or resp.headers.get("retry-after-ms"),
                    "provider": "OpenAI",
                }
        return {
            "error": "request_failed",
            "status": resp.status_code,
            "message": resp.text[:200],
            "provider": "OpenAI",
        }
    except Exception as e:  # pragma: no cover
        return f"OpenAI error: {e}"


async def _call_gemini(query: str):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "Gemini not configured"
    model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={"contents": [{"parts": [{"text": query}]}]},
            )
        if resp.status_code == 200:
            data = resp.json()
            return data["candidates"][0]["content"]["parts"][0]["text"]
        if resp.status_code == 429:
            return {
                "error": "rate_limited",
                "status": 429,
                "retry_after": resp.headers.get("retry-after") or resp.headers.get("retry-after-ms"),
                "provider": "Gemini",
            }
        return {
            "error": "request_failed",
            "status": resp.status_code,
            "message": resp.text[:200],
            "provider": "Gemini",
        }
    except Exception as e:  # pragma: no cover
        return f"Gemini error: {e}"


async def _call_grok(query: str):
    api_key = os.getenv("GROK_API_KEY")
    if not api_key:
        return "Grok not configured"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": "grok-2-vision-1212",
                    "messages": [{"role": "user", "content": query}],
                    "max_tokens": 1200,
                },
            )
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"]
        if resp.status_code == 429:
            return {
                "error": "rate_limited",
                "status": 429,
                "retry_after": resp.headers.get("retry-after") or resp.headers.get("retry-after-ms"),
                "provider": "Grok",
            }
        return {
            "error": "request_failed",
            "status": resp.status_code,
            "message": resp.text[:200],
            "provider": "Grok",
        }
    except Exception as e:  # pragma: no cover
        return f"Grok error: {e}"


async def call_llms_node(state: ConversationState) -> ConversationState:
    """Fan out to selected LLMs and store their individual answers."""
    prompt = _build_conversation_prompt(state)
    model_map = {
        "OpenAI": _call_openai,
        "Gemini": _call_gemini,
        "Grok": _call_grok,
    }
    tasks = []
    names = []
    for name in state.get("selected_models", []):
        fn = model_map.get(name)
        if fn:
            tasks.append(fn(prompt))
            names.append(name)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    answers: Dict[str, str] = {}
    errors: Dict[str, str] = {}
    for name, result in zip(names, results):
        if isinstance(result, Exception):
            errors[name] = str(result)
        elif isinstance(result, dict) and result.get("error"):
            errors[name] = f"{result['error']} (status {result.get('status')})"
        elif isinstance(result, str) and result.lower().startswith(("error", "openai error", "gemini error", "grok error")):
            errors[name] = result
        else:
            answers[name] = result
    state["llm_answers"] = answers
    state["llm_errors"] = errors
    state["agent_thoughts"].append(f"Collected {len(answers)} model answers")
    return state


async def generate_answer_node(state: ConversationState) -> ConversationState:
    """Generate the final answer using retrieved context"""
    
    llm = get_reasoning_llm()
    
    # Build context string
    context_str = ""
    if state.get("retrieved_context"):
        context_str = "\n\n## Retrieved Context:\n"
        for idx, ctx in enumerate(state["retrieved_context"], 1):
            if ctx["source"] == "vector_search":
                context_str += f"\n{idx}. [Vector Search] {ctx['content'][:200]}..."
            elif ctx["source"] == "user_memory":
                # Include past Q&A from user's history
                context_str += f"\n{idx}. [Past Q&A] Q: {ctx.get('query', '')[:100]}... A: {ctx.get('summary', '')[:200]}..."
            elif ctx["source"] == "session_history":
                context_str += f"\n{idx}. [Previous {ctx['role']}] {ctx['content'][:200]}"
    if state.get("llm_answers"):
        context_str += "\n\n## Model Opinions (do not copy verbatim; synthesize):\n"
        for name, text in state["llm_answers"].items():
            context_str += f"- {name}: {text[:400]}\n"
    
    # Build conversation history
    history_str = ""
    if state.get("messages"):
        history_str = "\n\n## Conversation History:\n"
        for msg in state["messages"][-10:]:  # Last 10 messages
            history_str += f"\n{msg['role']}: {msg['content']}"
    
    # Create the prompt
    system_prompt = build_answer_system_prompt(context_str, history_str)
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=state["current_query"])
    ]
    
    response = await llm.ainvoke(messages)
    answer = response.content
    
    state["final_answer"] = answer
    state["agent_thoughts"].append("Generated final answer")
    
    logger.info(f"Generated answer for query: {state['current_query'][:50]}...")
    
    return state


def create_agentic_rag_graph():
    """Create and compile the LangGraph workflow for Agentic RAG"""
    
    # Create the state graph
    workflow = StateGraph(ConversationState)
    
    # Add nodes
    workflow.add_node("route_query", route_query_node)
    workflow.add_node("retrieve_context", retrieve_context_node)
    workflow.add_node("refine_query", refine_query_node)
    workflow.add_node("call_llms", call_llms_node)
    workflow.add_node("generate_answer", generate_answer_node)
    
    # Set entry point
    workflow.set_entry_point("route_query")
    
    # Add conditional edges from route_query
    workflow.add_conditional_edges(
        "route_query",
        should_continue,
        {
            "retrieve_context": "retrieve_context",
            "generate_answer": "call_llms",  # even if no retrieval, still gather model answers
            END: END
        }
    )
    
    # After retrieving context, decide whether to refine or answer
    def _after_retrieve(state: ConversationState):
        if not state.get("retrieved_context") and state["iteration_count"] < state["max_iterations"]:
            return "refine_query"
        return "call_llms"
    
    workflow.add_conditional_edges(
        "retrieve_context",
        _after_retrieve,
        {
            "refine_query": "refine_query",
            "call_llms": "call_llms"  # Fixed: key must match return value from _after_retrieve
        }
    )
    
    # After refining, try retrieval again
    workflow.add_edge("refine_query", "retrieve_context")
    
    # After collecting model answers, synthesize final answer
    workflow.add_edge("call_llms", "generate_answer")
    
    # After generating answer, end
    workflow.add_edge("generate_answer", END)
    
    # Compile and return
    compiled_graph = workflow.compile()
    
    logger.info("Agentic RAG graph compiled successfully")
    
    return compiled_graph


# Export the graph creation function
__all__ = ["create_agentic_rag_graph", "ConversationState"]
