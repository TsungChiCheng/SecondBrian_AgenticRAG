# tools/notion_push.py
"""
Push daily topic-summaries into a Notion database.

  from tools.notion_push import push_daily_summary
  await push_daily_summary(day, items)

Mounted endpoint:
  POST /tools/notion_push
  {
    "day": "YYYY-MM-DD",
    "items": [
      {"topic": "...", "knowledge_point": "..."},
      ...
    ]
  }
"""

from __future__ import annotations
import os, logging, anyio
from datetime import date
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from notion_client import Client, APIResponseError

# ───────────────────────────
# ENV  &  Notion client
# ───────────────────────────
NOTION_TOKEN   = os.getenv("NOTION_TOKEN")
DATABASE_ID    = os.getenv("DATABASE_ID")                 # must be a DB ID
DATE_COLUMN    = os.getenv("NOTION_DATE_COL", "Date")     # optional date prop

notion: Client | None = Client(auth=NOTION_TOKEN) if NOTION_TOKEN else None
router = APIRouter(prefix="/tools")
log = logging.getLogger(__name__)

# ───────────────────────────
# Pydantic models
# ───────────────────────────
class TopicSummary(BaseModel):
    topic: str
    knowledge_point: str

class PushRequest(BaseModel):
    day: date
    items: List[TopicSummary]

class PushResponse(BaseModel):
    inserted: int

# ───────────────────────────
# Schema caches & helpers
# ───────────────────────────
_title_col_cache: str | None = None
_rich_text_col_cache: str | None = None
_db_properties_cache: set[str] | None = None


async def _get_schema():
    """Retrieve and cache the full DB schema."""
    global _db_properties_cache, _title_col_cache, _rich_text_col_cache

    if _db_properties_cache is not None:
        return  # already cached

    db = await anyio.to_thread.run_sync(lambda: notion.databases.retrieve(DATABASE_ID))
    _db_properties_cache = set(db["properties"].keys())

    for name, prop in db["properties"].items():
        if prop["type"] == "title" and _title_col_cache is None:
            _title_col_cache = name
        if prop["type"] == "rich_text" and _rich_text_col_cache is None:
            _rich_text_col_cache = name

    if _title_col_cache is None:
        raise RuntimeError("No Title column found in the Notion database.")
    if _rich_text_col_cache is None:
        raise RuntimeError("No Rich-Text column found in the Notion database.")


async def _insert_row(day: date, item: TopicSummary) -> bool:
    """Insert a single row (topic) into the Notion DB."""
    await _get_schema()  # ensure caches are populated

    def _create():
        props = {
            _title_col_cache: {  # type: ignore[arg-type]
                "title": [{"text": {"content": item.topic}}],
            },
            _rich_text_col_cache: {  # type: ignore[arg-type]
                "rich_text": [
                    {
                        "text": {
                            "content": f"{item.knowledge_point}"
                        }
                    }
                ],
            },
        }

        # Optional date property
        if DATE_COLUMN in _db_properties_cache:
            props[DATE_COLUMN] = {"date": {"start": day.isoformat()}}

        return notion.pages.create(parent={"database_id": DATABASE_ID},
                                   properties=props)

    try:
        await anyio.to_thread.run_sync(_create)
        return True
    except APIResponseError as e:
        log.error("Notion insert failed for topic '%s': %s", item.topic, e)
        return False

# ───────────────────────────
# Public helper
# ───────────────────────────
async def push_daily_summary(day: date, items: List[TopicSummary]) -> int:
    """Push all topics for *day* into Notion; return number inserted."""
    if notion is None or DATABASE_ID is None:
        raise RuntimeError("Notion integration not configured (token / DB ID)")

    successes = 0
    for item in items:
        if await _insert_row(day, item):
            successes += 1
    return successes

# ───────────────────────────
# FastAPI endpoint
# ───────────────────────────
@router.post("/notion_push", response_model=PushResponse)
async def notion_push(req: PushRequest):
    inserted = await push_daily_summary(req.day, req.items)
    if inserted == 0:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Notion insert failed for every item."
        )
    return PushResponse(inserted=inserted)