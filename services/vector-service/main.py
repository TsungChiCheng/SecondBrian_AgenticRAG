"""
Vector Service - Handles embedding generation and vector search using OpenAI embeddings and Qdrant
"""

import os
import logging
from typing import List, Dict, Any, Optional
import uuid
import numpy as np

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import httpx
import openai
from qdrant_client import QdrantClient
from qdrant_client.http import models
from qdrant_client.http.models import Distance, VectorParams, PointStruct

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level)
logger = logging.getLogger(__name__)
print("Vector service module imported; initializing...", flush=True)

# Try to import tiktoken for token counting
try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    logger.warning("tiktoken not available - using fallback token estimation")
    TIKTOKEN_AVAILABLE = False

# Token limits for OpenAI embeddings (text-embedding-3-small supports 8191 tokens)
MAX_EMBEDDING_TOKENS = 8191

app = FastAPI(title="Vector Service", description="Handles embeddings and vector search")

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
HAS_OPENAI_KEY = bool(OPENAI_API_KEY)
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))

if not HAS_OPENAI_KEY:
    logger.warning("OPENAI_API_KEY not set. Embedding features will be disabled.")
else:
    openai.api_key = OPENAI_API_KEY

class OpenAIEmbeddingsService:
    """Service for generating embeddings using OpenAI's API"""
    
    def __init__(self):
        self.model = "text-embedding-3-small"  # Using OpenAI's latest embedding model
        self._api_key = OPENAI_API_KEY
        self._client: Optional[openai.OpenAI] = None
        if self._api_key:
            self._client = openai.OpenAI(api_key=self._api_key)
        else:
            logger.warning("OpenAI API key missing - embeddings endpoints will return 503.")
    
    def is_configured(self) -> bool:
        """Return True when an API key is available."""
        return self._client is not None

    def _require_client(self) -> openai.OpenAI:
        """Return configured client or raise if unavailable."""
        if not self._client:
            raise RuntimeError("OpenAI API key not configured. Embedding features are disabled.")
        return self._client
    
    def _count_tokens(self, text: str) -> int:
        """Count tokens in text for validation."""
        if not TIKTOKEN_AVAILABLE:
            # Fallback: rough estimation (1 token ≈ 4 characters)
            return len(text) // 4
        
        try:
            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except Exception:
            # Fallback to character-based estimation
            return len(text) // 4
    
    def _validate_text_length(self, text: str, operation: str = "embedding") -> None:
        """Validate text doesn't exceed token limits."""
        token_count = self._count_tokens(text)
        if token_count > MAX_EMBEDDING_TOKENS:
            logger.error(
                f"Text exceeds embedding token limit: {token_count} > {MAX_EMBEDDING_TOKENS}. "
                f"Operation: {operation}. Text preview: {text[:200]}..."
            )
            raise ValueError(
                f"Text is too long for {operation} ({token_count} tokens, max {MAX_EMBEDDING_TOKENS}). "
                f"Please split into smaller chunks."
            )
        elif token_count > MAX_EMBEDDING_TOKENS * 0.9:
            logger.warning(
                f"Text approaching embedding token limit: {token_count} tokens "
                f"({token_count / MAX_EMBEDDING_TOKENS * 100:.1f}% of max). "
                f"Operation: {operation}."
            )
        
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            # Validate text length first
            self._validate_text_length(text, operation="single embedding")
            
            client = self._require_client()
            response = client.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            raise
    
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            # Validate all texts first
            for i, text in enumerate(texts):
                self._validate_text_length(text, operation=f"batch embedding (text {i+1}/{len(texts)})")
            
            client = self._require_client()
            response = client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except ValueError as e:
            # Re-raise validation errors
            raise
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

