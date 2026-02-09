"""
vocabulary_routes.py - API routes for vocabulary memory feature
Manages CRUD operations and search for vocabulary entries
"""
from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, status
import os

from models.vocabulary_models import (
    VocabularyCreateRequest,
    VocabularyUpdateRequest,
    VocabularySearchRequest,
    VocabularyListRequest,
    VocabularyReviewRequest,
    VocabularyEntry,
    VocabularyResponse,
    VocabularyListResponse,
    VocabularySearchResponse,
    VocabularySearchResult,
    VocabularyStatsResponse,
    VocabularyCreateResponse,
    VocabularyDeleteResponse,
    VocabularyRelatedWordsResponse,
)
from db.vocabulary_db import (
    insert_vocabulary,
    get_vocabulary_by_id,
    search_vocabulary_by_word,
    get_user_vocabulary,
    update_vocabulary,
    update_review_stats,
    delete_vocabulary,
    get_vocabulary_stats,
    get_words_for_review,
)
from db.vocabulary_vector_db import get_vocabulary_vector_db
from auth import User, get_current_user
from config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vocabulary", tags=["Vocabulary Memory"])


def _record_to_entry(record) -> VocabularyEntry:
    """Convert database record to VocabularyEntry model"""
    return VocabularyEntry(
        id=record["id"],
        user_id=record["user_id"],
        word=record["word"],
        pronunciation=record["pronunciation"],
        definition=record["definition"],
        sample_sentence=record["sample_sentence"],
        related_words=list(record["related_words"]) if record["related_words"] else [],
        language=record["language"],
        difficulty=record["difficulty"],
        tags=list(record["tags"]) if record["tags"] else [],
        notes=record["notes"],
        review_count=record["review_count"],
        last_reviewed=record["last_reviewed"],
        created_at=record["created_at"],
        updated_at=record["updated_at"],
    )


@router.post("/add", response_model=VocabularyCreateResponse)
async def add_vocabulary(
    request: VocabularyCreateRequest,
    user: User = Depends(get_current_user)
):
    """Add a new vocabulary word to memory"""
    try:
        logger.info(f"Adding vocabulary '{request.word}' for user {user.email}")
        
        # Insert into PostgreSQL
        vocab_id = await insert_vocabulary(
            user_id=user.id,
            word=request.word,
            pronunciation=request.pronunciation,
            definition=request.definition,
            sample_sentence=request.sample_sentence,
            related_words=request.related_words,
            language=request.language,
            difficulty=request.difficulty,
            tags=request.tags,
            notes=request.notes,
        )
        
        # Add to vector database for semantic search
        vector_db = get_vocabulary_vector_db()
        await vector_db.add_vocabulary(
            vocab_id=vocab_id,
            user_id=user.id,
            word=request.word,
            definition=request.definition,
            pronunciation=request.pronunciation,
            sample_sentence=request.sample_sentence,
            related_words=request.related_words,
            language=request.language,
            difficulty=request.difficulty,
            tags=request.tags,
        )
        
        logger.info(f"✅ Successfully added vocabulary: {request.word} (ID: {vocab_id})")
        
        return VocabularyCreateResponse(
            success=True,
            vocab_id=vocab_id,
            message=f"Successfully added '{request.word}' to your vocabulary"
        )
        
    except Exception as e:
        logger.error(f"Error adding vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add vocabulary: {str(e)}"
        )


@router.get("/{vocab_id}", response_model=VocabularyResponse)
async def get_vocabulary(
    vocab_id: int,
    user: User = Depends(get_current_user)
):
    """Get a specific vocabulary entry by ID"""
    try:
        record = await get_vocabulary_by_id(vocab_id, user.id)
        
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vocabulary entry {vocab_id} not found"
            )
        
        entry = _record_to_entry(record)
        
        return VocabularyResponse(
            success=True,
            data=entry
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get vocabulary: {str(e)}"
        )


