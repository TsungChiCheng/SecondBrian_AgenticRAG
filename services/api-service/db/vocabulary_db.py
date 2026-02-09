"""
vocabulary_db.py – Database helpers for the vocabulary_memory table.
Schema:

CREATE TABLE vocabulary_memory (
    id              SERIAL PRIMARY KEY,
    user_id         VARCHAR(255) NOT NULL,
    word            VARCHAR(255) NOT NULL,
    pronunciation   TEXT,
    definition      TEXT NOT NULL,
    sample_sentence TEXT,
    related_words   TEXT[],  -- Array of related words
    language        VARCHAR(50) DEFAULT 'english',
    difficulty      VARCHAR(20),  -- beginner, intermediate, advanced
    tags            TEXT[],
    notes           TEXT,
    review_count    INTEGER DEFAULT 0,
    last_reviewed   TIMESTAMP,
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);
"""
from __future__ import annotations
import json
from datetime import date, datetime, timedelta
from typing import Dict, List, Any, Optional
import asyncpg

from . import get_pool  # relative import


# ────────────────────────────────────────────────────────────────────────────
# Insert one vocabulary entry
# ────────────────────────────────────────────────────────────────────────────
async def insert_vocabulary(
    user_id: str,
    word: str,
    pronunciation: Optional[str],
    definition: str,
    sample_sentence: Optional[str] = None,
    related_words: List[str] = None,
    language: str = "english",
    difficulty: Optional[str] = None,
    tags: List[str] = None,
    notes: Optional[str] = None,
) -> int:
    """Insert a new vocabulary entry"""
    pool: asyncpg.Pool = await get_pool()
    
    if related_words is None:
        related_words = []
    if tags is None:
        tags = []
    
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO vocabulary_memory (
                user_id, word, pronunciation, definition, 
                sample_sentence, related_words, language, 
                difficulty, tags, notes
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
            """,
            user_id,
            word,
            pronunciation,
            definition,
            sample_sentence,
            related_words,
            language,
            difficulty,
            tags,
            notes,
        )


# ────────────────────────────────────────────────────────────────────────────
# Get vocabulary by ID
# ────────────────────────────────────────────────────────────────────────────
async def get_vocabulary_by_id(vocab_id: int, user_id: str) -> Optional[asyncpg.Record]:
    """Get a specific vocabulary entry by ID"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(
            """
            SELECT * FROM vocabulary_memory
            WHERE id = $1 AND user_id = $2
            """,
            vocab_id,
            user_id,
        )


