#!/usr/bin/env python3
"""
Embedding-based search implementation
Tests semantic search using OpenAI embeddings and cosine similarity
"""

import asyncio
import os
from typing import List, Dict, Any
import httpx
from openai import AsyncOpenAI
import numpy as np


class EmbeddingSearch:
    """Search using OpenAI embeddings and cosine similarity"""
    
    def __init__(self, vector_service_url: str = "http://localhost:8002"):
        self.vector_service_url = vector_service_url
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable not set")
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",  # or "text-embedding-ada-002"
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            print(f"Error generating embedding: {e}")
            raise
    
    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        vec1_np = np.array(vec1)
        vec2_np = np.array(vec2)
        
        dot_product = np.dot(vec1_np, vec2_np)
        norm1 = np.linalg.norm(vec1_np)
        norm2 = np.linalg.norm(vec2_np)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def search_by_embedding(
        self, 
        query: str, 
        limit: int = 10,
        score_threshold: float = 0.3
    ) -> Dict[str, Any]:
        """
        Search using embedding-based similarity
        
        Args:
            query: Search query text
            limit: Maximum number of results
            score_threshold: Minimum similarity score (0-1)
        
        Returns:
            Dictionary with search results
        """
        try:
            # Method 1: Use vector service (recommended)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.vector_service_url}/concepts/search",
                    json={
                        "query": query,
                        "limit": limit,
                        "score_threshold": score_threshold
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    raise Exception(f"Vector service error: {response.status_code}")
        
        except Exception as e:
            print(f"Error searching by embedding: {e}")
            return {"query": query, "results": [], "count": 0, "error": str(e)}
    
    async def search_local(
        self,
        query: str,
        stored_documents: List[Dict[str, Any]],
        limit: int = 10,
        score_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Search locally without vector service (for testing)
        
        Args:
            query: Search query
            stored_documents: List of documents with 'text' and 'embedding' keys
            limit: Maximum results
            score_threshold: Minimum score
        
        Returns:
            List of results with scores
        """
        # Generate query embedding
        query_embedding = await self.generate_embedding(query)
        
        # Calculate similarity for each document
        results = []
        for doc in stored_documents:
            if 'embedding' not in doc or 'text' not in doc:
                continue
            
            score = self.cosine_similarity(query_embedding, doc['embedding'])
            
            if score >= score_threshold:
                results.append({
                    'text': doc['text'],
                    'score': score,
                    'metadata': doc.get('metadata', {})
                })
        
        # Sort by score (descending) and limit
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:limit]


async def demo_search():
    """Demo: Test embedding search"""
    print("=" * 60)
    print("Embedding-based Search Demo")
    print("=" * 60)
    print()
    
    # Initialize search
    searcher = EmbeddingSearch()
    
    # Test queries
    test_queries = [
        "Taichung",
        "Taiwan travel",
        "week vacation plan",
        "yoga meditation",
        "machine learning"
    ]
    
    print("🔍 Testing searches...")
    print()
    
    for query in test_queries:
        print(f"Query: '{query}'")
        print("-" * 40)
        
        results = await searcher.search_by_embedding(
            query=query,
            limit=3,
            score_threshold=0.3
        )
        
        if results.get('results'):
            for i, result in enumerate(results['results'], 1):
                score = result.get('score', 0)
                content = result.get('content', '')[:100]
                print(f"  {i}. Score: {score:.4f}")
                print(f"     {content}...")
        else:
            print(f"  No results found")
        
        print()
    
    # Test similarity calculation
    print("=" * 60)
    print("Direct Similarity Calculation Demo")
    print("=" * 60)
    print()
    
    text1 = "Give me a week travel plan in Taichung"
    text2 = "I want to visit Taiwan for vacation"
    text3 = "What are the best yoga poses for beginners"
    
    print(f"Text 1: {text1}")
    print(f"Text 2: {text2}")
    print(f"Text 3: {text3}")
    print()
    
    # Generate embeddings
    emb1 = await searcher.generate_embedding(text1)
    emb2 = await searcher.generate_embedding(text2)
    emb3 = await searcher.generate_embedding(text3)
    
    # Calculate similarities
    sim_1_2 = searcher.cosine_similarity(emb1, emb2)
    sim_1_3 = searcher.cosine_similarity(emb1, emb3)
    sim_2_3 = searcher.cosine_similarity(emb2, emb3)
    
    print(f"Similarity (Text 1 ↔ Text 2): {sim_1_2:.4f} (travel-related)")
    print(f"Similarity (Text 1 ↔ Text 3): {sim_1_3:.4f} (unrelated)")
    print(f"Similarity (Text 2 ↔ Text 3): {sim_2_3:.4f} (unrelated)")
    print()
    
    print("✅ Higher scores mean more similar semantic meaning!")


if __name__ == "__main__":
    # Run demo
    asyncio.run(demo_search())