@router.post("/search", response_model=VocabularySearchResponse)
async def search_vocabulary(
    request: VocabularySearchRequest,
    user: User = Depends(get_current_user)
):
    """Search vocabulary entries"""
    try:
        logger.info(f"Searching vocabulary: '{request.query}' for user {user.email}")
        
        results = []
        
        if request.use_semantic_search:
            # Use vector search for semantic matching
            vector_db = get_vocabulary_vector_db()
            vector_results = await vector_db.search_vocabulary(
                query=request.query,
                user_id=user.id,
                limit=request.limit,
                language=request.language,
                difficulty=request.difficulty,
            )
            
            # Convert vector results to VocabularySearchResult
            for result in vector_results:
                # Get full entry from database
                vocab_id = result["metadata"]["vocab_id"]
                record = await get_vocabulary_by_id(vocab_id, user.id)
                
                if record:
                    entry = _record_to_entry(record)
                    results.append(VocabularySearchResult(
                        entry=entry,
                        relevance_score=result.get("score", 0.5)
                    ))
        else:
            # Use direct word search
            records = await search_vocabulary_by_word(
                word=request.query,
                user_id=user.id,
                exact_match=request.exact_match
            )
            
            for record in records[:request.limit]:
                entry = _record_to_entry(record)
                results.append(VocabularySearchResult(
                    entry=entry,
                    relevance_score=1.0 if request.exact_match else 0.8
                ))
        
        logger.info(f"Found {len(results)} vocabulary matches")
        
        return VocabularySearchResponse(
            success=True,
            query=request.query,
            results=results,
            total_found=len(results)
        )
        
    except Exception as e:
        logger.error(f"Error searching vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )


@router.post("/list", response_model=VocabularyListResponse)
async def list_vocabulary(
    request: VocabularyListRequest,
    user: User = Depends(get_current_user)
):
    """List vocabulary entries with optional filters"""
    try:
        records = await get_user_vocabulary(
            user_id=user.id,
            limit=request.limit,
            offset=request.offset,
            language=request.language,
            difficulty=request.difficulty,
            tags=request.tags,
        )
        
        entries = [_record_to_entry(record) for record in records]
        
        # Get total count (simplified - could be optimized)
        all_records = await get_user_vocabulary(
            user_id=user.id,
            limit=10000,  # Large number to get all
            language=request.language,
            difficulty=request.difficulty,
            tags=request.tags,
        )
        total = len(all_records)
        
        return VocabularyListResponse(
            success=True,
            data=entries,
            total=total,
            limit=request.limit,
            offset=request.offset
        )
        
    except Exception as e:
        logger.error(f"Error listing vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list vocabulary: {str(e)}"
        )


@router.put("/{vocab_id}", response_model=VocabularyResponse)
async def update_vocabulary_entry(
    vocab_id: int,
    request: VocabularyUpdateRequest,
    user: User = Depends(get_current_user)
):
    """Update a vocabulary entry"""
    try:
        # Check if entry exists
        existing = await get_vocabulary_by_id(vocab_id, user.id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vocabulary entry {vocab_id} not found"
            )
        
        # Update in PostgreSQL
        success = await update_vocabulary(
            vocab_id=vocab_id,
            user_id=user.id,
            word=request.word,
            pronunciation=request.pronunciation,
            definition=request.definition,
            sample_sentence=request.sample_sentence,
            related_words=request.related_words,
            language=request.language,
            difficulty=request.difficulty,
            tags=request.tags,
            notes=request.notes,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update vocabulary"
            )
        
        # Update in vector database
        updated_record = await get_vocabulary_by_id(vocab_id, user.id)
        if updated_record:
            vector_db = get_vocabulary_vector_db()
            await vector_db.update_vocabulary(
                vocab_id=vocab_id,
                user_id=user.id,
                word=updated_record["word"],
                definition=updated_record["definition"],
                pronunciation=updated_record["pronunciation"],
                sample_sentence=updated_record["sample_sentence"],
                related_words=list(updated_record["related_words"]) if updated_record["related_words"] else [],
                language=updated_record["language"],
                difficulty=updated_record["difficulty"],
                tags=list(updated_record["tags"]) if updated_record["tags"] else [],
            )
        
        entry = _record_to_entry(updated_record)
        
        logger.info(f"✅ Updated vocabulary: {entry.word} (ID: {vocab_id})")
        
        return VocabularyResponse(
            success=True,
            data=entry,
            message="Vocabulary updated successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update vocabulary: {str(e)}"
        )


@router.delete("/{vocab_id}", response_model=VocabularyDeleteResponse)
async def delete_vocabulary_entry(
    vocab_id: int,
    user: User = Depends(get_current_user)
):
    """Delete a vocabulary entry"""
    try:
        # Check if exists
        existing = await get_vocabulary_by_id(vocab_id, user.id)
        if not existing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vocabulary entry {vocab_id} not found"
            )
        
        # Delete from PostgreSQL
        success = await delete_vocabulary(vocab_id, user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete vocabulary"
            )
        
        # Delete from vector database
        vector_db = get_vocabulary_vector_db()
        await vector_db.delete_vocabulary(vocab_id, user.id)
        
        logger.info(f"✅ Deleted vocabulary: {existing['word']} (ID: {vocab_id})")
        
        return VocabularyDeleteResponse(
            success=True,
            message=f"Successfully deleted '{existing['word']}'"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete vocabulary: {str(e)}"
        )