class QdrantVectorService:
    """Service for managing vectors in Qdrant"""
    
    def __init__(self):
        self.client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        self.collection_name = "knowledge_graph_concepts"
        self.embeddings_service = OpenAIEmbeddingsService()
        self._initialize_collection()
    
    def _initialize_collection(self):
        """Initialize Qdrant collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                logger.info(f"Creating collection: {self.collection_name}")
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(size=1536, distance=Distance.COSINE)
                )
                logger.info("Collection created successfully")
            else:
                logger.info(f"Collection {self.collection_name} already exists")
                
        except Exception as e:
            logger.error(f"Error initializing collection: {e}")
            raise
    
    def add_concepts(self, concepts: List[Dict[str, Any]]) -> bool:
        """Add concept embeddings to the vector store"""
        try:
            if not concepts:
                return True
            
            # Generate embeddings for concept texts
            texts = [concept.get("content", "") for concept in concepts]
            embeddings = self.embeddings_service.generate_embeddings(texts)
            
            # Prepare points for insertion
            points = []
            for i, (concept, embedding) in enumerate(zip(concepts, embeddings)):
                point_id = str(uuid.uuid4())
                metadata = concept.get("metadata", {})
                user_id = metadata.get("user_id", None)  # Extract user_id from metadata
                
                points.append(
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={
                            "concept_id": concept.get("id", point_id),
                            "content": concept.get("content", ""),
                            "type": concept.get("type", "concept"),
                            "user_id": user_id,  # Store user_id at top level for filtering
                            "metadata": metadata
                        }
                    )
                )
            
            # Insert points
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"Added {len(points)} concepts to vector store (user_id: {user_id if user_id else 'NULL'})")
            return True
            
        except Exception as e:
            logger.error(f"Error adding concepts: {e}")
            return False
    
    def search_concepts(self, query: str, limit: int = 10, score_threshold: float = 0.3) -> List[Dict[str, Any]]:
        """Search for similar concepts"""
        try:
            # Generate embedding for query
            query_embedding = self.embeddings_service.generate_embedding(query)
            
            # Search in Qdrant
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold
            )
            
            # Format results
            results = []
            for result in search_results:
                results.append({
                    "id": result.id,
                    "score": result.score,
                    "concept_id": result.payload.get("concept_id"),
                    "content": result.payload.get("content"),
                    "type": result.payload.get("type"),
                    "metadata": result.payload.get("metadata", {})
                })
            
            logger.info(f"Found {len(results)} similar concepts for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching concepts: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the vector collection"""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            # Handle both old and new API response formats
            vectors_count = getattr(collection_info, 'vectors_count', None)
            points_count = getattr(collection_info, 'points_count', None)
            
            # If vectors_count is not available, try to get it from result
            if vectors_count is None and hasattr(collection_info, 'result'):
                vectors_count = collection_info.result.get('vectors_count', 0)
                points_count = collection_info.result.get('points_count', 0)
            
            status = "unknown"
            if hasattr(collection_info, 'status'):
                status = collection_info.status.value if hasattr(collection_info.status, 'value') else str(collection_info.status)
            
            return {
                "collection_name": self.collection_name,
                "vectors_count": vectors_count or 0,
                "points_count": points_count or 0,
                "status": status
            }
        except Exception as e:
            logger.error(f"Error getting collection stats: {e}")
            # Return basic stats instead of failing
            return {
                "collection_name": self.collection_name,
                "vectors_count": 0,
                "points_count": 0,
                "status": "unknown"
            }
    
    def get_knowledge_graph(self, limit: int = 100, user_id: str = None) -> Dict[str, Any]:
        """Get knowledge graph data with nodes and relationships"""
        try:
            # Build filter for user_id if provided
            scroll_filter = None
            if user_id:
                from qdrant_client.models import Filter, FieldCondition, MatchValue
                scroll_filter = Filter(
                    must=[
                        FieldCondition(
                            key="user_id",
                            match=MatchValue(value=user_id)
                        )
                    ]
                )
            
            # Scroll through all points to get concepts
            points_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=limit,
                with_payload=True,
                with_vectors=True,  # Need vectors for similarity calculations
                scroll_filter=scroll_filter
            )
            
            points = points_result[0] if isinstance(points_result, tuple) else points_result
            
            if not points:
                logger.info("No points found in collection for knowledge graph")
                return {
                    "nodes": [],
                    "edges": [],
                    "metadata": {
                        "total_nodes": 0,
                        "total_edges": 0,
                        "collection": self.collection_name,
                        "message": "No data yet. Ask some questions to build your knowledge graph!"
                    }
                }
            
            nodes = []
            edges = []
            concept_map = {}
            vectors_map = {}
            
            # Process points to create nodes
            for point in points:
                concept_id = str(point.payload.get("concept_id", point.id))
                content = point.payload.get("content", "")
                concept_type = point.payload.get("type", "concept")
                
                # Extract title from content (first 50 chars or first line)
                label = content.split('\n')[0] if '\n' in content else content
                label = label[:50] + "..." if len(label) > 50 else label
                
                node = {
                    "id": concept_id,
                    "label": label,
                    "content": content,
                    "type": concept_type,
                    "size": min(max(len(content) / 10, 10), 25)  # Size based on content length
                }
                nodes.append(node)
                concept_map[concept_id] = point
                # Store vector if available
                if hasattr(point, 'vector') and point.vector:
                    vectors_map[concept_id] = point.vector
            
            logger.info(f"Created {len(nodes)} nodes for knowledge graph")
            
            # Find relationships by similarity using stored vectors
            # OPTIMIZED: Use vectorized NumPy operations for parallel calculation
            edge_set = set()  # To avoid duplicate edges
            
            # Prepare vectors matrix for batch processing
            node_ids = [node["id"] for node in nodes if node["id"] in vectors_map]
            
            if len(node_ids) < 2:
                logger.info("Not enough nodes with vectors for edge calculation")
                return {
                    "nodes": nodes,
                    "edges": [],
                    "metadata": {
                        "total_nodes": len(nodes),
                        "total_edges": 0,
                        "collection": self.collection_name,
                        "message": "Need at least 2 nodes to create relationships"
                    }
                }
            
            # Create matrix of all vectors (shape: n_nodes x vector_dim)
            vectors_matrix = np.array([vectors_map[node_id] for node_id in node_ids])
            
            # OPTIMIZATION 1: Pre-normalize vectors (compute norms once)
            # Normalized vectors allow us to use simple dot product for cosine similarity
            norms = np.linalg.norm(vectors_matrix, axis=1, keepdims=True)
            normalized_vectors = vectors_matrix / norms
            
            # OPTIMIZATION 2: Vectorized similarity calculation (massive speedup!)
            # Compute all pairwise similarities in one operation: similarity = V @ V.T
            # This uses optimized BLAS operations (multi-threaded C/Fortran code)
            similarity_matrix = np.dot(normalized_vectors, normalized_vectors.T)
            
            logger.info(f"Computed similarity matrix of shape {similarity_matrix.shape}")
            
            # OPTIMIZATION 3: Extract edges only from upper triangle (avoid duplicates)
            # Get indices where similarity > threshold
            threshold = 0.7
            i_indices, j_indices = np.where(
                (similarity_matrix > threshold) & 
                (similarity_matrix < 0.9999)  # Exclude self-similarity (≈1.0)
            )
            
            # Create edges from high-similarity pairs
            for idx in range(len(i_indices)):
                i, j = i_indices[idx], j_indices[idx]
                
                # Only process upper triangle to avoid duplicates
                if i >= j:
                    continue
                
                similarity = float(similarity_matrix[i, j])
                node_a_id = node_ids[i]
                node_b_id = node_ids[j]
                
                edge_key = tuple(sorted([node_a_id, node_b_id]))
                if edge_key not in edge_set:
                    edge = {
                        "source": node_a_id,
                        "target": node_b_id,
                        "weight": similarity,
                        "type": "similarity"
                    }
                    edges.append(edge)
                    edge_set.add(edge_key)
            
            logger.info(f"Created {len(edges)} edges for knowledge graph (optimized vectorized calculation)")
            
            return {
                "nodes": nodes,
                "edges": edges,
                "metadata": {
                    "total_nodes": len(nodes),
                    "total_edges": len(edges),
                    "collection": self.collection_name
                }
            }
            
        except Exception as e:
            logger.error(f"Error getting knowledge graph: {e}")
            import traceback
            traceback.print_exc()
            return {
                "nodes": [],
                "edges": [],
                "metadata": {
                    "error": str(e),
                    "message": "Error generating knowledge graph. Please check the logs."
                }
            }

