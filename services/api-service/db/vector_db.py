"""
vector_db.py - ChromaDB integration for Second Brain
Manages vector storage and retrieval of conversations and knowledge points.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4

import chromadb
from chromadb.config import Settings
from pydantic import BaseModel

from config.config import settings

log = logging.getLogger(__name__)

# Configuration
CHROMA_DB_PATH = settings.CHROMA_DB_PATH
COLLECTION_NAME = settings.CHROMA_COLLECTION_NAME

class KnowledgeEntry(BaseModel):
    id: str
    user_input: str
    summary: str
    answers: Dict[str, Any]
    created_at: datetime
    topics: List[str] = []
    embedding_text: str

class VectorDatabase:
    def __init__(self):
        self._client = None
        self._collection = None

    def get_client(self):
        """Get or create ChromaDB client"""
        if self._client is None:
            self._client = chromadb.PersistentClient(
                path=CHROMA_DB_PATH,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
        return self._client

    def get_collection(self):
        """Get or create the knowledge collection"""
        if self._collection is None:
            client = self.get_client()
            try:
                self._collection = client.get_collection(name=COLLECTION_NAME)
                log.info(f"Loaded existing collection: {COLLECTION_NAME}")
            except Exception:
                # Collection doesn't exist, create it
                self._collection = client.create_collection(
                    name=COLLECTION_NAME,
                    metadata={"description": "Second Brain knowledge storage"}
                )
                log.info(f"Created new collection: {COLLECTION_NAME}")
        return self._collection

    def _prepare_embedding_text(self, user_input: str, summary: str, answers: Dict[str, Any]) -> str:
        """Prepare text for embedding by combining all relevant content"""
        # Combine user input, summary, and key parts of answers
        parts = [
            f"Question: {user_input}",
            f"Summary: {summary}"
        ]
        
        # Add answers from each AI model
        if isinstance(answers, dict):
            for model, answer in answers.items():
                if isinstance(answer, str):
                    parts.append(f"{model}: {answer[:500]}")  # Limit length
        
        return "\n".join(parts)

    def _extract_topics(self, user_input: str, summary: str) -> List[str]:
        """Extract simple topics from user input and summary"""
        # Simple keyword extraction - could be enhanced with NLP
        text = f"{user_input} {summary}".lower()
        
        # Common topic keywords (could be expanded or made smarter)
        topic_keywords = {
            'programming': ['code', 'programming', 'python', 'javascript', 'software', 'development'],
            'ai': ['ai', 'artificial intelligence', 'machine learning', 'llm', 'gpt', 'model'],
            'database': ['database', 'sql', 'postgresql', 'data', 'query'],
            'web': ['web', 'html', 'css', 'frontend', 'backend', 'api'],
            'science': ['science', 'research', 'study', 'analysis'],
            'business': ['business', 'strategy', 'market', 'company'],
            'health': ['health', 'medical', 'medicine', 'healthcare'],
            'technology': ['technology', 'tech', 'innovation', 'digital'],
        }
        
        detected_topics = []
        for topic, keywords in topic_keywords.items():
            if any(keyword in text for keyword in keywords):
                detected_topics.append(topic)
        
        return detected_topics if detected_topics else ['general']

    async def store_knowledge(
        self, 
        user_input: str, 
        summary: str, 
        answers: Dict[str, Any]
    ) -> str:
        """Store a knowledge entry in the vector database"""
        try:
            collection = self.get_collection()
            
            # Generate unique ID
            entry_id = str(uuid4())
            
            # Prepare embedding text
            embedding_text = self._prepare_embedding_text(user_input, summary, answers)
            
            # Extract topics
            topics = self._extract_topics(user_input, summary)
            
            # Create metadata
            metadata = {
                "user_input": user_input,
                "summary": summary,
                "created_at": datetime.now().isoformat(),
                "topics": json.dumps(topics),
                "answer_count": len(answers) if isinstance(answers, dict) else 0
            }
            
            # Store in ChromaDB
            collection.add(
                ids=[entry_id],
                documents=[embedding_text],
                metadatas=[metadata]
            )
            
            log.info(f"Stored knowledge entry: {entry_id}")
            return entry_id
            
        except Exception as e:
            log.error(f"Error storing knowledge: {e}")
            raise e

    async def search_similar(
        self, 
        query: str, 
        limit: int = 10,
        similarity_threshold: float = 0.7
    ) -> List[KnowledgeEntry]:
        """Search for similar knowledge entries"""
        try:
            collection = self.get_collection()
            
            # Query the vector database
            results = collection.query(
                query_texts=[query],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )
            
            entries = []
            if results['ids'] and results['ids'][0]:
                for i, entry_id in enumerate(results['ids'][0]):
                    # Filter by similarity threshold
                    distance = results['distances'][0][i] if results['distances'] else 0
                    similarity = 1 - distance  # Convert distance to similarity
                    
                    if similarity >= similarity_threshold:
                        metadata = results['metadatas'][0][i]
                        
                        # Reconstruct answers from stored data (simplified)
                        # In a real implementation, you might store answers separately
                        answers = {"summary": metadata.get("summary", "")}
                        
                        entry = KnowledgeEntry(
                            id=entry_id,
                            user_input=metadata.get("user_input", ""),
                            summary=metadata.get("summary", ""),
                            answers=answers,
                            created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
                            topics=json.loads(metadata.get("topics", "[]")),
                            embedding_text=results['documents'][0][i]
                        )
                        entries.append(entry)
            
            log.info(f"Found {len(entries)} similar entries for query: {query[:50]}...")
            return entries
            
        except Exception as e:
            log.error(f"Error searching knowledge: {e}")
            return []

    async def get_by_topic(self, topic: str, limit: int = 20) -> List[KnowledgeEntry]:
        """Get entries by topic"""
        try:
            collection = self.get_collection()
            
            # Use where clause to filter by topic
            results = collection.get(
                where={"topics": {"$contains": topic}},
                limit=limit,
                include=["documents", "metadatas"]
            )
            
            entries = []
            if results['ids']:
                for i, entry_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    
                    answers = {"summary": metadata.get("summary", "")}
                    
                    entry = KnowledgeEntry(
                        id=entry_id,
                        user_input=metadata.get("user_input", ""),
                        summary=metadata.get("summary", ""),
                        answers=answers,
                        created_at=datetime.fromisoformat(metadata.get("created_at", datetime.now().isoformat())),
                        topics=json.loads(metadata.get("topics", "[]")),
                        embedding_text=results['documents'][i]
                    )
                    entries.append(entry)
            
            return entries
            
        except Exception as e:
            log.error(f"Error getting entries by topic: {e}")
            return []

    async def get_by_date_range(
        self, 
        start_date: date, 
        end_date: Optional[date] = None,
        limit: int = 50
    ) -> List[KnowledgeEntry]:
        """Get entries within a date range"""
        try:
            if end_date is None:
                end_date = start_date
            
            collection = self.get_collection()
            
            # Get all entries and filter by date (ChromaDB doesn't have great date filtering)
            results = collection.get(
                limit=1000,  # Get more entries to filter
                include=["documents", "metadatas"]
            )
            
            entries = []
            if results['ids']:
                for i, entry_id in enumerate(results['ids']):
                    metadata = results['metadatas'][i]
                    
                    try:
                        entry_date = datetime.fromisoformat(metadata.get("created_at", "")).date()
                        if start_date <= entry_date <= end_date:
                            answers = {"summary": metadata.get("summary", "")}
                            
                            entry = KnowledgeEntry(
                                id=entry_id,
                                user_input=metadata.get("user_input", ""),
                                summary=metadata.get("summary", ""),
                                answers=answers,
                                created_at=datetime.fromisoformat(metadata.get("created_at", "")),
                                topics=json.loads(metadata.get("topics", "[]")),
                                embedding_text=results['documents'][i]
                            )
                            entries.append(entry)
                            
                            if len(entries) >= limit:
                                break
                    except (ValueError, TypeError):
                        continue  # Skip entries with invalid dates
            
            return entries
            
        except Exception as e:
            log.error(f"Error getting entries by date range: {e}")
            return []

    async def get_all_topics(self) -> List[Dict[str, Any]]:
        """Get all unique topics with counts"""
        try:
            collection = self.get_collection()
            
            results = collection.get(
                include=["metadatas"]
            )
            
            topic_counts = {}
            if results['metadatas']:
                for metadata in results['metadatas']:
                    topics = json.loads(metadata.get("topics", "[]"))
                    for topic in topics:
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1
            
            return [{"topic": topic, "count": count} for topic, count in topic_counts.items()]
            
        except Exception as e:
            log.error(f"Error getting topics: {e}")
            return []

    async def delete_entry(self, entry_id: str) -> bool:
        """Delete a knowledge entry"""
        try:
            collection = self.get_collection()
            collection.delete(ids=[entry_id])
            log.info(f"Deleted entry: {entry_id}")
            return True
        except Exception as e:
            log.error(f"Error deleting entry {entry_id}: {e}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the knowledge collection"""
        try:
            collection = self.get_collection()
            count = collection.count()
            
            return {
                "total_entries": count,
                "collection_name": COLLECTION_NAME,
                "db_path": CHROMA_DB_PATH
            }
        except Exception as e:
            log.error(f"Error getting collection stats: {e}")
            return {"total_entries": 0, "error": str(e)}

# Global instance
_vector_db = None

def get_vector_db() -> VectorDatabase:
    """Get the global vector database instance"""
    global _vector_db
    if _vector_db is None:
        _vector_db = VectorDatabase()
    return _vector_db