@router.post("/{vocab_id}/review")
async def mark_as_reviewed(
    vocab_id: int,
    user: User = Depends(get_current_user)
):
    """Mark a vocabulary word as reviewed (updates review count and timestamp)"""
    try:
        success = await update_review_stats(vocab_id, user.id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vocabulary entry {vocab_id} not found"
            )
        
        return {
            "success": True,
            "message": "Review recorded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recording review: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record review: {str(e)}"
        )


@router.post("/review/due", response_model=VocabularyListResponse)
async def get_review_words(
    request: VocabularyReviewRequest,
    user: User = Depends(get_current_user)
):
    """Get vocabulary words due for review (spaced repetition)"""
    try:
        records = await get_words_for_review(user.id, request.limit)
        entries = [_record_to_entry(record) for record in records]
        
        return VocabularyListResponse(
            success=True,
            data=entries,
            total=len(entries),
            limit=request.limit,
            offset=0,
            message=f"Here are {len(entries)} words to review"
        )
        
    except Exception as e:
        logger.error(f"Error getting review words: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get review words: {str(e)}"
        )


@router.get("/stats/summary", response_model=VocabularyStatsResponse)
async def get_stats(user: User = Depends(get_current_user)):
    """Get statistics about user's vocabulary"""
    try:
        stats = await get_vocabulary_stats(user.id)
        
        return VocabularyStatsResponse(
            total_words=stats["total_words"],
            by_language=stats["by_language"],
            by_difficulty=stats["by_difficulty"],
            recent_additions=stats["recent_additions"],
            reviewed_words=stats["reviewed_words"],
        )
        
    except Exception as e:
        logger.error(f"Error getting vocabulary stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/{vocab_id}/related", response_model=VocabularyRelatedWordsResponse)
async def get_related_words(
    vocab_id: int,
    limit: int = 5,
    user: User = Depends(get_current_user)
):
    """Get vocabulary entries related to a specific word with similarity scores"""
    try:
        # Get the original word
        record = await get_vocabulary_by_id(vocab_id, user.id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Vocabulary entry {vocab_id} not found"
            )
        
        word = record["word"]
        
        # Find related words using vector search
        vector_db = get_vocabulary_vector_db()
        vector_results = await vector_db.find_related_words(word, user.id, limit=limit + 1)  # +1 to account for the original word
        
        # Convert to entries with distance scores
        from models.vocabulary_models import RelatedWordEntry
        related_entries = []
        for result in vector_results:
            related_vocab_id = result["metadata"]["vocab_id"]
            # Skip the original word
            if related_vocab_id != vocab_id:
                related_record = await get_vocabulary_by_id(related_vocab_id, user.id)
                if related_record:
                    entry = _record_to_entry(related_record)
                    # Get distance/similarity score from vector result
                    # Note: Qdrant returns similarity scores (higher is better)
                    # We convert to distance (lower is better) for consistency
                    similarity = result.get("score", 0.5)
                    distance = 1.0 - similarity if similarity > 0 else 0.5
                    
                    related_entries.append(RelatedWordEntry(
                        entry=entry,
                        distance=distance
                    ))
        
        # Limit to requested number
        related_entries = related_entries[:limit]
        
        return VocabularyRelatedWordsResponse(
            success=True,
            word=word,
            related_words=related_entries
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting related words: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get related words: {str(e)}"
        )


