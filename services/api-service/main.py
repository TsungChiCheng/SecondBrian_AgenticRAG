# API Service - Main business logic service (stub implementation for testing)
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional
import httpx
import os
import asyncio
import logging
from dotenv import load_dotenv
from config.config import settings

import uvicorn
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from uuid import UUID
from utils.chunk import chunk_text, adaptive_chunk_text

# Load environment variables
load_dotenv()

# Configure logging - must be done before uvicorn starts
import sys

# Custom filter to exclude health check logs
class ExcludeHealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Exclude GET /health requests from access logs
        return 'GET /health' not in record.getMessage()

# Configure root logger with DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ],
    force=True  # Override any existing configuration
)
logger = logging.getLogger(__name__)

# Configure uvicorn's loggers
logging.getLogger("uvicorn").setLevel(logging.INFO)
uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.setLevel(logging.INFO)
uvicorn_access_logger.addFilter(ExcludeHealthCheckFilter())  # Filter out health checks

# Set httpx to WARNING to reduce noise from HTTP requests
logging.getLogger("httpx").setLevel(logging.WARNING)

# Direct HTTP-based LLM calls to avoid version conflicts
import json

# --- Compatibility patch --------------------------------------------------
# OpenAI 2.x calls pydantic's `model_dump` with `by_alias=None`, which
# raises a TypeError on some Pydantic 2.7 builds. Force `by_alias` to a
# boolean to keep LangGraph/ChatOpenAI happy until dependencies are bumped.
try:  # noqa: E722 – defensive patch; don't crash service if import fails
    import openai._compat as _openai_compat

    _orig_model_dump = _openai_compat.model_dump

    def _model_dump_safe(model, *, exclude=None, exclude_unset=False,
                         exclude_defaults=False, warnings=True,
                         mode="python", by_alias=None):
        if by_alias is None:
            by_alias = False
        return _orig_model_dump(
            model,
            exclude=exclude,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            warnings=warnings,
            mode=mode,
            by_alias=by_alias,
        )

    _openai_compat.model_dump = _model_dump_safe
    logger.debug("Applied OpenAI/Pydantic model_dump compatibility patch")
except Exception as e:  # pragma: no cover - best-effort guard
    logger.warning(f"OpenAI compat patch failed: {e}")
# --------------------------------------------------------------------------

# Import tool routers
from tools import summarizer_router, notion_router, combo_router
from tools.vocabulary_routes import router as vocabulary_router
from db.prompt_logs import insert_record

# Import authentication
from auth import User, get_current_user

# Import session management and agentic RAG
from db.sessions import (
    create_session, get_session, list_user_sessions, 
    add_message, get_session_messages, delete_session, update_session_title,
    deactivate_session
)
from agentic import create_agentic_rag_graph, ConversationState
from agentic.prompts import IMAGE_ANALYSIS_PROMPT, build_summarization_system_prompt
from db import get_pool  # For seeding test user when auth bypass is enabled

# Pydantic Models
class QueryRequest(BaseModel):
    query: str
    use_vector_search: bool = True

class QueryResponse(BaseModel):
    answer: str
    sources: List[str] = []
    timestamp: str

class StoreKnowledgeRequest(BaseModel):
    query: str
    answer: str
    sources: List[str] = []

class AskRequest(BaseModel):
    user_input: str
    session_id: Optional[str] = None  # NEW: Optional session ID for conversation continuity
    selected_models: List[str] = ["OpenAI", "Claude", "Gemini", "Grok"]
    use_agentic_rag: bool = True  # NEW: Enable/disable agentic RAG workflow

class AskResponse(BaseModel):
    id: Optional[str] = None  # legacy QA id
    session_id: Optional[str] = None  # return session for continuation
    summary: str
    answers: Dict[str, str] = {}
    related_knowledge: List[Dict] = []
    suggested_topics: List[str] = []

class ImageAnalysisRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"  # image/jpeg, image/png, image/webp
    prompt: Optional[str] = IMAGE_ANALYSIS_PROMPT
    user_query: Optional[str] = None  # Additional text input from user to provide context
    session_id: Optional[str] = None  # Link to conversation if provided
    selected_models: List[str] = ["OpenAI", "Claude", "Gemini", "Grok"]

class ImageAnalysisResponse(BaseModel):
    session_id: Optional[str] = None  # Return session id for client continuity
    summary: str  # Consensus from all models
    descriptions: Dict[str, str] = {}  # Individual model responses
    extracted_text: str
    suggested_search_queries: List[str] = []
    timestamp: str

