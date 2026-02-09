"""
prompt_logs.py – helpers for the prompt_logs table.
Schema:

CREATE TABLE prompt_logs (
    id         SERIAL PRIMARY KEY,
    user_input TEXT      NOT NULL,
    answers    JSONB     NOT NULL,   -- all LLM answers as a single JSON object
    summary    TEXT      NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
"""
from __future__ import annotations
import json
from datetime import date, timedelta
from typing import Dict, List, Any
import asyncpg


from . import get_pool                               # relative import


# ────────────────────────────────────────────────────────────────────────────
# Insert one record
# ────────────────────────────────────────────────────────────────────────────
async def insert_record(
    user_input: str,
    answers: Dict[str, Any],
    summary: str,
    user_id: str = None,  # Optional user_id for multi-user support
    session_id: str = None,
) -> int:
    pool: asyncpg.Pool = await get_pool()
    # print(f'---insert_record, user_input:{user_input}')
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO prompt_logs (user_input, answers, summary, user_id, session_id)
            VALUES ($1, $2::jsonb, $3, $4, $5)
            RETURNING id
            """,
            user_input,
            json.dumps(answers),
            summary,
            user_id,
            session_id,
        )


# ────────────────────────────────────────────────────────────────────────────
# Fetch all rows for a given calendar day
# ────────────────────────────────────────────────────────────────────────────
async def fetch_by_date(day: date, user_id: str = None) -> List[asyncpg.Record]:
    """
    Return list[Record] where ts between <day 00:00> and <day+1 00:00).
    If user_id is provided, filter by that user.
    """
    start, end = day, day + timedelta(days=1)
    pool: asyncpg.Pool = await get_pool()
    async with pool.acquire() as conn:
        if user_id:
            return await conn.fetch(
                """
                SELECT id, user_input, answers, summary, created_at
                FROM   prompt_logs
                WHERE  created_at::date = $1::date 
                AND    user_id = $2
                ORDER  BY created_at
                """,
                day,
                user_id,
            )
        else:
            return await conn.fetch(
                """
                SELECT id, user_input, answers, summary, created_at
                FROM   prompt_logs
                WHERE  created_at::date = $1::date
                ORDER  BY created_at
                """,
                day,
            )
