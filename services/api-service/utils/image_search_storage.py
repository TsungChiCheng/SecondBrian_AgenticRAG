#!/usr/bin/env python3
"""
Store image analysis results in both PostgreSQL and Vector Database
Fixes the issue where image search results are not searchable
"""

import asyncio
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
import httpx
import asyncpg


class ImageSearchStorage:
    """Store and retrieve image analysis results"""
    
    def __init__(
        self,
        postgres_host: str = "localhost",
        postgres_port: int = 5432,
        postgres_db: str = "secondbrain",
        postgres_user: str = "postgres",
        postgres_password: str = "postgres",
        vector_service_url: str = "http://localhost:8002"
    ):
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_db = postgres_db
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.vector_service_url = vector_service_url
        self.conn = None
    
    async def connect(self):
        """Connect to PostgreSQL"""
        if not self.conn:
            self.conn = await asyncpg.connect(
                host=self.postgres_host,
                port=self.postgres_port,
                database=self.postgres_db,
                user=self.postgres_user,
                password=self.postgres_password
            )
            print(f"✅ Connected to PostgreSQL at {self.postgres_host}:{self.postgres_port}")
    
    async def close(self):
        """Close PostgreSQL connection"""
        if self.conn:
            await self.conn.close()
            print("✅ PostgreSQL connection closed")
    
    async def store_image_analysis(
        self,
        user_query: Optional[str],
        summary: str,
        descriptions: Dict[str, str],
        extracted_text: str,
        suggested_queries: List[str],
        topics: List[str]
    ) -> str:
        """
        Store image analysis in both PostgreSQL and Vector DB
        
        Args:
            user_query: Optional user question about the image
            summary: Consensus summary from all models
            descriptions: Individual model descriptions
            extracted_text: Extracted text from image
            suggested_queries: Generated search queries
            topics: Extracted topics
        
        Returns:
            Analysis ID
        """
        analysis_id = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            await self.connect()
            
            # 1. Store in PostgreSQL
            await self._store_in_postgres(
                analysis_id=analysis_id,
                user_query=user_query,
                summary=summary,
                descriptions=descriptions,
                extracted_text=extracted_text,
                suggested_queries=suggested_queries,
                topics=topics
            )
            
            # 2. Store in Vector Database
            await self._store_in_vector_db(
                analysis_id=analysis_id,
                user_query=user_query,
                summary=summary,
                topics=topics
            )
            
            print(f"✅ Stored image analysis: {analysis_id}")
            return analysis_id
            
        except Exception as e:
            print(f"❌ Error storing image analysis: {e}")
            raise
    
    async def _store_in_postgres(
        self,
        analysis_id: str,
        user_query: Optional[str],
        summary: str,
        descriptions: Dict[str, str],
        extracted_text: str,
        suggested_queries: List[str],
        topics: List[str]
    ):
        """Store in PostgreSQL prompt_logs table"""
        import json
        
        # Combine user query and summary for user_input field
        user_input = user_query if user_query else "Image Analysis"
        
        # Create answers dict from descriptions
        answers = {
            "summary": summary,
            "descriptions": descriptions,
            "extracted_text": extracted_text,
            "suggested_queries": suggested_queries
        }
        
        query = """
            INSERT INTO prompt_logs 
            (id, user_input, summary, answers, topics, created_at)
            VALUES ($1, $2, $3, $4, $5, $6)
        """
        
        await self.conn.execute(
            query,
            analysis_id,
            user_input,
            summary,
            json.dumps(answers),
            topics,
            datetime.now()
        )
        
        print(f"  ✓ Stored in PostgreSQL")
    
    async def _store_in_vector_db(
        self,
        analysis_id: str,
        user_query: Optional[str],
        summary: str,
        topics: List[str]
    ):
        """Store in Vector Database for semantic search"""
        
        # Create searchable content
        if user_query:
            content = f"Image Query: {user_query}\nAnalysis: {summary}"
            display_query = user_query
        else:
            content = f"Image Analysis: {summary}"
            display_query = "Image Analysis"
        
        concept_data = {
            "concepts": [
                {
                    "id": analysis_id,
                    "content": content,
                    "type": "image_analysis",
                    "metadata": {
                        "query": display_query,
                        "summary": summary,
                        "topics": topics,
                        "timestamp": datetime.now().isoformat(),
                        "is_image": True
                    }
                }
            ]
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.vector_service_url}/concepts/add",
                json=concept_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                print(f"  ✓ Stored in Vector Database")
            else:
                raise Exception(f"Vector DB error: {response.status_code} - {response.text[:200]}")
    
    async def search_image_analyses(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search stored image analyses
        
        Args:
            query: Search query
            limit: Maximum results
        
        Returns:
            List of matching image analyses
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.vector_service_url}/concepts/search",
                    json={
                        "query": query,
                        "limit": limit,
                        "score_threshold": 0.3
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Filter to only image analyses
                    results = [
                        r for r in data.get("results", [])
                        if r.get("metadata", {}).get("is_image", False)
                    ]
                    return results
                else:
                    raise Exception(f"Search error: {response.status_code}")
                    
        except Exception as e:
            print(f"❌ Error searching: {e}")
            return []


async def demo_image_storage():
    """Demo: Store and search image analysis"""
    print("=" * 60)
    print("Image Analysis Storage Demo")
    print("=" * 60)
    print()
    
    # Initialize storage
    storage = ImageSearchStorage(
        postgres_host="localhost",
        postgres_port=5432,
        vector_service_url="http://localhost:8002"
    )
    
    try:
        # Example 1: Image with user query
        print("1️⃣  Storing image analysis with user query...")
        analysis_id_1 = await storage.store_image_analysis(
            user_query="What landmarks are in this image?",
            summary="The image shows the Taipei 101 skyscraper, one of Taiwan's most iconic buildings. The tower stands prominently against a clear blue sky, showcasing its distinctive pagoda-inspired architecture with bamboo-like structural elements.",
            descriptions={
                "OpenAI": "This is Taipei 101, a landmark skyscraper in Taiwan...",
                "Claude": "The image depicts the famous Taipei 101 building...",
                "Gemini": "Taipei 101 is shown in this photograph...",
                "Grok": "The iconic Taipei 101 tower dominates this image..."
            },
            extracted_text="",
            suggested_queries=["taipei-101", "taiwan-landmarks", "skyscrapers"],
            topics=["taiwan", "architecture", "landmarks"]
        )
        print(f"   ID: {analysis_id_1}")
        print()
        
        # Example 2: Image without query
        print("2️⃣  Storing image analysis without user query...")
        analysis_id_2 = await storage.store_image_analysis(
            user_query=None,
            summary="The image shows a traditional Japanese temple with cherry blossoms in full bloom. The scene captures spring in Japan with pink sakura petals falling around a wooden temple structure with curved roofs.",
            descriptions={
                "OpenAI": "A beautiful Japanese temple surrounded by cherry blossoms...",
                "Claude": "This photo shows a traditional temple during hanami season...",
            },
            extracted_text="",
            suggested_queries=["japanese-temple", "cherry-blossoms", "spring-japan"],
            topics=["japan", "temples", "sakura", "spring"]
        )
        print(f"   ID: {analysis_id_2}")
        print()
        
        # Wait for indexing
        print("⏳ Waiting 2 seconds for vector indexing...")
        await asyncio.sleep(2)
        print()
        
        # Search examples
        print("3️⃣  Searching stored image analyses...")
        print()
        
        search_queries = [
            "Taiwan buildings",
            "Japanese temples",
            "cherry blossoms",
            "architecture"
        ]
        
        for search_query in search_queries:
            print(f"Search: '{search_query}'")
            print("-" * 40)
            
            results = await storage.search_image_analyses(
                query=search_query,
                limit=3
            )
            
            if results:
                for i, result in enumerate(results, 1):
                    score = result.get('score', 0)
                    content = result.get('content', '')[:100]
                    is_image = result.get('metadata', {}).get('is_image', False)
                    icon = "🖼️ " if is_image else "📝 "
                    print(f"  {i}. {icon}Score: {score:.4f}")
                    print(f"     {content}...")
            else:
                print("  No results found")
            
            print()
        
    finally:
        await storage.close()
    
    print("=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)


async def update_image_endpoint():
    """
    Show how to modify the /analyze-image endpoint to store results
    This is a code example, not executable
    """
    print("=" * 60)
    print("Code Example: Update /analyze-image Endpoint")
    print("=" * 60)
    print()
    
    example_code = '''
# Add this to /analyze-image endpoint in services/api-service/main.py
# After generating the summary (around line 805)

# Store image analysis in databases
try:
    # Extract topics
    topics = await _extract_topics_from_question(
        request.user_query if request.user_query else summary[:100]
    )
    
    # Store in PostgreSQL
    analysis_id = f"img_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Create content for storage
    if request.user_query:
        user_input = f"Image Query: {request.user_query}"
        storage_content = f"Q: {request.user_query}\\nA: {summary}"
    else:
        user_input = "Image Analysis"
        storage_content = f"Image Analysis: {summary}"
    
    # Store in vector database
    async with httpx.AsyncClient() as client:
        concept_data = {
            "concepts": [{
                "id": analysis_id,
                "content": storage_content,
                "type": "image_analysis",
                "metadata": {
                    "query": request.user_query or "Image Analysis",
                    "summary": summary,
                    "topics": topics,
                    "timestamp": datetime.now().isoformat(),
                    "is_image": True
                }
            }]
        }
        
        vector_response = await client.post(
            f"{VECTOR_SERVICE_URL}/concepts/add",
            json=concept_data,
            timeout=30.0
        )
        
        if vector_response.status_code == 200:
            print(f"✅ Stored image analysis in vector DB: {analysis_id}")
        else:
            print(f"❌ Failed to store in vector DB: {vector_response.status_code}")
            
except Exception as e:
    print(f"❌ Error storing image analysis: {e}")
'''
    
    print(example_code)
    print()
    print("=" * 60)


if __name__ == "__main__":
    # Run demos
    print()
    asyncio.run(demo_image_storage())
    print()
    asyncio.run(update_image_endpoint())