# Initialize FastAPI app
app = FastAPI(
    title="Second Brain API Service",
    version="1.0.0",
    root_path="/api"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Startup: seed test user when ENABLE_TEST_MODE is true
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def seed_test_user():
    """Insert a stub user so FK constraints succeed in test mode."""
    if os.getenv("ENABLE_TEST_MODE", "false").lower() != "true":
        return

    test_user = {
        "id": os.getenv("TEST_USER_ID", "local-test-user"),
        "email": os.getenv("TEST_USER_EMAIL", "test@localhost"),
        "name": os.getenv("TEST_USER_NAME", "Local Test User"),
        "picture": None,
    }

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (id, email, name, picture)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (id) DO UPDATE SET
                    email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    picture = EXCLUDED.picture,
                    last_login = NOW();
                """,
                test_user["id"],
                test_user["email"],
                test_user["name"],
                test_user["picture"],
            )
            logger.info("🧪 Test user seeded for ENABLE_TEST_MODE: %s (%s)", test_user["name"], test_user["email"])
    except Exception as e:
        logger.error("Failed to seed test user: %s", e)

# Include tool routers
app.include_router(summarizer_router)
app.include_router(notion_router)  
app.include_router(combo_router)
app.include_router(vocabulary_router)  # Add vocabulary routes

# Service URLs
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://vector:8002")
FRONTEND_SERVICE_URL = os.getenv("FRONTEND_SERVICE_URL", "http://frontend:8000")

async def _extract_topics_from_question(question: str) -> List[str]:
    """Extract relevant topics from a question using LLM for unrestricted topic discovery"""
    try:
        # Use OpenAI to extract topics naturally without predefined categories
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("No OpenAI API key found for topic extraction")
            return []  # Return empty if no API key
        
        topic_extraction_prompt = f"""
Extract 1-3 specific, meaningful topics from this question. Topics should be:
- Specific and descriptive (not generic like "general" or "knowledge")
- Relevant to the actual subject matter
- Suitable for knowledge organization
- Lowercase, hyphenated if multiple words

Question: "{question}"

Return only the topics as a comma-separated list, nothing else.
Examples:
- "machine-learning" not "technology"
- "yoga-philosophy" not "health"  
- "quantum-physics" not "science"
- "renaissance-art" not "art"
"""
        
        model = os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL)
        # GPT-5 models don't support temperature and use max_completion_tokens
        is_new_model = model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")
        
        request_json = {
            "model": model,
            "messages": [{"role": "user", "content": topic_extraction_prompt}],
        }
        
        if is_new_model:
            request_json["max_completion_tokens"] = 100
        else:
            request_json["temperature"] = 0.3
            request_json["max_tokens"] = 100
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json,
                timeout=15.0
            )
            
            if response.status_code == 200:
                data = response.json()
                topics_text = data["choices"][0]["message"]["content"].strip()
                print(f"LLM topic extraction for '{question[:50]}...': {topics_text}")
                
                # Parse the comma-separated topics
                topics = [topic.strip().lower() for topic in topics_text.split(",") if topic.strip()]
                
                # Clean and validate topics
                valid_topics = []
                for topic in topics:
                    # Remove any quotes or extra formatting
                    topic = topic.strip('"\'').strip()
                    # Skip generic or empty topics
                    if topic and len(topic) > 2 and topic not in ["general", "knowledge", "question", "topic", "misc"]:
                        valid_topics.append(topic)
                
                print(f"Final extracted topics: {valid_topics}")
                return valid_topics[:3]  # Limit to 3 topics
            else:
                print(f"OpenAI API error for topic extraction: {response.status_code} - {response.text[:100]}")
                return []  # Return empty if API call fails
                
    except Exception as e:
        print(f"Topic extraction error: {e}")
        return []  # Return empty on any error

# Direct HTTP LLM calls to avoid dependency issues
async def get_openai_response(query: str) -> str:
    """Get response from OpenAI using direct HTTP"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return f"OpenAI response for: '{query}' (API key not configured)"
        
        # Add current date context to the query
        current_date = datetime.now().strftime("%B %d, %Y")
        enhanced_query = f"Today's date is {current_date}. {query}"
        
        model = os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL)
        # GPT-5 and reasoning models have different parameter requirements
        is_new_model = model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")
        
        request_json = {
            "model": model,
            "messages": [{"role": "user", "content": enhanced_query}],
        }
        
        # GPT-5 models don't support temperature parameter, only add for older models
        if not is_new_model:
            request_json["temperature"] = float(os.getenv("OPENAI_TEMPERATURE", "0"))
            request_json["max_tokens"] = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
        else:
            request_json["max_completion_tokens"] = int(os.getenv("OPENAI_MAX_TOKENS", "4000"))
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json=request_json,
                timeout=float(os.getenv("LLM_TIMEOUT", "120"))
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"OpenAI API error: {response.status_code} - {response.text[:100]}"
                
    except Exception as e:
        return f"OpenAI error: {str(e)[:100]}..."

async def get_claude_response(query: str) -> str:
    """Get response from Claude using direct HTTP"""
    try:
        api_key = os.getenv("CLAUDE_API_KEY")
        if not api_key:
            return f"Claude response for: '{query}' (API key not configured)"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01"
                },
                json={
                    "model": os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022"),
                    "max_tokens": int(os.getenv("CLAUDE_MAX_TOKENS", "4000")),
                    "temperature": float(os.getenv("CLAUDE_TEMPERATURE", "0")),
                    "messages": [{"role": "user", "content": query}]
                },
                timeout=float(os.getenv("LLM_TIMEOUT", "120"))
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["content"][0]["text"]
            else:
                return f"Claude API error: {response.status_code} - {response.text[:100]}"
                
    except Exception as e:
        return f"Claude error: {str(e)[:100]}..."

async def get_gemini_response(query: str) -> str:
    """Get response from Gemini using direct HTTP"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return f"Gemini response for: '{query}' (API key not configured)"
        
        # Add current date context to the query
        current_date = datetime.now().strftime("%B %d, %Y")
        enhanced_query = f"Today's date is {current_date}. {query}"
        
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": enhanced_query}]}],
                    "generationConfig": {
                        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0")),
                        "maxOutputTokens": int(os.getenv("GEMINI_MAX_TOKENS", "4000"))
                    }
                },
                timeout=float(os.getenv("LLM_TIMEOUT", "120"))
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            else:
                return f"Gemini API error: {response.status_code} - {response.text[:100]}"
                
    except Exception as e:
        return f"Gemini error: {str(e)[:100]}..."

async def get_grok_response(query: str) -> str:
    """Get response from Grok using direct HTTP"""
    try:
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            return f"Grok response for: '{query}' (API key not configured)"
        
        # Add current date context to the query
        current_date = datetime.now().strftime("%B %d, %Y")
        enhanced_query = f"Today's date is {current_date}. {query}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.x.ai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": os.getenv("GROK_MODEL", "grok-2-1212"),
                    "messages": [{"role": "user", "content": enhanced_query}],
                    "temperature": float(os.getenv("GROK_TEMPERATURE", "0")),
                    "max_tokens": int(os.getenv("GROK_MAX_TOKENS", "4000"))
                },
                timeout=float(os.getenv("LLM_TIMEOUT", "120"))
            )
            
            if response.status_code == 200:
                data = response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Grok API error: {response.status_code} - {response.text[:100]}"
                
    except Exception as e:
        return f"Grok error: {str(e)[:100]}..."

async def get_gemini_pro_summary(question: str, llm_responses: Dict[str, str]) -> str:
    """Use Gemini 2.0 Pro to create a comprehensive summary from all LLM responses"""
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return f"Summary of responses to: '{question}' (Gemini API key not configured)"
        
        # Format all responses for summarization
        responses_text = ""
        for model, response in llm_responses.items():
            if response and not response.startswith(f"{model} error"):
                responses_text += f"\n--- {model} Response ---\n{response}\n"
        
        if not responses_text.strip():
            return f"No valid responses available to summarize for question: '{question}'"
        
        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Create summarization prompt
        summarization_prompt = f"""
