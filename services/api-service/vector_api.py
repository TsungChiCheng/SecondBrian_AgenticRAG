"""
vector_api.py - API endpoints for vector database operations
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import ValidationError

from db.vector_db import get_vector_db
from models.vector_models import (
    VectorQueryRequest, 
    VectorSearchResponse,
    TopicQueryRequest,
    DateRangeQueryRequest, 
    KnowledgeStats
)

router = APIRouter(prefix="/vector", tags=["Vector Database"])

@router.post("/search", response_model=VectorSearchResponse)
async def search_knowledge(request: VectorQueryRequest):
    """Search for similar knowledge entries using vector similarity"""
    start_time = time.time()
    
    try:
        vector_db = get_vector_db()
        results = await vector_db.search_similar(
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convert results to dict format
        result_dicts = []
        for entry in results:
            result_dicts.append({
                "id": entry.id,
                "user_input": entry.user_input,
                "summary": entry.summary,
                "topics": entry.topics,
                "created_at": entry.created_at.isoformat(),
                "relevance_score": 0.85  # Placeholder - would be calculated from distance
            })
        
        execution_time = (time.time() - start_time) * 1000
        
        return VectorSearchResponse(
            query=request.query,
            results=result_dicts,
            total_found=len(results),
            execution_time_ms=round(execution_time, 2)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector search failed: {str(e)}"
        )


@router.get("/topics")
async def get_all_topics():
    """Get all available topics with their counts"""
    try:
        vector_db = get_vector_db()
        topics = await vector_db.get_all_topics()
        return {"topics": topics}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get topics: {str(e)}"
        )


@router.post("/by-topic")
async def get_by_topic(request: TopicQueryRequest):
    """Get knowledge entries by topic"""
    try:
        vector_db = get_vector_db()
        entries = await vector_db.get_by_topic(request.topic, request.limit)
        
        results = []
        for entry in entries:
            results.append({
                "id": entry.id,
                "user_input": entry.user_input,
                "summary": entry.summary,
                "topics": entry.topics,
                "created_at": entry.created_at.isoformat()
            })
        
        return {
            "topic": request.topic,
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Topic search failed: {str(e)}"
        )


@router.post("/by-date-range")
async def get_by_date_range(request: DateRangeQueryRequest):
    """Get knowledge entries within a date range"""
    try:
        vector_db = get_vector_db()
        entries = await vector_db.get_by_date_range(
            start_date=request.start_date,
            end_date=request.end_date,
            limit=request.limit
        )
        
        results = []
        for entry in entries:
            results.append({
                "id": entry.id,
                "user_input": entry.user_input,
                "summary": entry.summary,
                "topics": entry.topics,
                "created_at": entry.created_at.isoformat()
            })
        
        return {
            "start_date": request.start_date.isoformat(),
            "end_date": (request.end_date or request.start_date).isoformat(),
            "results": results,
            "total_found": len(results)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Date range search failed: {str(e)}"
        )


@router.get("/stats", response_model=KnowledgeStats)
async def get_knowledge_stats():
    """Get statistics about the knowledge base"""
    try:
        vector_db = get_vector_db()
        
        # Get basic stats
        collection_stats = await vector_db.get_collection_stats()
        
        # Get topics
        topics = await vector_db.get_all_topics()
        
        # Get recent entries count (last 7 days)
        seven_days_ago = date.today() - timedelta(days=7)
        recent_entries = await vector_db.get_by_date_range(seven_days_ago, date.today())
        
        return KnowledgeStats(
            total_entries=collection_stats.get("total_entries", 0),
            topics=topics,
            recent_entries_count=len(recent_entries),
            collection_info=collection_stats
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.delete("/entry/{entry_id}")
async def delete_entry(entry_id: str):
    """Delete a specific knowledge entry"""
    try:
        vector_db = get_vector_db()
        success = await vector_db.delete_entry(entry_id)
        
        if success:
            return {"message": f"Entry {entry_id} deleted successfully"}
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry {entry_id} not found"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete entry: {str(e)}"
        )


@router.get("/similar/{entry_id}")
async def get_similar_to_entry(entry_id: str, limit: int = Query(default=5, ge=1, le=20)):
    """Find entries similar to a specific entry"""
    try:
        vector_db = get_vector_db()
        
        # First get the entry to use as search query
        # This is a simplified approach - in practice you'd search by the entry's embedding
        collection = vector_db.get_collection()
        entry_result = collection.get(ids=[entry_id], include=["documents", "metadatas"])
        
        if not entry_result['ids'] or not entry_result['ids'][0]:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Entry {entry_id} not found"
            )
        
        # Use the document text as search query
        query_text = entry_result['documents'][0]
        
        # Search for similar entries
        similar_entries = await vector_db.search_similar(
            query=query_text,
            limit=limit + 1,  # +1 because original entry will be included
            similarity_threshold=0.5
        )
        
        # Remove the original entry from results
        filtered_entries = [entry for entry in similar_entries if entry.id != entry_id][:limit]
        
        results = []
        for entry in filtered_entries:
            results.append({
                "id": entry.id,
                "user_input": entry.user_input,
                "summary": entry.summary,
                "topics": entry.topics,
                "created_at": entry.created_at.isoformat()
            })
        
        return {
            "original_entry_id": entry_id,
            "similar_entries": results,
            "total_found": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar entries: {str(e)}"
        )


# Export the router
__all__ = ["router"]