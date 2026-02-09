# API Service Utilities

This directory contains utility scripts and helpers for the API service.

## Files

### embedding_search.py
**Purpose**: Standalone embedding-based search utility

**Features**:
- Generate embeddings using OpenAI API
- Calculate cosine similarity between vectors
- Search concepts by semantic similarity
- Demo functions for testing search functionality

**Usage**:
```bash
# Run demo
cd /path/to/services/api-service/utils
python embedding_search.py
```

**Classes**:
- `EmbeddingSearch`: Main class for embedding operations
  - `generate_embedding(text)`: Create embedding vector
  - `cosine_similarity(vec1, vec2)`: Calculate similarity score
  - `search_by_embedding(query, limit, threshold)`: Search via vector service
  - `search_local(query, documents, limit, threshold)`: Local search without vector service

### image_search_storage.py
**Purpose**: Store and retrieve image analysis results

**Features**:
- Store image analyses in PostgreSQL
- Store image embeddings in Vector Database (Qdrant)
- Search stored image analyses by semantic similarity
- Demo functions for testing storage

**Usage**:
```bash
# Run demo
cd /path/to/services/api-service/utils
python image_search_storage.py
```

**Classes**:
- `ImageSearchStorage`: Main storage class
  - `store_image_analysis(...)`: Store analysis in both databases
  - `search_image_analyses(query, limit)`: Find similar analyses
  - `_store_in_postgres(...)`: PostgreSQL storage
  - `_store_in_vector_db(...)`: Vector DB storage

## Integration

The image storage functionality has been **integrated into the main API service**:

### `/analyze-image` Endpoint Enhancement

The endpoint now automatically:
1. ✅ Analyzes images with multiple vision models
2. ✅ Generates consensus summary
3. ✅ **Stores results in PostgreSQL** (`prompt_logs` table)
4. ✅ **Stores embeddings in Vector DB** for semantic search
5. ✅ Extracts topics from user query or summary
6. ✅ Makes image analyses searchable via `/search` endpoint

### Storage Flow

```
User uploads image
    ↓
Vision models analyze → Generate summary
    ↓
Extract topics (via LLM)
    ↓
Store in PostgreSQL:
  - user_input: "Image Query: {user_query}" or "Image Analysis"
  - summary: Consensus from all models
  - answers: Individual model descriptions
  - topics: Extracted topics array
    ↓
Store in Vector DB:
  - content: "Q: {query}\nA: {summary}"
  - metadata: query, summary, topics, timestamp, is_image=true
  - embedding: Generated from content
    ↓
Image analysis now searchable!
```

## Testing Image Search

### Test 1: Upload and Analyze
```bash
# Upload an image with a question
curl -X POST http://localhost:8001/analyze-image \
  -H "Content-Type: application/json" \
  -d '{
    "image_base64": "...",
    "mime_type": "image/jpeg",
    "user_query": "What landmarks are in this image?",
    "models": ["openai", "claude", "gemini"]
  }'
```

### Test 2: Search for Image Results
```bash
# Search should now return image analyses
curl http://localhost:8001/search/landmarks

# Response should include:
# - is_image: true in metadata
# - score: similarity score
# - content: image analysis summary
```

### Test 3: Verify Storage
```bash
# Check PostgreSQL
docker exec -it postgres psql -U alvin -d secondbrain \
  -c "SELECT user_input, summary FROM prompt_logs WHERE user_input LIKE 'Image%' ORDER BY created_at DESC LIMIT 3;"

# Check Vector DB
curl http://localhost:8002/concepts/search \
  -H "Content-Type: application/json" \
  -d '{"query": "image", "limit": 5}'
```

## Environment Variables

Required for utilities:
```bash
OPENAI_API_KEY=sk-...                    # For embeddings
POSTGRES_HOST=localhost                  # Database host
POSTGRES_PORT=5432                       # Database port
POSTGRES_DB=secondbrain                  # Database name
POSTGRES_USER=alvin                      # Database user
POSTGRES_PASSWORD=postgres               # Database password
VECTOR_SERVICE_URL=http://localhost:8002 # Vector service
```

## Benefits

✅ **Image analyses are now searchable**: Search "taiwan landmarks" will find images with Taipei 101  
✅ **Topic browsing includes images**: Topics like "architecture" will show both Q&A and image analyses  
✅ **Unified search experience**: Text and image content searched together semantically  
✅ **Knowledge persistence**: Image insights stored alongside Q&A sessions  

## Next Steps

1. ✅ Integration complete - image storage working in main API
2. ⬜ Test with real images and verify search results
3. ⬜ Add image metadata filtering (filter by is_image flag)
4. ⬜ Create dedicated `/images/search` endpoint for image-only search
5. ⬜ Add image thumbnail storage for visual results display
