"""
Session management for LangGraph conversation state persistence
"""
import os
import json
import asyncpg
from typing import Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Database connection pool
_pool: Optional[asyncpg.Pool] = None


async def get_pool() -> asyncpg.Pool:
    """Get or create database connection pool"""
    global _pool
    if _pool is None:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            # Construct from individual env vars
            db_host = os.getenv("POSTGRES_HOST", "db")
            db_port = os.getenv("POSTGRES_PORT", "5432")
            db_user = os.getenv("POSTGRES_USER", "secondbrain")
            db_pass = os.getenv("POSTGRES_PASSWORD", "secondbrain_password")
            db_name = os.getenv("POSTGRES_DB", "secondbrain")
            database_url = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
        
        _pool = await asyncpg.create_pool(database_url, min_size=2, max_size=10)
        logger.info("Database connection pool created")
    
    return _pool


async def create_session(user_id: str, title: str = None, metadata: dict = None) -> str:
    """Create a new conversation session
    
    Args:
        user_id: User ID from authentication
        title: Optional session title
        metadata: Optional metadata dictionary
        
    Returns:
        session_id: UUID string
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversation_sessions (user_id, title, metadata)
            VALUES ($1, $2, $3::jsonb)
            RETURNING id
            """,
            user_id,
            title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            json.dumps(metadata or {})
        )
        session_id = str(row['id'])
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id


async def get_session(session_id: str) -> Optional[Dict]:
    """Get session metadata
    
    Args:
        session_id: UUID string
        
    Returns:
        Session dict or None if not found
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, user_id, title, created_at, updated_at, metadata, is_active
            FROM conversation_sessions
            WHERE id = $1
            """,
            session_id
        )
        
        if not row:
            return None
        
        return {
            "id": str(row['id']),
            "user_id": row['user_id'],
            "title": row['title'],
            "created_at": row['created_at'].isoformat(),
            "updated_at": row['updated_at'].isoformat(),
            "metadata": row['metadata'],
            "is_active": row['is_active']
        }


async def list_user_sessions(user_id: str, limit: int = 50, include_inactive: bool = False) -> List[Dict]:
    """List all sessions for a user
    
    Args:
        user_id: User ID from authentication
        limit: Maximum number of sessions to return
        include_inactive: Whether to include inactive sessions
        
    Returns:
        List of session dicts
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        if include_inactive:
            query = """
                SELECT id, user_id, title, created_at, updated_at, metadata, is_active,
                       (SELECT COUNT(*) FROM conversation_messages WHERE session_id = conversation_sessions.id) as message_count
                FROM conversation_sessions
                WHERE user_id = $1
                ORDER BY updated_at DESC
                LIMIT $2
            """
        else:
            query = """
                SELECT id, user_id, title, created_at, updated_at, metadata, is_active,
                       (SELECT COUNT(*) FROM conversation_messages WHERE session_id = conversation_sessions.id) as message_count
                FROM conversation_sessions
                WHERE user_id = $1 AND is_active = true
                ORDER BY updated_at DESC
                LIMIT $2
            """
        
        rows = await conn.fetch(query, user_id, limit)
        
        return [
            {
                "id": str(row['id']),
                "user_id": row['user_id'],
                "title": row['title'],
                "created_at": row['created_at'].isoformat(),
                "updated_at": row['updated_at'].isoformat(),
                "metadata": row['metadata'],
                "is_active": row['is_active'],
                "message_count": row['message_count']
            }
            for row in rows
        ]


async def add_message(session_id: str, role: str, content: str, metadata: dict = None) -> str:
    """Add a message to a conversation session
    
    Args:
        session_id: UUID string
        role: Message role (user, assistant, system, tool)
        content: Message content
        metadata: Optional metadata (model info, tool calls, etc.)
        
    Returns:
        message_id: UUID string
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO conversation_messages (session_id, role, content, metadata)
            VALUES ($1, $2, $3, $4::jsonb)
            RETURNING id
            """,
            session_id,
            role,
            content,
            json.dumps(metadata or {})
        )
        message_id = str(row['id'])
        logger.debug(f"Added {role} message to session {session_id}")
        return message_id


async def deactivate_session(session_id: str) -> bool:
    """Mark a session as inactive"""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE conversation_sessions
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            session_id
        )
        return result[-1] != "0"  # check rows affected


async def get_session_messages(session_id: str, limit: int = 100) -> List[Dict]:
    """Retrieve conversation history for a session
    
    Args:
        session_id: UUID string
        limit: Maximum number of messages to return (most recent)
        
    Returns:
        List of message dicts in chronological order
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, session_id, role, content, metadata, created_at
            FROM conversation_messages
            WHERE session_id = $1
            ORDER BY created_at ASC
            LIMIT $2
            """,
            session_id,
            limit
        )
        
        return [
            {
                "id": str(row['id']),
                "session_id": str(row['session_id']),
                "role": row['role'],
                "content": row['content'],
                "metadata": row['metadata'],
                "created_at": row['created_at'].isoformat()
            }
            for row in rows
        ]


async def delete_session(session_id: str) -> bool:
    """Delete a conversation session and all its messages
    
    Args:
        session_id: UUID string
        
    Returns:
        True if deleted, False if not found
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM conversation_sessions
            WHERE id = $1
            """,
            session_id
        )
        # Result format: "DELETE N" where N is number of rows deleted
        deleted = result.split()[-1] == "1"
        if deleted:
            logger.info(f"Deleted session {session_id}")
        return deleted


async def update_session_title(session_id: str, title: str) -> bool:
    """Update session title
    
    Args:
        session_id: UUID string
        title: New title
        
    Returns:
        True if updated, False if not found
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE conversation_sessions
            SET title = $1, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            """,
            title,
            session_id
        )
        updated = result.split()[-1] == "1"
        return updated


async def deactivate_session(session_id: str) -> bool:
    """Mark a session as inactive (soft delete)
    
    Args:
        session_id: UUID string
        
    Returns:
        True if updated, False if not found
    """
    pool = await get_pool()
    
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE conversation_sessions
            SET is_active = false, updated_at = CURRENT_TIMESTAMP
            WHERE id = $2
            """,
            session_id
        )
        updated = result.split()[-1] == "1"
        return updated