# Initialize services lazily at startup so the server can listen first
vector_service = None
_init_task = None

@app.on_event("startup")
async def startup_event():
    """Kick off background initialization so the server can listen immediately."""
    import asyncio
    global _init_task
    print("Vector service startup_event triggered", flush=True)

    async def _init_worker():
        global vector_service
        max_attempts = 120
        delay_seconds = 2
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"[startup/bg] Initializing Vector service (attempt {attempt}/{max_attempts})")
                vs = QdrantVectorService()
                # Quick smoke check to verify Qdrant is reachable
                _ = vs.get_collection_stats()
                vector_service = vs
                logger.info("[startup/bg] Vector service initialized successfully")
                return
            except Exception as e:
                logger.warning(f"[startup/bg] Vector service init failed: {e}. Retrying in {delay_seconds}s...")
                await asyncio.sleep(delay_seconds)
        logger.error("[startup/bg] Vector service failed to initialize after retries. Health will report 503 until ready.")

    # Start background task only once
    if _init_task is None:
        _init_task = asyncio.create_task(_init_worker())

# Request/Response Models
class AddConceptsRequest(BaseModel):
    concepts: List[Dict[str, Any]]

class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    score_threshold: float = 0.25  # Lowered from 0.3 to get more related results

class EmbeddingRequest(BaseModel):
    text: str

