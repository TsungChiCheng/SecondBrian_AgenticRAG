from __future__ import annotations
from datetime import date
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel

from tools.summarizer import QAEntry, TopicSummary, _summarise   # reuse logic
from db.prompt_logs import fetch_by_date
from tools.notion_push import push_daily_summary

# Import authentication
from auth import User, get_current_user

router = APIRouter()

# ───────────────────────── models ─────────────────────────
class CombinedRequest(BaseModel):
    day: date

class CombinedResponse(BaseModel):
    inserted: int
    topics: List[TopicSummary]

# ───────────────────────── endpoint ──────────────────────
router = APIRouter(prefix="/tools")
@router.post("/daily_summarize_and_push", response_model=CombinedResponse)
async def daily_summarize_and_push(
    req: CombinedRequest,
    user: User = Depends(get_current_user)  # ← Add authentication
):
    # 1) fetch logs for this user only
    rows = await fetch_by_date(req.day, user_id=user.id)  # ← Filter by user_id
    if not rows:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No prompt logs found for {req.day}"
        )

    entries = [QAEntry(question=r["user_input"], answer=r["answers"])
               for r in rows]

    # 2) summarise → list[TopicSummary]
    topics: List[TopicSummary] = _summarise(req.day, entries)

    # 3) push to Notion
    inserted = await push_daily_summary(req.day, topics)

    return CombinedResponse(inserted=inserted, topics=topics)