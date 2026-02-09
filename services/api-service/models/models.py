# second_brain/models/models.py
from __future__ import annotations
from datetime import datetime, date
from typing import Dict, Any

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Request body for /ask
# ------------------------------------------------------------------
class Prompt(BaseModel):
    user_input: str = Field(..., description="The question asked by the user")


# ------------------------------------------------------------------
# Standard response from /ask
# ------------------------------------------------------------------
class PromptResponse(BaseModel):
    id: int
    summary: str
    answers: Dict[str, Any]


# ------------------------------------------------------------------
# One row from the prompt_logs table
# Useful for internal admin routes or unit tests
# ------------------------------------------------------------------
class PromptLog(BaseModel):
    id: int
    user_input: str
    summary: str
    answers: Dict[str, Any]
    created_at: datetime

    class Config:
        orm_mode = True          # if you ever switch to SQLAlchemy


# ------------------------------------------------------------------
# Models for the daily summariser / Notion push tool
# ------------------------------------------------------------------
class DailySummaryRequest(BaseModel):
    day: date = Field(..., description="Calendar day to summarise (YYYY-MM-DD)")


class DailySummaryResponse(BaseModel):
    notion_page_url: str
    entries_count: int