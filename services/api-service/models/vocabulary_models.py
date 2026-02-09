"""
vocabulary_models.py - Pydantic models for vocabulary memory feature
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field


# ─────────────────────────────────────────────────────────────────────────────
# Request Models
# ─────────────────────────────────────────────────────────────────────────────

class VocabularyCreateRequest(BaseModel):
    """Request to create a new vocabulary entry"""
    word: str = Field(..., description="The vocabulary word", min_length=1, max_length=255)
    pronunciation: Optional[str] = Field(None, description="Phonetic pronunciation (IPA or simple)")
    definition: str = Field(..., description="Definition of the word", min_length=1)
    sample_sentence: Optional[str] = Field(None, description="Example sentence using the word")
    related_words: Optional[List[str]] = Field(default=[], description="List of related or similar words")
    language: str = Field(default="english", description="Language of the word")
    difficulty: Optional[str] = Field(None, description="Difficulty level: beginner, intermediate, advanced")
    tags: Optional[List[str]] = Field(default=[], description="Custom tags for categorization")
    notes: Optional[str] = Field(None, description="Additional notes or context")


class VocabularyUpdateRequest(BaseModel):
    """Request to update an existing vocabulary entry"""
    word: Optional[str] = Field(None, description="The vocabulary word", max_length=255)
    pronunciation: Optional[str] = Field(None, description="Phonetic pronunciation")
    definition: Optional[str] = Field(None, description="Definition of the word")
    sample_sentence: Optional[str] = Field(None, description="Example sentence")
    related_words: Optional[List[str]] = Field(None, description="List of related words")
    language: Optional[str] = Field(None, description="Language of the word")
    difficulty: Optional[str] = Field(None, description="Difficulty level")
    tags: Optional[List[str]] = Field(None, description="Custom tags")
    notes: Optional[str] = Field(None, description="Additional notes")


class VocabularySearchRequest(BaseModel):
    """Request to search vocabulary"""
    query: str = Field(..., description="Search query (word or semantic search)", min_length=1)
    exact_match: bool = Field(default=False, description="Whether to search for exact word match")
    language: Optional[str] = Field(None, description="Filter by language")
    difficulty: Optional[str] = Field(None, description="Filter by difficulty")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    use_semantic_search: bool = Field(default=True, description="Use vector search for semantic matching")


class VocabularyListRequest(BaseModel):
    """Request to list vocabulary with filters"""
    language: Optional[str] = Field(None, description="Filter by language")
    difficulty: Optional[str] = Field(None, description="Filter by difficulty level")
    tags: Optional[List[str]] = Field(None, description="Filter by tags")
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class VocabularyReviewRequest(BaseModel):
    """Request to get words for review"""
    limit: int = Field(default=10, ge=1, le=50, description="Number of words to review")


# ─────────────────────────────────────────────────────────────────────────────
# Response Models
# ─────────────────────────────────────────────────────────────────────────────

class VocabularyEntry(BaseModel):
    """Complete vocabulary entry"""
    id: int
    user_id: str
    word: str
    pronunciation: Optional[str]
    definition: str
    sample_sentence: Optional[str]
    related_words: List[str]
    language: str
    difficulty: Optional[str]
    tags: List[str]
    notes: Optional[str]
    review_count: int
    last_reviewed: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class VocabularyResponse(BaseModel):
    """Response containing a single vocabulary entry"""
    success: bool
    data: Optional[VocabularyEntry]
    message: Optional[str] = None


class VocabularyListResponse(BaseModel):
    """Response containing a list of vocabulary entries"""
    success: bool
    data: List[VocabularyEntry]
    total: int
    limit: int
    offset: int
    message: Optional[str] = None


class VocabularySearchResult(BaseModel):
    """Search result with relevance score"""
    entry: VocabularyEntry
    relevance_score: float = Field(description="Relevance score (0-1)")


class VocabularySearchResponse(BaseModel):
    """Response for vocabulary search"""
    success: bool
    query: str
    results: List[VocabularySearchResult]
    total_found: int
    message: Optional[str] = None


class VocabularyStatsResponse(BaseModel):
    """Statistics about user's vocabulary"""
    total_words: int
    by_language: List[dict]
    by_difficulty: List[dict]
    recent_additions: int
    reviewed_words: int
    message: Optional[str] = None


class VocabularyCreateResponse(BaseModel):
    """Response after creating a vocabulary entry"""
    success: bool
    vocab_id: int
    message: str


class VocabularyDeleteResponse(BaseModel):
    """Response after deleting a vocabulary entry"""
    success: bool
    message: str


class RelatedWordEntry(BaseModel):
    """Related word entry with similarity score"""
    entry: VocabularyEntry
    distance: float = Field(description="Semantic distance/similarity score (0-1, lower is more similar)")


class VocabularyRelatedWordsResponse(BaseModel):
    """Response containing related words with similarity scores"""
    success: bool
    word: str
    related_words: List[RelatedWordEntry]
    message: Optional[str] = None
