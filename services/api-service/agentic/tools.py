"""
RAG tools for the agentic system
"""
import os
import httpx
from typing import List, Dict, Any
from langchain_core.tools import tool
import logging

logger = logging.getLogger(__name__)

# Service URLs
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://vector:8002")
SIM_THRESHOLD = float(os.getenv("AGENTIC_SIM_THRESHOLD", "0.6"))


@tool
async def semantic_search_tool(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search the vector database for semantically similar content.
    
    Args:
        query: The search query text
        limit: Maximum number of results to return
        
    Returns:
        List of search results with content and metadata
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{VECTOR_SERVICE_URL}/concepts/search",
                json={
                    "query": query,
                    "limit": limit,
                    "score_threshold": SIM_THRESHOLD
                }
            )
            response.raise_for_status()
            data = response.json()
            logger.info(f"Semantic search for '{query}' returned {len(data.get('results', []))} results")
            return data.get("results", [])
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []


@tool
async def session_history_tool(session_id: str, limit: int = 10) -> List[Dict[str, str]]:
    """Retrieve recent conversation history from the current session.
    
    Args:
        session_id: UUID of the conversation session
        limit: Maximum number of messages to return
        
    Returns:
        List of messages in format [{"role": "...", "content": "..."}, ...]
    """
    try:
        # Import here to avoid circular dependency
        from db.sessions import get_session_messages
        
        messages = await get_session_messages(session_id, limit)
        
        # Convert to simple format for the agent
        result = [
            {
                "role": msg["role"],
                "content": msg["content"]
            }
            for msg in messages
        ]
        
        logger.info(f"Retrieved {len(result)} messages from session {session_id}")
        return result
    except Exception as e:
        logger.error(f"Session history retrieval failed: {e}")
        return []


@tool
async def knowledge_graph_tool(concept: str, depth: int = 1) -> List[Dict[str, Any]]:
    """Find related concepts using the knowledge graph.
    
    Args:
        concept: The concept to find related nodes for
        depth: How many hops away to explore (default 1)
        
    Returns:
        List of related concepts with relationships
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{VECTOR_SERVICE_URL}/knowledge-graph",
                params={"concept": concept, "depth": depth}
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract related nodes
            nodes = data.get("nodes", [])
            related = [n for n in nodes if n.get("id") != concept]
            
            logger.info(f"Knowledge graph search for '{concept}' found {len(related)} related concepts")
            return related[:10]  # Limit to top 10 related concepts
    except Exception as e:
        logger.error(f"Knowledge graph query failed: {e}")
        return []


@tool
async def user_memories_tool(user_id: str, session_id: str = None, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieve user's stored memories and past Q&A sessions.
    
    Args:
        user_id: User ID from authentication
        session_id: Optional session ID to filter memories
        limit: Maximum number of memories to return
        
    Returns:
        List of user memories
    """
    try:
        # Import here to avoid circular dependency
        from db.sessions import get_pool
        
        pool = await get_pool()
        
        async with pool.acquire() as conn:
            if session_id:
                query = """
                    SELECT id, user_input, summary, created_at
                    FROM prompt_logs
                    WHERE user_id = $1 AND session_id = $2
                    ORDER BY created_at DESC
                    LIMIT $3
                """
                rows = await conn.fetch(query, user_id, session_id, limit)
            else:
                query = """
                    SELECT id, user_input, summary, created_at
                    FROM prompt_logs
                    WHERE user_id = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """
                rows = await conn.fetch(query, user_id, limit)
            
            memories = [
                {
                    "id": row["id"],
                    "query": row["user_input"],
                    "summary": row["summary"],
                    "created_at": row["created_at"].isoformat()
                }
                for row in rows
            ]
            
            logger.info(f"Retrieved {len(memories)} memories for user {user_id}")
            return memories
    except Exception as e:
        logger.error(f"User memories retrieval failed: {e}")
        return []


# Tool registry for easy access
RAG_TOOLS = [
    semantic_search_tool,
    session_history_tool,
    knowledge_graph_tool,
    user_memories_tool
]
