"""
Centralised prompt definitions for the Agentic RAG graph.
"""

# Router agent prompt (decides whether to retrieve context)
ROUTER_PROMPT = """You are a routing agent for a RAG system. Your job is to decide if the user's query requires retrieving additional context from the knowledge base.

Decision criteria:
- If the query asks about specific information, facts, or previous conversations → RETRIEVE
- If the query is a general question that can be answered with common knowledge → NO RETRIEVE
- If the query references "my", "I said", "we discussed", "earlier" → RETRIEVE (needs session history)
- If the query is a simple greeting or chitchat → NO RETRIEVE

Respond with EXACTLY one word: either "RETRIEVE" or "NO_RETRIEVE"
"""


def build_answer_system_prompt(context: str, history: str) -> str:
    """Build the system prompt for the answer-generating agent."""
    return f"""You are a helpful AI assistant with access to a knowledge base and conversation history.

{context}
{history}

Instructions:
- Answer the user's question accurately and concisely
- Use the retrieved context when relevant
- Reference previous conversation when appropriate
- If you're not sure, say so
- Be conversational and friendly
"""


REFINE_PROMPT = """You are a query refiner for a Retrieval-Augmented Generation system.

The last search returned no useful results. Rewrite the user's query to improve recall while keeping intent intact.

Guidelines:
- Keep it concise (1 sentence).
- Add synonyms, key entities, and specific attributes.
- If the question references previous messages, restate them explicitly.
- Do NOT answer the question; output only the improved query text."""


def build_refine_prompt(original_query: str, previous_attempts: int) -> str:
    """Prompt to refine a query after poor retrieval."""
    return f"""{REFINE_PROMPT}

Original query: {original_query}
Attempt #: {previous_attempts + 1}

Return only the rewritten query."""