Today's date is {current_date}.

You are an expert AI summarizer. Given the following question and multiple AI model responses, create a comprehensive, coherent summary that:

1. Synthesizes the key insights from all responses
2. Identifies common themes and agreements
3. Notes any significant differences or contradictions
4. Provides a balanced, well-structured summary
5. Maintains accuracy while being concise

Original Question: "{question}"

AI Model Responses:
{responses_text}

Please provide a comprehensive summary that combines the best insights from all responses:
"""
        
        # Use configured Gemini model for summarization
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                headers={"Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": summarization_prompt}]}],
                    "generationConfig": {
                        "temperature": float(os.getenv("GEMINI_TEMPERATURE", "0.3")),
                        "maxOutputTokens": int(os.getenv("GEMINI_MAX_TOKENS", "2000"))
                    }
                },
                timeout=45.0  # Longer timeout for summarization
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data["candidates"][0]["content"]["parts"][0]["text"]
                return summary.strip()
            else:
                return f"Gemini Pro summarization error: {response.status_code} - Fallback summary of {len(llm_responses)} AI responses to '{question}'"
                
    except Exception as e:
        return f"Gemini Pro summary error: {str(e)[:100]}... Fallback: Multiple AI models provided responses to '{question}'"

async def get_openai_summary(question: str, llm_responses: Dict[str, str]) -> str:
    """Use OpenAI to create a comprehensive summary from all LLM responses"""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return f"Summary of responses to: '{question}' (OpenAI API key not configured)"
        
        # Format all responses for summarization
        responses_text = ""
        for model, response in llm_responses.items():
            if response and not response.startswith(f"{model} error"):
                responses_text += f"\n--- {model} Response ---\n{response}\n"
        
        if not responses_text.strip():
            return f"No valid responses to summarize for: '{question}'"
        
        # Get current date for context
        current_date = datetime.now().strftime("%B %d, %Y")
        
        # Create summarization prompt
        system_prompt = build_summarization_system_prompt(current_date)
        
        user_prompt = f"""Question: {question}

Here are responses from multiple AI models:
{responses_text}