@router.post("/learn", response_model=VocabularyCreateResponse)
async def learn_vocabulary(
    word: str,
    language: str = "english",
    user: User = Depends(get_current_user)
):
    """
    AI-powered vocabulary learning: Enter a word and get AI-generated
    definition, pronunciation, and example sentence, then save to memory
    """
    try:
        import openai
        import os
        import json
        
        logger.info(f"Learning vocabulary '{word}' for user {user.email}")
        
        # Use OpenAI to generate vocabulary information
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if not openai_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenAI API key not configured"
            )
        
        client = openai.OpenAI(api_key=openai_api_key)
        
        # Create a prompt for generating vocabulary information
        prompt = f"""You are a vocabulary teacher. Provide detailed information about the word "{word}" in {language}.

Return a JSON object with these fields:
- word: the word itself
- pronunciation: IPA phonetic pronunciation
- definition: clear, concise definition (1-2 sentences)
- sample_sentence: a natural example sentence using the word
- related_words: array of 3-5 related or similar words
- difficulty: one of "beginner", "intermediate", or "advanced"
- tags: array of 2-4 relevant category tags

Example format:
{{
    "word": "apple",
    "pronunciation": "/ˈæp.əl/",
    "definition": "A round fruit with red or green skin and firm white flesh",
    "sample_sentence": "I eat an apple every day for breakfast.",
    "related_words": ["fruit", "pear", "banana", "orange"],
    "difficulty": "beginner",
    "tags": ["food", "fruit", "health", "nutrition"]
}}

Only return the JSON object, no other text."""

        model = os.getenv("OPENAI_MODEL", settings.OPENAI_MODEL)
        is_new_model = model.startswith("gpt-5") or model.startswith("o1") or model.startswith("o3")

        completion_kwargs = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful vocabulary teacher that provides accurate, educational word definitions."},
                {"role": "user", "content": prompt}
            ],
        }

        # OpenAI API: GPT-4 uses max_tokens; GPT-5/o1/o3 use max_completion_tokens
        if is_new_model:
            completion_kwargs["max_completion_tokens"] = 500
        else:
            completion_kwargs["max_tokens"] = 500
            completion_kwargs["temperature"] = 0.7

        response = client.chat.completions.create(**completion_kwargs)
        
        # Parse the AI response
        ai_content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if ai_content.startswith("```"):
            ai_content = ai_content.split("```")[1]
            if ai_content.startswith("json"):
                ai_content = ai_content[4:]
            ai_content = ai_content.strip()
        
        vocab_data = json.loads(ai_content)
        
        # Insert into PostgreSQL
        vocab_id = await insert_vocabulary(
            user_id=user.id,
            word=vocab_data.get("word", word),
            pronunciation=vocab_data.get("pronunciation"),
            definition=vocab_data["definition"],
            sample_sentence=vocab_data.get("sample_sentence"),
            related_words=vocab_data.get("related_words", []),
            language=language,
            difficulty=vocab_data.get("difficulty"),
            tags=vocab_data.get("tags", []),
            notes=f"AI-generated on {vocab_data.get('word', word)}",
        )
        
        # Add to vector database for semantic search
        vector_db = get_vocabulary_vector_db()
        await vector_db.add_vocabulary(
            vocab_id=vocab_id,
            user_id=user.id,
            word=vocab_data.get("word", word),
            definition=vocab_data["definition"],
            pronunciation=vocab_data.get("pronunciation"),
            sample_sentence=vocab_data.get("sample_sentence"),
            related_words=vocab_data.get("related_words", []),
            language=language,
            difficulty=vocab_data.get("difficulty"),
            tags=vocab_data.get("tags", []),
        )
        
        logger.info(f"✅ Successfully learned vocabulary: {word} (ID: {vocab_id})")
        
        return VocabularyCreateResponse(
            success=True,
            vocab_id=vocab_id,
            message=f"Successfully learned '{word}' with AI-generated content"
        )
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse AI response: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to parse AI-generated vocabulary data"
        )
    except Exception as e:
        logger.error(f"Error learning vocabulary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to learn vocabulary: {str(e)}"
        )


# Export the router
__all__ = ["router"]