class EmbeddingsRequest(BaseModel):
    texts: List[str]

class GraphRequest(BaseModel):
    limit: int = 100
    similarity_threshold: float = 0.8
    user_id: str = None  # Optional user_id for filtering

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        stats = vector_service.get_collection_stats()
        return {
            "status": "healthy",
            "service": "vector-service",
            "openai_configured": vector_service.embeddings_service.is_configured(),
            "qdrant_connected": True,
            "collection_stats": stats
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {e}")

@app.post("/embeddings/generate")
async def generate_embedding(request: EmbeddingRequest):
    """Generate embedding for a single text"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        embedding = vector_service.embeddings_service.generate_embedding(request.text)
        return {
            "embedding": embedding,
            "dimensions": len(embedding),
            "model": "text-embedding-3-small"
        }
    except Exception as e:
        logger.error(f"Error generating embedding: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/embeddings/generate-batch")
async def generate_embeddings(request: EmbeddingsRequest):
    """Generate embeddings for multiple texts"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        embeddings = vector_service.embeddings_service.generate_embeddings(request.texts)
        return {
            "embeddings": embeddings,
            "count": len(embeddings),
            "dimensions": len(embeddings[0]) if embeddings else 0,
            "model": "text-embedding-3-small"
        }
    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/concepts/add")
async def add_concepts(request: AddConceptsRequest):
    """Add concepts with embeddings to the vector store"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        success = vector_service.add_concepts(request.concepts)
        if success:
            return {
                "message": f"Successfully added {len(request.concepts)} concepts",
                "count": len(request.concepts)
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add concepts")
    except Exception as e:
        logger.error(f"Error adding concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/concepts/search")
async def search_concepts(request: SearchRequest):
    """Search for similar concepts"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        results = vector_service.search_concepts(
            query=request.query,
            limit=request.limit,
            score_threshold=request.score_threshold
        )
        return {
            "query": request.query,
            "results": results,
            "count": len(results)
        }
    except Exception as e:
        logger.error(f"Error searching concepts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/collection/stats")
async def get_collection_stats():
    """Get vector collection statistics"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        stats = vector_service.get_collection_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting collection stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge-graph")
async def get_knowledge_graph(request: GraphRequest):
    """Get knowledge graph data for visualization"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        graph_data = vector_service.get_knowledge_graph(request.limit, user_id=request.user_id)
        return graph_data
    except Exception as e:
        logger.error(f"Error getting knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge-graph")
async def get_knowledge_graph_simple():
    """Get knowledge graph data for visualization (simple version) - DEPRECATED"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        # No user_id filtering for backwards compatibility (shows all data)
        graph_data = vector_service.get_knowledge_graph(100, user_id=None)
        return graph_data
    except Exception as e:
        logger.error(f"Error getting knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# VOCABULARY ENDPOINTS
# ============================================================================

class VocabularyAddRequest(BaseModel):
    collection_name: str
    id: str
    text: str
    metadata: Dict[str, Any]

class VocabularySearchRequest(BaseModel):
    collection_name: str
    query: str
    limit: int = 10
    filter: Optional[Dict[str, Any]] = None

class VocabularyDeleteRequest(BaseModel):
    collection_name: str
    id: str

class CollectionCreateRequest(BaseModel):
    collection_name: str
    vector_size: int = 1536
    distance: str = "Cosine"


@app.get("/collections/{collection_name}")
async def check_collection(collection_name: str):
    """Check if a collection exists"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        collections = vector_service.client.get_collections()
        collection_names = [col.name for col in collections.collections]
        
        if collection_name in collection_names:
            collection_info = vector_service.client.get_collection(collection_name)
            return {
                "exists": True,
                "collection_name": collection_name,
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count
            }
        else:
            raise HTTPException(status_code=404, detail=f"Collection {collection_name} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/collections/create")
