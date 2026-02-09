"""
vocabulary_vector_db.py - Qdrant integration for vocabulary memory
Manages vector storage and retrieval of vocabulary entries for semantic search.
Uses a separate collection from the main knowledge base.
"""
from __future__ import annotations

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
import os

log = logging.getLogger(__name__)

# Vector service configuration
VECTOR_SERVICE_URL = os.getenv("VECTOR_SERVICE_URL", "http://vector:8002")
VOCABULARY_COLLECTION = "vocabulary_memory"


class VocabularyVectorDB:
    """Handler for vocabulary vector operations using the vector service"""
    
    def __init__(self):
        self.vector_service_url = VECTOR_SERVICE_URL
        self.collection_name = VOCABULARY_COLLECTION
    
    async def _ensure_collection_exists(self) -> bool:
        """Ensure the vocabulary collection exists in Qdrant"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Check if collection exists
                response = await client.get(
                    f"{self.vector_service_url}/collections/{self.collection_name}"
                )
                
                if response.status_code == 200:
                    return True
                
                # Collection doesn't exist, create it
                log.info(f"Creating vocabulary collection: {self.collection_name}")
                create_response = await client.post(
                    f"{self.vector_service_url}/collections/create",
                    json={
                        "collection_name": self.collection_name,
                        "vector_size": 1536,  # OpenAI embeddings size
                        "distance": "Cosine"
                    }
                )
                
                if create_response.status_code == 200:
                    log.info(f"Created vocabulary collection successfully")
                    return True
                else:
                    log.error(f"Failed to create collection: {create_response.text}")
                    return False
                    
        except Exception as e:
            log.error(f"Error ensuring collection exists: {e}")
            return False
    
    async def add_vocabulary(
        self,
        vocab_id: int,
        user_id: str,
        word: str,
        definition: str,
        pronunciation: Optional[str] = None,
        sample_sentence: Optional[str] = None,
        related_words: List[str] = None,
        language: str = "english",
        difficulty: Optional[str] = None,
        tags: List[str] = None,
    ) -> bool:
        """Add a vocabulary entry to the vector database"""
        try:
            await self._ensure_collection_exists()
            
            # Prepare the text for embedding (combine all relevant information)
            embedding_parts = [
                f"Word: {word}",
                f"Definition: {definition}",
            ]
            
            if pronunciation:
                embedding_parts.append(f"Pronunciation: {pronunciation}")
            
            if sample_sentence:
                embedding_parts.append(f"Example: {sample_sentence}")
            
            if related_words:
                embedding_parts.append(f"Related: {', '.join(related_words)}")
            
            embedding_text = "\n".join(embedding_parts)
            
            # Prepare metadata
            metadata = {
                "vocab_id": vocab_id,
                "user_id": user_id,
                "word": word,
                "definition": definition,
                "pronunciation": pronunciation or "",
                "sample_sentence": sample_sentence or "",
                "related_words": related_words or [],
                "language": language,
                "difficulty": difficulty or "",
                "tags": tags or [],
                "created_at": datetime.now().isoformat(),
            }
            
            # Store in vector database via vector service
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.vector_service_url}/vocabulary/add",
                    json={
                        "collection_name": self.collection_name,
                        "id": f"vocab_{vocab_id}_{user_id}",
                        "text": embedding_text,
                        "metadata": metadata
                    }
                )
                
                if response.status_code == 200:
                    log.info(f"Added vocabulary to vector DB: {word} (ID: {vocab_id})")
                    return True
                else:
                    log.error(f"Failed to add vocabulary to vector DB: {response.text}")
                    return False
                    
        except Exception as e:
            log.error(f"Error adding vocabulary to vector DB: {e}")
            return False
    
    async def search_vocabulary(
        self,
        query: str,
        user_id: str,
        limit: int = 10,
        language: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vocabulary entries using semantic search"""
        try:
            # Build filter for user-specific search
            filter_conditions = {"user_id": user_id}
            
            if language:
                filter_conditions["language"] = language
            
            if difficulty:
                filter_conditions["difficulty"] = difficulty
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.vector_service_url}/vocabulary/search",
                    json={
                        "collection_name": self.collection_name,
                        "query": query,
                        "limit": limit,
                        "filter": filter_conditions
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get("results", [])
                    log.info(f"Found {len(results)} vocabulary matches for query: {query[:50]}")
                    return results
                else:
                    log.error(f"Vocabulary search failed: {response.text}")
                    return []
                    
        except Exception as e:
            log.error(f"Error searching vocabulary: {e}")
            return []
    
    async def find_related_words(
        self,
        word: str,
        user_id: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Find vocabulary entries related to a given word"""
        try:
            # Search using the word itself to find semantically similar entries
            query = f"Words related to or similar to: {word}"
            return await self.search_vocabulary(query, user_id, limit=limit)
            
        except Exception as e:
            log.error(f"Error finding related words: {e}")
            return []
    
    async def update_vocabulary(
        self,
        vocab_id: int,
        user_id: str,
        word: str,
        definition: str,
        pronunciation: Optional[str] = None,
        sample_sentence: Optional[str] = None,
        related_words: List[str] = None,
        language: str = "english",
        difficulty: Optional[str] = None,
        tags: List[str] = None,
    ) -> bool:
        """Update a vocabulary entry in the vector database"""
        try:
            # Delete old entry and add new one (Qdrant update strategy)
            await self.delete_vocabulary(vocab_id, user_id)
            return await self.add_vocabulary(
                vocab_id=vocab_id,
                user_id=user_id,
                word=word,
                definition=definition,
                pronunciation=pronunciation,
                sample_sentence=sample_sentence,
                related_words=related_words,
                language=language,
                difficulty=difficulty,
                tags=tags,
            )
            
        except Exception as e:
            log.error(f"Error updating vocabulary in vector DB: {e}")
            return False
    
    async def delete_vocabulary(self, vocab_id: int, user_id: str) -> bool:
        """Delete a vocabulary entry from the vector database"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.delete(
                    f"{self.vector_service_url}/vocabulary/delete",
                    json={
                        "collection_name": self.collection_name,
                        "id": f"vocab_{vocab_id}_{user_id}"
                    }
                )
                
                if response.status_code == 200:
                    log.info(f"Deleted vocabulary from vector DB: ID {vocab_id}")
                    return True
                else:
                    log.warning(f"Failed to delete vocabulary from vector DB: {response.text}")
                    return False
                    
        except Exception as e:
            log.error(f"Error deleting vocabulary from vector DB: {e}")
            return False
    
    async def get_collection_stats(self, user_id: str) -> Dict[str, Any]:
        """Get statistics about the vocabulary collection for a specific user"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.vector_service_url}/vocabulary/stats",
                    json={
                        "collection_name": self.collection_name,
                        "user_id": user_id
                    }
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    return {"total_entries": 0, "error": "Failed to get stats"}
                    
        except Exception as e:
            log.error(f"Error getting vocabulary stats: {e}")
            return {"total_entries": 0, "error": str(e)}


# Global instance
_vocab_vector_db = None

def get_vocabulary_vector_db() -> VocabularyVectorDB:
    """Get the global vocabulary vector database instance"""
    global _vocab_vector_db
    if _vocab_vector_db is None:
        _vocab_vector_db = VocabularyVectorDB()
    return _vocab_vector_db