Please provide a comprehensive summary that:
1. Combines the most accurate and relevant information
2. Resolves any contradictions by favoring factual content
3. Is clear, concise, and directly answers the question
4. Maintains technical accuracy while being accessible"""

        model = os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL)
        # GPT-5 models don't support temperature and use max_completion_tokens
        is_new_model = model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")
        
        request_json = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        }
        
        if is_new_model:
            request_json["max_completion_tokens"] = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
        else:
            request_json["temperature"] = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
            request_json["max_tokens"] = int(os.getenv("OPENAI_MAX_TOKENS", "2000"))
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=request_json,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                summary = data["choices"][0]["message"]["content"]
                return summary.strip()
            else:
                return f"OpenAI summarization error: {response.status_code} - Fallback summary of {len(llm_responses)} AI responses to '{question}'"
                
    except Exception as e:
        return f"OpenAI summary error: {str(e)[:100]}... Fallback: Multiple AI models provided responses to '{question}'"

async def get_smart_summary(question: str, llm_responses: Dict[str, str]) -> str:
    """Smart summarization with Gemini primary and OpenAI fallback on quota errors"""
    try:
        # First, try Gemini Pro
        summary = await get_gemini_pro_summary(question, llm_responses)
        
        # Check if Gemini returned a quota error (429) or quota-related message
        quota_indicators = ["429", "quota", "exceeded", "rate limit", "too many requests"]
        if any(indicator in summary.lower() for indicator in quota_indicators) and "gemini" in summary.lower():
            print(f"Gemini quota/rate limit detected, falling back to OpenAI for summarization")
            print(f"Gemini error was: {summary[:200]}...")
            summary = await get_openai_summary(question, llm_responses)
            # Removed prefix - users don't need to see fallback details
        
        return summary
        
    except Exception as e:
        print(f"Error in smart summary, falling back to OpenAI: {str(e)}")
        # If anything goes wrong with Gemini, use OpenAI
        fallback_summary = await get_openai_summary(question, llm_responses)
        return fallback_summary  # Removed prefix

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "api"}

# ============ SESSION MANAGEMENT ENDPOINTS ============

@app.post("/sessions/create")
async def create_new_session(
    title: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """Create a new conversation session"""
    try:
        session_id = await create_session(user.id, title)
        return {
            "session_id": session_id,
            "message": "Session created successfully",
            "title": title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        }
    except Exception as e:
        logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions")
async def list_sessions(
    limit: int = 50,
    include_inactive: bool = False,
    user: User = Depends(get_current_user)
):
    """List all sessions for the current user"""
    try:
        sessions = await list_user_sessions(user.id, limit, include_inactive)
        return {
            "sessions": sessions,
            "total": len(sessions)
        }
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sessions/{session_id}")
async def get_session_detail(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """Get session details and message history"""
    try:
        # Get session metadata
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Verify ownership
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Get messages
        messages = await get_session_messages(session_id)
        
        return {
            "session": session,
            "messages": messages,
            "message_count": len(messages)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/sessions/{session_id}")
async def delete_session_endpoint(
    session_id: str,
    user: User = Depends(get_current_user)
):
    """Delete a conversation session"""
    try:
        # Verify ownership first
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Delete the session
        deleted = await delete_session(session_id)
        if not deleted:
            raise HTTPException(status_code=500, detail="Failed to delete session")
        
        return {"message": "Session deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/sessions/{session_id}/title")
async def update_session_title_endpoint(
    session_id: str,
    title: str,
    user: User = Depends(get_current_user)
):
    """Update session title"""
    try:
        # Verify ownership
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Update title
        updated = await update_session_title(session_id, title)
        if not updated:
            raise HTTPException(status_code=500, detail="Failed to update title")
        
        return {"message": "Title updated successfully", "title": title}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating session title: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/sessions/new")
async def start_new_session_endpoint(
    previous_session_id: Optional[str] = None,
    user: User = Depends(get_current_user)
):
    """End current session (if provided and owned) and start a new one"""
    try:
        if previous_session_id:
            session = await get_session(previous_session_id)
            if session and session["user_id"] == user.id:
                await deactivate_session(previous_session_id)
        new_session_id = await create_session(user.id)
        return {"session_id": new_session_id, "message": "New session created"}
    except Exception as e:
        logger.error(f"Error creating new session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ ENHANCED ASK ENDPOINT WITH AGENTIC RAG ============

@app.post("/ask", response_model=AskResponse)
async def ask_question(
    request: AskRequest,
    user: User = Depends(get_current_user)  # ← Add authentication
):
    """Enhanced ask endpoint with session management and agentic RAG"""
    
    logger.debug(f"📝 Processing question from user {user.name} ({user.email}, ID: {user.id[:8]}...): {request.user_input[:50]}...")
    
    # Session management: Create or use existing session
    session_id = request.session_id
    # If client sends an invalid UUID (e.g., legacy qa_ ids), ignore and start fresh
    if session_id:
        try:
            UUID(session_id)
        except Exception:
            logger.warning(f"Ignoring invalid session_id '{session_id}', creating a new session")
            session_id = None
    if not session_id:
        # Create a new session automatically
        session_id = await create_session(user.id, f"Chat {datetime.now().strftime('%H:%M')}")
        logger.info(f"Created new session {session_id} for user {user.id[:8]}...")
    else:
        # Verify session exists and user owns it
        session = await get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        if session["user_id"] != user.id:
            raise HTTPException(status_code=403, detail="Access denied to this session")
        logger.info(f"Using existing session {session_id}")
    
    # Add user message to session
    await add_message(session_id, "user", request.user_input)
    
    # Initialize variables
    summary = ""
    related_knowledge = []
    answers = {}
    
    # Decide whether to use Agentic RAG or traditional flow
    if request.use_agentic_rag and os.getenv("OPENAI_API_KEY"):
        logger.info("🤖 Using Agentic RAG workflow")
        
        try:
            # Create the Lang Graph workflow
            graph = create_agentic_rag_graph()
            
            # Get recent conversation history
            recent_messages = await get_session_messages(session_id, limit=20)
            
            # Build initial state
            initial_state: ConversationState = {
                "session_id": session_id,
                "user_id": user.id,
                "messages": [{"role": msg["role"], "content": msg["content"]} for msg in recent_messages],
                "current_query": request.user_input,
                "retrieved_context": [],
                "llm_answers": {},
                "llm_errors": {},
                "agent_thoughts": [],
                "iteration_count": 0,
                "max_iterations": int(os.getenv("AGENTIC_MAX_ITERATIONS", "2")),
                "should_retrieve": True,
                "should_refine": False,
                "final_answer": None,
                "selected_models": request.selected_models
            }
            
            # Execute the graph
            logger.info("Executing LangGraph workflow...")
            result = await graph.ainvoke(initial_state)
            
            # Extract the final answer
            summary = result.get("final_answer", "")
            retrieved_context = result.get("retrieved_context", [])
            agent_thoughts = result.get("agent_thoughts", [])
            answers = result.get("llm_answers", {})
            errors = result.get("llm_errors", {})
            # surface errors in answers so UI shows availability without polluting synthesis
            for name, err in errors.items():
                answers[name] = f"{name} unavailable: {err}"
            
            logger.info(f"Agent completed with {len(agent_thoughts)} reasoning steps and {len(answers)} model outputs")
            
            # Use retrieved context as related knowledge
            related_knowledge = retrieved_context[:5]  # Limit to 5 items
            
        except Exception as e:
            logger.exception(f"Agentic RAG error; falling back to traditional flow: {e}")
            # Fall back to traditional flow
            request.use_agentic_rag = False
    
    # Traditional multi-LLM flow (fallback or if use_agentic_rag=False)
    if not request.use_agentic_rag or not os.getenv("OPENAI_API_KEY"):
        logger.info("🔄 Using traditional multi-LLM workflow")
        
        # Get vector search results (with enhanced stub data for demo)
        related_knowledge = []
        try:
            async with httpx.AsyncClient() as client:
                vector_response = await client.post(
                    f"{VECTOR_SERVICE_URL}/concepts/search",
                    json={"query": request.user_input, "limit": 3},
                    timeout=30.0
                )
                logger.debug(f"Vector service response status: {vector_response.status_code}")
                if vector_response.status_code == 200:
                    vector_data = vector_response.json()
                    related_knowledge = vector_data.get("results", [])
                    logger.debug(f"Vector service returned {len(related_knowledge)} results")
        except Exception as e:
            logger.error(f"Vector service error: {e}")
        
        # Get real AI model responses based on selected models
        llm_functions = {
            "OpenAI": get_openai_response,
            "Claude": get_claude_response,
            "Gemini": get_gemini_response,
            "Grok": get_grok_response
        }
        
        # Call selected LLMs concurrently
        tasks = []
        selected_llms = []
        for model in request.selected_models:
            if model in llm_functions:
                tasks.append(llm_functions[model](request.user_input))
                selected_llms.append(model)
        
        # Execute all LLM calls concurrently
        try:
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            answers = {}
            for i, (model, response) in enumerate(zip(selected_llms, responses)):
                if isinstance(response, Exception):
                    answers[model] = f"{model} error: {str(response)[:100]}..."
                else:
                    answers[model] = response
        except Exception as e:
            answers = {model: f"{model} response error" for model in request.selected_models}
        
    # Generate comprehensive summary
    summary = await get_smart_summary(request.user_input, answers)
    
    # Add assistant message to session
    await add_message(session_id, "assistant", summary, metadata={"models_used": request.selected_models})
    
    # Generate suggested topics using LLM-based extraction
    suggested_topics = []
    
    # Extract topics from related knowledge first
    for item in related_knowledge:
        if "topics" in item:
            suggested_topics.extend(item["topics"])
    
    # Add the topics we just extracted from the current question
    current_question_topics = await _extract_topics_from_question(request.user_input)
    suggested_topics.extend(current_question_topics)
    
    # Remove duplicates and limit to 5 topics
    suggested_topics = list(set(suggested_topics))[:5]
    
    # Determine if the answer is informative; skip storing noisy "no record" responses in vector DB
    lower_summary = summary.lower() if isinstance(summary, str) else ""
    is_informative = not any(phrase in lower_summary for phrase in [
        "don't have a record",
        "do not have a record",
        "no record",
        "cannot find",
        "don't have enough information",
        "i'm sorry, but i don't have"
    ])
    
    # Store the knowledge in database with session linkage (always)
    try:
        await insert_record(
            user_input=request.user_input,
            answers=answers,
            summary=summary,
            user_id=user.id,
            session_id=session_id  # Link to session
        )
        logger.debug(f"💾 ✅ Stored Q&A in PostgreSQL for user {user.name} ({user.email}, ID: {user.id[:8]}...): {request.user_input[:50]}...")
    except Exception as e:
        logger.error(f"❌ Error storing knowledge in database: {e}")
    
    # Store in vector DB only if informative to avoid polluting retrieval
    if is_informative:
        try:
            # Use adaptive chunking for LLM answers (hierarchical markdown splitting)
            chunks = adaptive_chunk_text(
                text=f"Q: {request.user_input}\nA: {summary}",
                content_type="answer"  # Enable hierarchical markdown chunking
            )
            chunk_total = len(chunks)
            concepts = []
            base_id = f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.id[:8]}"
            for idx, chunk in enumerate(chunks):
                concepts.append({
                    "id": f"{base_id}_c{idx}",
                    "content": chunk,
                    "type": "qa_concept",
                    "metadata": {
                        "user_id": user.id,
                        "question": request.user_input,
                        "summary": summary,
                        "topics": suggested_topics,
                        "timestamp": datetime.now().isoformat(),
                        "chunk_index": idx,
                        "chunk_total": chunk_total,
                        "chunking_method": "adaptive_markdown",  # Track method used
                    }
                })
            
            async with httpx.AsyncClient() as client:
                concept_data = {"concepts": concepts}
                logger.debug(f"Attempting to store {chunk_total} chunks in vector database...")
                vector_response = await client.post(
                    f"{VECTOR_SERVICE_URL}/concepts/add",
                    json=concept_data,
                    timeout=30.0
                )
                logger.debug(f"Vector service response: {vector_response.status_code}")
                if vector_response.status_code == 200:
                    logger.debug(f"🔷 ✅ Stored {chunk_total} Q&A chunks in Vector DB for user {user.name} ({user.email}, ID: {user.id[:8]}...): {request.user_input[:50]}...")
                else:
                    response_text = vector_response.text[:200] if vector_response.text else "No response text"
                    logger.error(f"❌ Failed to store in vector database: {vector_response.status_code} - {response_text}")
        except Exception as e:
            logger.error(f"❌ Error storing in vector database: {e}")
    
    return AskResponse(
        id=f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        session_id=session_id,
        summary=summary,
        answers=answers,
        related_knowledge=related_knowledge,
        suggested_topics=suggested_topics
    )

@app.post("/analyze-image", response_model=ImageAnalysisResponse)
async def analyze_image(
    request: ImageAnalysisRequest,
    user: User = Depends(get_current_user)  # ← Add authentication
):
    """Analyze an image using multiple vision models with optional text context"""
    
    print(f"📷 Processing image analysis from user {user.name} ({user.email}, ID: {user.id[:8]}...)")
    
    # Debug: Log request details (without full base64)
    image_len = len(request.image_base64) if request.image_base64 else 0
    print(f"📷 Image base64 length: {image_len} chars")
    print(f"📷 MIME type: {request.mime_type}")
    print(f"📷 Selected models: {request.selected_models}")
    print(f"📷 First 50 chars of base64: {request.image_base64[:50] if image_len > 50 else request.image_base64}")
    
    try:
        # Session management (optional)
        session_id = request.session_id
        if session_id:
            try:
                UUID(session_id)
            except Exception:
                logger.warning(f"Ignoring invalid session_id '{session_id}' for image analysis")
                session_id = None
        if not session_id:
            session_id = await create_session(user.id, f"Image Chat {datetime.now().strftime('%H:%M')}")
        else:
            session = await get_session(session_id)
            if not session or session["user_id"] != user.id:
                session_id = await create_session(user.id, f"Image Chat {datetime.now().strftime('%H:%M')}")

        # Enhance the prompt with user's query if provided
        analysis_prompt = request.prompt
        if request.user_query:
            analysis_prompt = f"{request.prompt}\n\nUser's specific question/context: {request.user_query}"
        
        # Store user message in session
        await add_message(session_id, "user", request.user_query or "[Image uploaded]", metadata={"is_image": True})
        
        # Call selected vision models
        descriptions = {}
        tasks = []
        
        async def analyze_with_openai():
            try:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    return ("OpenAI", "OpenAI API key not configured")
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "gpt-4o",
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": analysis_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:{request.mime_type};base64,{request.image_base64}"}}
                                ]
                            }],
                            "max_tokens": 2000
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return ("OpenAI", result["choices"][0]["message"]["content"])
                    return ("OpenAI", f"Error: {response.status_code}")
            except Exception as e:
                return ("OpenAI", f"Error: {str(e)}")
        
        async def analyze_with_claude():
            try:
                api_key = os.getenv("CLAUDE_API_KEY")
                if not api_key:
                    return ("Claude", "Claude API key not configured")
                
                # Detect actual image format from base64 data
                import base64
                try:
                    image_data = base64.b64decode(request.image_base64)
                    # Check magic bytes to detect actual format
                    if image_data[:8] == b'\x89PNG\r\n\x1a\n':
                        mime_type = "image/png"
                    elif image_data[:3] == b'\xff\xd8\xff':
                        mime_type = "image/jpeg"
                    elif image_data[:6] in (b'GIF87a', b'GIF89a'):
                        mime_type = "image/gif"
                    elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
                        mime_type = "image/webp"
                    else:
                        # Fallback to request mime_type or jpeg
                        mime_type = request.mime_type if request.mime_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/jpeg"
                except Exception:
                    # If detection fails, use request mime_type or default to jpeg
                    mime_type = request.mime_type if request.mime_type in ["image/jpeg", "image/png", "image/gif", "image/webp"] else "image/jpeg"
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": api_key,
                            "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "claude-3-5-sonnet-20241022",
                            "max_tokens": 2000,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {
                                            "type": "base64",
                                            "media_type": mime_type,
                                            "data": request.image_base64
                                        }
                                    },
                                    {"type": "text", "text": analysis_prompt}
                                ]
                            }]
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return ("Claude", result["content"][0]["text"])
                    # Return detailed error information
                    error_text = response.text[:200] if response.text else "No error details"
                    return ("Claude", f"Error {response.status_code}: {error_text}")
            except Exception as e:
                return ("Claude", f"Error: {str(e)}")
        
        async def analyze_with_gemini():
            try:
                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    return ("Gemini", "Gemini API key not configured")
                
                # Use configured Gemini model
                model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-exp")
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
                        headers={"Content-Type": "application/json"},
                        json={
                            "contents": [{
                                "parts": [
                                    {"text": analysis_prompt},
                                    {"inlineData": {"mimeType": request.mime_type, "data": request.image_base64}}
                                ]
                            }]
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return ("Gemini", result["candidates"][0]["content"]["parts"][0]["text"])
                    return ("Gemini", f"Error: {response.status_code}")
            except Exception as e:
                return ("Gemini", f"Error: {str(e)}")
        
        async def analyze_with_grok():
            try:
                api_key = os.getenv("GROK_API_KEY")
                if not api_key:
                    return ("Grok", "Grok API key not configured")
                
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        "https://api.x.ai/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": "grok-2-vision-1212",
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": analysis_prompt},
                                    {"type": "image_url", "image_url": {"url": f"data:{request.mime_type};base64,{request.image_base64}"}}
                                ]
                            }],
                            "max_tokens": 2000
                        }
                    )
                    if response.status_code == 200:
                        result = response.json()
                        return ("Grok", result["choices"][0]["message"]["content"])
                    # Return detailed error information
                    error_text = response.text[:200] if response.text else "No error details"
                    return ("Grok", f"Error {response.status_code}: {error_text}")
            except Exception as e:
                return ("Grok", f"Error: {str(e)}")
        
        # Call selected models
        if "OpenAI" in request.selected_models:
            tasks.append(analyze_with_openai())
        if "Claude" in request.selected_models:
            tasks.append(analyze_with_claude())
        if "Gemini" in request.selected_models:
            tasks.append(analyze_with_gemini())
        if "Grok" in request.selected_models:
            tasks.append(analyze_with_grok())
        
        if not tasks:
            raise HTTPException(400, "No models selected")
        
        # Execute all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Collect descriptions
        for result in results:
            if isinstance(result, tuple):
                model_name, description = result
                descriptions[model_name] = description
        
        # Generate consensus summary using smart summarization
        valid_descriptions = {k: v for k, v in descriptions.items() if not v.startswith("Error")}
        if valid_descriptions:
            if len(valid_descriptions) == 1:
                # Single model: use its description directly
                summary = list(valid_descriptions.values())[0]
            else:
                # Multiple models: use smart summarization with the same prompt sent to LLMs
                summary = await get_smart_summary(analysis_prompt, valid_descriptions)
        else:
            summary = "All models encountered errors analyzing this image."
        
        # Store assistant message in session for continuity
        try:
            await add_message(session_id, "assistant", summary, metadata={"is_image": True, "models_used": request.selected_models})
        except Exception as e:
            logger.error(f"Failed to add assistant image message to session: {e}")
        
        # Extract keywords for search queries
        all_text = " ".join(valid_descriptions.values()) if isinstance(valid_descriptions, dict) else " ".join(valid_descriptions)
        keywords = []
        for word in all_text.split():
            word_clean = word.strip('.,!?;:').lower()
            if len(word_clean) > 4 and word_clean not in ['image', 'shows', 'contains', 'appears', 'this', 'that', 'with', 'from']:
                if word_clean not in keywords:
                    keywords.append(word_clean)
        
        suggested_queries = keywords[:3] if keywords else [summary[:50]]
        
        # Store image analysis in databases (PostgreSQL + Vector DB)
        try:
            # Extract topics from query or summary
            if request.user_query:
                topics = await _extract_topics_from_question(request.user_query)
                user_input = f"Image Query: {request.user_query}"
                storage_content = f"Q: {request.user_query}\nA: {summary}"
            else:
                # Extract topics from summary if no user query
                topics = await _extract_topics_from_question(summary[:200])
                user_input = "Image Analysis"
                storage_content = f"Image Analysis: {summary}"
            
            # Generate unique ID for this analysis
            analysis_id = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.id[:8]}"  # ← Include user_id in ID
            
            # Store in PostgreSQL
            await insert_record(
                user_input=user_input,
                answers=descriptions,
                summary=summary,
                user_id=user.id,  # ← Add user_id
                session_id=session_id
            )
            print(f"💾 ✅ Stored image analysis in PostgreSQL for user {user.name} ({user.email}, ID: {user.id[:8]}...): {user_input[:50]}...")
            
            # Store in vector database for semantic search
            async with httpx.AsyncClient() as client:
                # Use adaptive chunking for image analysis content
                chunks = adaptive_chunk_text(
                    text=storage_content,
                    content_type="answer"  # Image analysis can benefit from markdown structure too
                )
                chunk_total = len(chunks)
                concepts = []
                for idx, chunk in enumerate(chunks):
                    concepts.append({
                        "id": f"{analysis_id}_c{idx}",
                        "content": chunk,
                        "type": "image_analysis",
                        "metadata": {
                            "user_id": user.id,
                            "session_id": session_id,
                            "query": request.user_query if request.user_query else "Image Analysis",
                            "summary": summary,
                            "topics": topics,
                            "timestamp": datetime.now().isoformat(),
                            "is_image": True,
                            "chunk_index": idx,
                            "chunking_method": "adaptive_markdown",
                            "chunk_total": chunk_total,
                        }
                    })
                concept_data = {"concepts": concepts}
                
                vector_response = await client.post(
                    f"{VECTOR_SERVICE_URL}/concepts/add",
                    json=concept_data,
                    timeout=30.0
                )
                
                if vector_response.status_code == 200:
                    print(f"🔷 ✅ Stored image analysis in Vector DB for user {user.name} ({user.email}, ID: {user.id[:8]}...): {analysis_id}")
                else:
                    response_text = vector_response.text[:200] if vector_response.text else "No response text"
                    print(f"❌ Failed to store in vector DB: {vector_response.status_code} - {response_text}")
                    
        except Exception as e:
            # Log error but don't fail the request
            print(f"❌ Error storing image analysis: {e}")
        
        return ImageAnalysisResponse(
            session_id=session_id,
            summary=summary,
            descriptions=descriptions,
            extracted_text=all_text[:500],
            suggested_search_queries=suggested_queries,
            timestamp=datetime.now().isoformat()
        )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Image analysis error: {str(e)}")

@app.post("/reset")
async def reset_session():
    """Reset session/memory (stub implementation)"""
    return {"message": "Session reset successfully", "timestamp": datetime.now().isoformat()}

@app.post("/query", response_model=QueryResponse)
async def query_llm(request: QueryRequest):
    """Main query endpoint (stub implementation)"""
    
    # Simulate vector search if requested
    similar_docs = []
    if request.use_vector_search:
        try:
            async with httpx.AsyncClient() as client:
                vector_response = await client.post(
                    f"{VECTOR_SERVICE_URL}/concepts/search",  # Fixed endpoint
                    json={"query": request.query, "limit": 3},
                    timeout=30.0
                )
                if vector_response.status_code == 200:
                    vector_data = vector_response.json()
                    similar_docs = [result["summary"] for result in vector_data.get("results", [])]
        except Exception as e:
            print(f"Vector service error: {e}")
    
    # Simulate LLM response (stub)
    answer = f"This is a stub response for: '{request.query}'"
    if similar_docs:
        answer += f"\n\nSimilar content found: {', '.join(similar_docs)}"
    
    return QueryResponse(
        answer=answer,
        sources=similar_docs,
        timestamp=datetime.now().isoformat()
    )

@app.post("/store-knowledge")
async def store_knowledge(request: StoreKnowledgeRequest):
    """Store knowledge in vector database"""
    try:
        async with httpx.AsyncClient() as client:
            # Store in vector database
            vector_response = await client.post(
                f"{VECTOR_SERVICE_URL}/store-knowledge",
                json={
                    "query": request.query,
                    "summary": request.answer,
                    "answers": {"sources": request.sources}
                },
                timeout=30.0
            )
            
            if vector_response.status_code == 200:
                return {"message": "Knowledge stored successfully", "timestamp": datetime.now().isoformat()}
            else:
                raise HTTPException(500, "Failed to store in vector database")
                
    except Exception as e:
        raise HTTPException(500, f"Error storing knowledge: {str(e)}")

@app.get("/search/{query}")
async def search_knowledge(query: str, limit: int = 10, score_threshold: float = 0.3):
    """Search existing knowledge with configurable similarity threshold"""
    try:
        async with httpx.AsyncClient() as client:
            vector_response = await client.post(
                f"{VECTOR_SERVICE_URL}/concepts/search",  # Fixed endpoint
                json={"query": query, "limit": limit, "score_threshold": score_threshold},
                timeout=30.0
            )
            
            if vector_response.status_code == 200:
                return vector_response.json()
            else:
                error_detail = f"Vector service returned {vector_response.status_code}: {vector_response.text[:200]}"
                raise HTTPException(500, error_detail)
                
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Search error: {type(e).__name__}: {str(e)}")

@app.get("/status")
async def get_system_status():
    """Get status of all microservices"""
    status = {
        "api": "healthy",
        "vector": "unknown",
        "frontend": "unknown",
        "timestamp": datetime.now().isoformat()
    }
    
    # Check vector service
    try:
        async with httpx.AsyncClient() as client:
            vector_response = await client.get(f"{VECTOR_SERVICE_URL}/health", timeout=10.0)
            if vector_response.status_code == 200:
                status["vector"] = "healthy"
    except Exception:
        status["vector"] = "unhealthy"
    
    # Check frontend service
    try:
        async with httpx.AsyncClient() as client:
            frontend_response = await client.get(f"{FRONTEND_SERVICE_URL}/health", timeout=10.0)
            if frontend_response.status_code == 200:
                status["frontend"] = "healthy"
    except Exception:
        status["frontend"] = "unhealthy"
    
    return status

# Vector proxy endpoints
@app.post("/vector/search")
async def vector_search_proxy(request: dict):
    """Proxy to vector service search"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTOR_SERVICE_URL}/concepts/search",  # Fixed endpoint
                json=request,
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(500, "Vector search failed")
    except Exception as e:
        raise HTTPException(500, f"Vector search error: {str(e)}")

