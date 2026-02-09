"""
vector_models.py - Pydantic models for vector database operations
"""
from __future__ import annotations
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class VectorQueryRequest(BaseModel):
    query: str = Field(..., description="Search query text")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Minimum similarity score")


class VectorSearchResponse(BaseModel):
    query: str
    results: List[Dict[str, Any]]
    total_found: int
    execution_time_ms: float


class TopicQueryRequest(BaseModel):
    topic: str = Field(..., description="Topic to search for")
    limit: int = Field(default=20, ge=1, le=100)


class DateRangeQueryRequest(BaseModel):
    start_date: date = Field(..., description="Start date for search")
    end_date: Optional[date] = Field(None, description="End date for search (defaults to start_date)")
    limit: int = Field(default=50, ge=1, le=200)


class KnowledgeStats(BaseModel):
    total_entries: int
    topics: List[Dict[str, Any]]
    recent_entries_count: int
    collection_info: Dict[str, Any]


class EnhancedPromptResponse(BaseModel):
    """Enhanced response that includes related knowledge"""
    id: str
    summary: str
    answers: Dict[str, Any]
    related_knowledge: List[Dict[str, Any]] = []
    suggested_topics: List[str] = []