# ────────────────────────────────────────────────────────────────────────────
# Search vocabulary by word
# ────────────────────────────────────────────────────────────────────────────
async def search_vocabulary_by_word(
    word: str, 
    user_id: str,
    exact_match: bool = False
) -> List[asyncpg.Record]:
    """Search for vocabulary entries by word (exact or partial match)"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        if exact_match:
            return await conn.fetch(
                """
                SELECT * FROM vocabulary_memory
                WHERE LOWER(word) = LOWER($1) AND user_id = $2
                ORDER BY created_at DESC
                """,
                word,
                user_id,
            )
        else:
            return await conn.fetch(
                """
                SELECT * FROM vocabulary_memory
                WHERE LOWER(word) LIKE LOWER($1) AND user_id = $2
                ORDER BY created_at DESC
                """,
                f"%{word}%",
                user_id,
            )


# ────────────────────────────────────────────────────────────────────────────
# Get all vocabulary for a user
# ────────────────────────────────────────────────────────────────────────────
async def get_user_vocabulary(
    user_id: str,
    limit: int = 50,
    offset: int = 0,
    language: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[List[str]] = None,
) -> List[asyncpg.Record]:
    """Get all vocabulary entries for a user with optional filters"""
    pool: asyncpg.Pool = await get_pool()
    
    # Build dynamic query based on filters
    query = "SELECT * FROM vocabulary_memory WHERE user_id = $1"
    params = [user_id]
    param_count = 1
    
    if language:
        param_count += 1
        query += f" AND language = ${param_count}"
        params.append(language)
    
    if difficulty:
        param_count += 1
        query += f" AND difficulty = ${param_count}"
        params.append(difficulty)
    
    if tags:
        param_count += 1
        query += f" AND tags && ${param_count}"
        params.append(tags)
    
    query += " ORDER BY created_at DESC"
    
    param_count += 1
    query += f" LIMIT ${param_count}"
    params.append(limit)
    
    param_count += 1
    query += f" OFFSET ${param_count}"
    params.append(offset)
    
    async with pool.acquire() as conn:
        return await conn.fetch(query, *params)


# ────────────────────────────────────────────────────────────────────────────
# Update vocabulary entry
# ────────────────────────────────────────────────────────────────────────────
async def update_vocabulary(
    vocab_id: int,
    user_id: str,
    word: Optional[str] = None,
    pronunciation: Optional[str] = None,
    definition: Optional[str] = None,
    sample_sentence: Optional[str] = None,
    related_words: Optional[List[str]] = None,
    language: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[List[str]] = None,
    notes: Optional[str] = None,
) -> bool:
    """Update a vocabulary entry (only provided fields)"""
    pool: asyncpg.Pool = await get_pool()
    
    # Build dynamic update query
    update_fields = []
    params = [vocab_id, user_id]
    param_count = 2
    
    if word is not None:
        param_count += 1
        update_fields.append(f"word = ${param_count}")
        params.append(word)
    
    if pronunciation is not None:
        param_count += 1
        update_fields.append(f"pronunciation = ${param_count}")
        params.append(pronunciation)
    
    if definition is not None:
        param_count += 1
        update_fields.append(f"definition = ${param_count}")
        params.append(definition)
    
    if sample_sentence is not None:
        param_count += 1
        update_fields.append(f"sample_sentence = ${param_count}")
        params.append(sample_sentence)
    
    if related_words is not None:
        param_count += 1
        update_fields.append(f"related_words = ${param_count}")
        params.append(related_words)
    
    if language is not None:
        param_count += 1
        update_fields.append(f"language = ${param_count}")
        params.append(language)
    
    if difficulty is not None:
        param_count += 1
        update_fields.append(f"difficulty = ${param_count}")
        params.append(difficulty)
    
    if tags is not None:
        param_count += 1
        update_fields.append(f"tags = ${param_count}")
        params.append(tags)
    
    if notes is not None:
        param_count += 1
        update_fields.append(f"notes = ${param_count}")
        params.append(notes)
    
    if not update_fields:
        return False
    
    # Always update the updated_at timestamp
    update_fields.append("updated_at = NOW()")
    
    query = f"""
        UPDATE vocabulary_memory
        SET {', '.join(update_fields)}
        WHERE id = $1 AND user_id = $2
    """
    
    async with pool.acquire() as conn:
        result = await conn.execute(query, *params)
        return result == "UPDATE 1"


# ────────────────────────────────────────────────────────────────────────────
# Update review information
# ────────────────────────────────────────────────────────────────────────────
async def update_review_stats(vocab_id: int, user_id: str) -> bool:
    """Increment review count and update last reviewed timestamp"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE vocabulary_memory
            SET review_count = review_count + 1,
                last_reviewed = NOW()
            WHERE id = $1 AND user_id = $2
            """,
            vocab_id,
            user_id,
        )
        return result == "UPDATE 1"


# ────────────────────────────────────────────────────────────────────────────
# Delete vocabulary entry
# ────────────────────────────────────────────────────────────────────────────
async def delete_vocabulary(vocab_id: int, user_id: str) -> bool:
    """Delete a vocabulary entry"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM vocabulary_memory
            WHERE id = $1 AND user_id = $2
            """,
            vocab_id,
            user_id,
        )
        return result == "DELETE 1"


# ────────────────────────────────────────────────────────────────────────────
# Get vocabulary statistics
# ────────────────────────────────────────────────────────────────────────────
async def get_vocabulary_stats(user_id: str) -> Dict[str, Any]:
    """Get statistics about user's vocabulary"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM vocabulary_memory WHERE user_id = $1",
            user_id
        )
        
        by_language = await conn.fetch(
            """
            SELECT language, COUNT(*) as count
            FROM vocabulary_memory
            WHERE user_id = $1
            GROUP BY language
            """,
            user_id
        )
        
        by_difficulty = await conn.fetch(
            """
            SELECT difficulty, COUNT(*) as count
            FROM vocabulary_memory
            WHERE user_id = $1 AND difficulty IS NOT NULL
            GROUP BY difficulty
            """,
            user_id
        )
        
        recent_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM vocabulary_memory
            WHERE user_id = $1 AND created_at >= NOW() - INTERVAL '7 days'
            """,
            user_id
        )
        
        reviewed_count = await conn.fetchval(
            """
            SELECT COUNT(*) FROM vocabulary_memory
            WHERE user_id = $1 AND review_count > 0
            """,
            user_id
        )
        
        return {
            "total_words": total,
            "by_language": [dict(row) for row in by_language],
            "by_difficulty": [dict(row) for row in by_difficulty],
            "recent_additions": recent_count,
            "reviewed_words": reviewed_count,
        }


# ────────────────────────────────────────────────────────────────────────────
# Get words due for review (spaced repetition)
# ────────────────────────────────────────────────────────────────────────────
async def get_words_for_review(
    user_id: str,
    limit: int = 10
) -> List[asyncpg.Record]:
    """Get words that are due for review based on spaced repetition"""
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        # Simple spaced repetition: prioritize words that haven't been reviewed
        # or haven't been reviewed in a while
        return await conn.fetch(
            """
            SELECT * FROM vocabulary_memory
            WHERE user_id = $1
            ORDER BY 
                CASE 
                    WHEN last_reviewed IS NULL THEN 0
                    ELSE EXTRACT(EPOCH FROM (NOW() - last_reviewed))
                END DESC,
                review_count ASC
            LIMIT $2
            """,
            user_id,
            limit
        )