async def create_collection(request: CollectionCreateRequest):
    """Create a new collection"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        # Map distance string to Qdrant Distance enum
        distance_map = {
            "Cosine": Distance.COSINE,
            "Euclid": Distance.EUCLID,
            "Dot": Distance.DOT
        }
        distance = distance_map.get(request.distance, Distance.COSINE)
        
        vector_service.client.create_collection(
            collection_name=request.collection_name,
            vectors_config=VectorParams(
                size=request.vector_size,
                distance=distance
            )
        )
        
        logger.info(f"Created collection: {request.collection_name}")
        return {
            "success": True,
            "collection_name": request.collection_name,
            "message": f"Collection {request.collection_name} created successfully"
        }
    except Exception as e:
        logger.error(f"Error creating collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vocabulary/add")
async def add_vocabulary(request: VocabularyAddRequest):
    """Add a vocabulary entry to the vector database"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        # Generate embedding for the text
        embedding = vector_service.embeddings_service.generate_embedding(request.text)
        
        # Create point with embedding and metadata
        point = PointStruct(
            id=request.id,
            vector=embedding,
            payload=request.metadata
        )
        
        # Upsert to Qdrant
        vector_service.client.upsert(
            collection_name=request.collection_name,
            points=[point]
        )
        
        logger.info(f"Added vocabulary entry: {request.id} to {request.collection_name}")
        return {
            "success": True,
            "id": request.id,
            "message": "Vocabulary entry added successfully"
        }
    except Exception as e:
        logger.error(f"Error adding vocabulary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vocabulary/search")
async def search_vocabulary(request: VocabularySearchRequest):
    """Search for similar vocabulary entries"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    if not vector_service.embeddings_service.is_configured():
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    try:
        # Generate embedding for the query
        query_embedding = vector_service.embeddings_service.generate_embedding(request.query)
        
        # Build search filter if provided
        search_filter = None
        if request.filter:
            # Convert dict filter to Qdrant Filter format
            conditions = []
            for key, value in request.filter.items():
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value)
                    )
                )
            if conditions:
                search_filter = models.Filter(must=conditions)
        
        # Search in Qdrant
        search_results = vector_service.client.search(
            collection_name=request.collection_name,
            query_vector=query_embedding,
            limit=request.limit,
            query_filter=search_filter
        )
        
        # Format results
        results = []
        for result in search_results:
            results.append({
                "id": result.id,
                "score": result.score,
                "metadata": result.payload
            })
        
        logger.info(f"Vocabulary search returned {len(results)} results for query: {request.query[:50]}")
        return {
            "results": results,
            "total": len(results),
            "query": request.query
        }
    except Exception as e:
        logger.error(f"Error searching vocabulary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/vocabulary/delete")
async def delete_vocabulary(request: VocabularyDeleteRequest):
    """Delete a vocabulary entry"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    try:
        vector_service.client.delete(
            collection_name=request.collection_name,
            points_selector=models.PointIdsList(
                points=[request.id]
            )
        )
        
        logger.info(f"Deleted vocabulary entry: {request.id} from {request.collection_name}")
        return {
            "success": True,
            "id": request.id,
            "message": "Vocabulary entry deleted successfully"
        }
    except Exception as e:
        logger.error(f"Error deleting vocabulary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vocabulary/stats")
async def get_vocabulary_stats(request: dict):
    """Get statistics about vocabulary collection for a user"""
    if not vector_service:
        raise HTTPException(status_code=503, detail="Vector service not initialized")
    
    collection_name = request.get("collection_name")
    user_id = request.get("user_id")
    
    try:
        collection_info = vector_service.client.get_collection(collection_name)
        
        # Count user-specific entries if user_id provided
        user_count = 0
        if user_id:
            # This is a simplified count - in production you'd want a more efficient approach
            scroll_result = vector_service.client.scroll(
                collection_name=collection_name,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="user_id",
                            match=models.MatchValue(value=user_id)
                        )
                    ]
                ),
                limit=10000  # Adjust as needed
            )
            user_count = len(scroll_result[0])
        
        return {
            "total_entries": collection_info.points_count,
            "user_entries": user_count if user_id else collection_info.points_count,
            "vectors_count": collection_info.vectors_count,
            "collection_name": collection_name
        }
    except Exception as e:
        logger.error(f"Error getting vocabulary stats: {e}")
        return {
            "total_entries": 0,
            "user_entries": 0,
            "error": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)
