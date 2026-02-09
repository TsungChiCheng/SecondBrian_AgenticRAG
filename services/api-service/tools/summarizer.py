# tools/summarizer.py
from __future__ import annotations
import json
import logging
from datetime import date
from typing import List, Dict, Any, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field, ValidationError
from langchain_openai import ChatOpenAI

from db.prompt_logs import fetch_by_date
from config.config import settings

# Import authentication
from auth import User, get_current_user

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tools")

# ─────────────────────────────────────────────────────────────
# Response / Request Models
# ─────────────────────────────────────────────────────────────
class TopicSummary(BaseModel):
    topic: str
    knowledge_point: str

class QAEntry(BaseModel):
    question: str
    answer:   str

class DailySummaryRequest(BaseModel):
    day: date
    entries: List[QAEntry] | None = None   # if None → auto-fetch from DB

class DailySummaryResponse(BaseModel):
    items: List[TopicSummary]
    entries_count: int

# ─────────────────────────────────────────────────────────────
# LLM prompt
# ─────────────────────────────────────────────────────────────
# For daily summarizer, respect OPENAI_MODEL from environment.
# GPT-4 class models use max_tokens; GPT-5/o1/o3 use max_completion_tokens.
_model = settings.OPENAI_MODEL
_is_new_model = _model.startswith("gpt-5") or _model.startswith("o1") or _model.startswith("o3")

_llm_kwargs = {
    "model": _model,
    "api_key": settings.OPENAI_API_KEY,
}
if _is_new_model:
    _llm_kwargs["max_completion_tokens"] = 2000
else:
    _llm_kwargs["max_tokens"] = 2000
    _llm_kwargs["temperature"] = 0.3

_LLM = ChatOpenAI(**_llm_kwargs)

_PROMPT = """
You are a knowledge-management assistant.

**Goal**  
Return a concise JSON array.  
Each element must be an object with exactly two keys:

    \"topic\"           – a short title that groups related questions
    \"knowledge_point\" – 1-3 sentences summarising the key insight(s)

**Rules**  
• Output *only* valid JSON – no Markdown, no preamble.  
• Each question should appear under one topic.
• Classify all toipcs.
• Summarize the the knowledge which are in same topic class.
• Each topic should not be similar with others.

JSON schema example:

[
  {{\"topic\": \"Networking\", \"knowledge_point\": \"SSH works but port 3000 fails because...\"}},
  {{\"topic\": \"Database\",  \"knowledge_point\": \"asyncpg expects json.dumps(...) for JSONB columns.\"}}
]

---

Date: {day}

Q&A list:
{joined}
"""

def _summarise(day: date, entries: List[QAEntry]) -> List[TopicSummary]:
    if not entries:
        return []

    joined = "\n\n".join(
        f"Q: {e.question}\nA: {e.answer}" for e in entries
    )
    raw = _LLM.invoke(
        _PROMPT.format(day=day.isoformat(), joined=joined)
    ).content.strip()

    # Parse JSON from the model
    try:
        data = json.loads(raw)
        return [TopicSummary(**item) for item in data]
    except (json.JSONDecodeError, ValidationError) as e:
        # Surface a clear error for client / logs
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"LLM did not return valid JSON: {e}"
        )


# ─────────────────────────────────────────────────────────────
# FastAPI endpoint
# ─────────────────────────────────────────────────────────────
@router.post("/daily_summarizer", response_model=DailySummaryResponse)
async def daily_summarizer(
    req: DailySummaryRequest,
    user: User = Depends(get_current_user)  # ← Add authentication
):
    # Auto-load from DB if caller didn't supply entries
    print(f"📅 Daily summary requested by user {user.name} ({user.email}, ID: {user.id[:8]}...) for date: {req.day}")
    if req.entries is None:
        rows = await fetch_by_date(req.day, user_id=user.id)  # ← Filter by user_id
        # print(f'---daily_summarizer, rows: {rows}')
        if not rows:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail=f"No prompt logs found for {req.day}"
            )
        req.entries = [
            QAEntry(question=r["user_input"], answer=r["answers"])
            for r in rows
        ]

    items = _summarise(req.day, req.entries)
    return DailySummaryResponse(items=items, entries_count=len(req.entries))