@app.post("/vector/topics")
async def vector_topics_proxy(user: User = Depends(get_current_user)):  # ← Add authentication
    """Return topics extracted from actual Q&A sessions - optimized with parallel processing"""
    print(f"📊 === Browse Topics requested by user {user.name} ({user.email}, ID: {user.id[:8]}...) ===")
    try:
        import asyncio
        from datetime import date, timedelta
        from db.prompt_logs import fetch_by_date
        from collections import Counter
        
        print("Importing dependencies successful")
        
        # Collect topics from the last 7 days
        topics_counter = Counter()
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        
        print(f"Fetching data from {start_date} to {end_date} for user {user.id}")
        
        # Fetch all dates in parallel
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        # Parallel fetch from database - filter by user_id
        print(f"Fetching data for {len(date_range)} days in parallel...")
        fetch_tasks = [fetch_by_date(d, user_id=user.id) for d in date_range]  # ← Add user_id filter
        all_rows_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        # Collect all rows
        all_rows = []
        for idx, result in enumerate(all_rows_results):
            if isinstance(result, Exception):
                print(f"Error fetching data for {date_range[idx]}: {result}")
            else:
                print(f"Date {date_range[idx]}: found {len(result)} rows")
                all_rows.extend(result)
        
        total_rows_processed = len(all_rows)
        print(f"Total rows to process: {total_rows_processed}")
        
        if total_rows_processed == 0:
            print("No rows found, returning fallback")
            return {
                "topics": [{"topic": "general", "count": 0, "description": "Start asking questions to build your knowledge base"}],
                "total_count": 0,
                "status": "success"
            }
        
        # Extract topics from all Q&A entries in parallel (batch processing)
        print("Extracting topics from all entries in parallel...")
        topic_extraction_tasks = [
            _extract_topics_from_question(row["user_input"])
            for row in all_rows
        ]
        
        # Process in batches to avoid overwhelming the API
        batch_size = 10
        all_topics_results = []
        for i in range(0, len(topic_extraction_tasks), batch_size):
            batch = topic_extraction_tasks[i:i+batch_size]
            print(f"Processing batch {i//batch_size + 1}/{(len(topic_extraction_tasks) + batch_size - 1)//batch_size}")
            batch_results = await asyncio.gather(*batch, return_exceptions=True)
            all_topics_results.extend(batch_results)
        
        # Count topics
        for idx, topics_result in enumerate(all_topics_results):
            if isinstance(topics_result, Exception):
                print(f"Error extracting topics for row {idx}: {topics_result}")
            else:
                for topic in topics_result:
                    topics_counter[topic] += 1
        
        print(f"Topics counter: {dict(topics_counter)}")
        
        # If no real topics found, return a minimal fallback
        if not topics_counter:
            print("No topics found after extraction, returning fallback")
            return {
                "topics": [{"topic": "general", "count": 0, "description": "Start asking questions to build your knowledge base"}],
                "total_count": 0,
                "status": "success"
            }
        
        # Convert to the expected format with dynamic descriptions
        real_topics = []
        for topic, count in topics_counter.most_common(20):  # Top 20 topics (increased from 10)
            # Generate a natural description for any topic
            description = f"Knowledge and discussions about {topic.replace('-', ' ')}"
            
            real_topics.append({
                "topic": topic,
                "count": count,
                "description": description
            })
        
        print(f"Returning {len(real_topics)} topics")
        return {
            "topics": real_topics,
            "total_count": len(real_topics),
            "status": "success"
        }
    except Exception as e:
        print(f"Error in vector_topics_proxy: {e}")
        import traceback
        traceback.print_exc()
        # Fallback to minimal stub if there's an error
        return {
            "topics": [{"topic": "general", "count": 0, "description": "Start asking questions to build your knowledge base"}],
            "total_count": 0,
            "status": "error",
            "message": str(e)
        }

@app.post("/vector/stats")
async def vector_stats_proxy():
    """Proxy to vector service stats"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{VECTOR_SERVICE_URL}/stats",
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(500, "Vector stats failed")
    except Exception as e:
        raise HTTPException(500, f"Vector stats error: {str(e)}")

@app.get("/vector/knowledge-graph")
async def vector_knowledge_graph_proxy(user: User = Depends(get_current_user)):
    """Return user's knowledge graph"""
    try:
        print(f"🕸️ Fetching knowledge graph for user {user.name} ({user.email}, ID: {user.id[:8]}...)")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{VECTOR_SERVICE_URL}/knowledge-graph",
                json={
                    "limit": 100,
                    "similarity_threshold": 0.8,
                    "user_id": user.id
                },
                timeout=60.0
            )
            if response.status_code == 200:
                return response.json()
            else:
                raise HTTPException(500, "Knowledge graph request failed")
    except Exception as e:
        print(f"Knowledge graph error: {str(e)}")
        raise HTTPException(500, f"Knowledge graph error: {str(e)}")

@app.post("/vector/by-topic")
async def vector_by_topic_proxy(request: dict, user: User = Depends(get_current_user)):
    """Return user's entries filtered by topic"""
    try:
        topic = request.get("topic", "")
        limit = request.get("limit", 10)
        
        if not topic:
            raise HTTPException(400, "Topic is required")
        
        print(f"🏷️ Fetching entries for topic '{topic}' for user {user.name} ({user.email}, ID: {user.id[:8]}...)")
        
        # Fetch user's data from the last 30 days
        from datetime import date, timedelta
        from db.prompt_logs import fetch_by_date
        import asyncio
        
        end_date = date.today()
        start_date = end_date - timedelta(days=30)
        
        # Fetch all dates in parallel
        date_range = []
        current_date = start_date
        while current_date <= end_date:
            date_range.append(current_date)
            current_date += timedelta(days=1)
        
        fetch_tasks = [fetch_by_date(d, user_id=user.id) for d in date_range]
        all_rows_results = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        
        # Collect all rows
        all_rows = []
        for result in all_rows_results:
            if isinstance(result, Exception):
                continue
            all_rows.extend(result)
        
        if not all_rows:
            return {
                "results": [],
                "topic": topic,
                "count": 0,
                "status": "success",
                "message": "No entries found"
            }
        
        # Filter by topic (extract topics from each entry and match)
        matching_results = []
        for row in all_rows:
            # Extract topics for this entry
            entry_topics = await _extract_topics_from_question(row["user_input"])
            
            # Check if requested topic matches any of the entry's topics
            if topic in entry_topics:
                matching_results.append({
                    "user_input": row["user_input"],
                    "summary": row.get("summary", ""),
                    "topics": entry_topics,
                    "created_at": row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"])
                })
                
                if len(matching_results) >= limit:
                    break
        
        print(f"Found {len(matching_results)} entries for topic '{topic}'")
        
        return {
            "results": matching_results[:limit],
            "topic": topic,
            "count": len(matching_results),
            "status": "success"
        }
    except Exception as e:
        raise HTTPException(500, f"Vector by-topic error: {str(e)}")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
    )
