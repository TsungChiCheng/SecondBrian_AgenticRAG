# Chunking Strategy Improvement Plan

## Problem Statement

**Current Issue:**
- LLM answers are typically **short** (200-1000 words) compared to documents
- Current fixed-size chunking (900 chars) creates **too many fragments**
- Chunks split mid-sentence/mid-thought, losing semantic coherence
- **No differentiation** between answer chunking and document chunking

**Key Insight:**
> LLM responses have **structured content** (when formatted as markdown), which can be used for smarter semantic chunking

**Important Design Principle:**
> ⚠️ **Markdown formatting is ONLY for storage/chunking purposes.** The answer generation agent should NOT be influenced by markdown structure when reasoning or generating responses. Markdown is applied AFTER the answer is generated, purely for better retrieval organization.

---

## Proposed Solution: Content-Aware Adaptive Chunking

### Strategy Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    LLM Response Received                     │
└─────────────────────────┬───────────────────────────────────┘
                          │
                ┌─────────▼──────────┐
                │ Enforce Markdown   │
                │ Format in Prompts  │
                └─────────┬──────────┘
                          │
                ┌─────────▼──────────┐
                │ Analyze Length     │
                │ & Structure        │
                └─────────┬──────────┘
                          │
        ┌─────────────────┴─────────────────┐
        │                                   │
    Short Answer                      Long Answer
    (< 6000 words)                   (≥ 6000 words)
        │                                   │
        ▼                                   ▼
  ┌──────────────┐                  ┌──────────────┐
  │ Store Whole  │                  │ Split by ##  │
  │  (No Split)  │                  │   Headers    │
  └──────────────┘                  └──────────────┘
        │                                   │
        └─────────────────┬─────────────────┘
                          │
                ┌─────────▼──────────┐
                │  Encode & Store    │
                │   in Qdrant        │
                └────────────────────┘
```

---

## Implementation Options

### Option 1: Markdown Header-Based Splitting (Your Proposal)

**Approach:**
1. **Enforce markdown format** in LLM system prompts
2. **Check word count** on response
3. **Split strategy:**
   - If ≤ 6000 words → Store entire response as single chunk
   - If > 6000 words → Split by `##` headers (H2 level)

**Pros:**
- ✅ Semantic coherence preserved
- ✅ Natural section boundaries
- ✅ No mid-sentence splits
- ✅ Easy to implement
- ✅ Retrieval returns complete thoughts

**Cons:**
- ⚠️ Assumes LLM follows markdown consistently
- ⚠️ Uneven chunk sizes (some sections huge, others tiny)
- ⚠️ Headers might not exist at ideal split points
- ⚠️ Single large section could exceed embedding limits

**Example:**
```markdown
## Introduction
This is the introduction section...

## Technical Details
Very long technical explanation that might be 3000 words...

## Conclusion
Brief conclusion...
```
→ Creates 3 chunks of vastly different sizes

---

### Option 2: Hierarchical Markdown Splitting (Enhanced)

**Approach:**
1. Parse markdown into hierarchical structure
2. Split by headers with **size constraints**:
   - Primary split: `##` (H2)
   - If section > max_size → split by `###` (H3)
   - If still too large → apply recursive character split
3. Preserve header context in each chunk

**Pros:**
- ✅ Semantic + size control
- ✅ Handles edge cases better
- ✅ More consistent chunk sizes
- ✅ Context preserved with headers

**Cons:**
- ⚠️ More complex implementation
- ⚠️ Requires markdown parser

**Implementation:**
```python
def adaptive_markdown_chunk(text: str, max_words: int = 400) -> List[str]:
    """
    Split markdown text by headers with size constraints
    """
    chunks = []
    
    # Parse by H2 headers first
    h2_sections = split_by_header(text, level=2)
    
    for section in h2_sections:
        word_count = count_words(section)
        
        if word_count <= max_words:
            # Section fits in one chunk
            chunks.append(section)
        else:
            # Split by H3 headers
            h3_sections = split_by_header(section, level=3)
            
            for subsection in h3_sections:
                if count_words(subsection) <= max_words:
                    chunks.append(subsection)
                else:
                    # Fallback to sentence-based split
                    semantic_chunks = semantic_split(subsection, max_words)
                    chunks.extend(semantic_chunks)
    
    return chunks
```

---

### Option 3: Semantic Sentence-Based Splitting (Research-Backed)

**Approach:**
Based on recent RAG research (LlamaIndex, Pinecone):
1. Split by **complete sentences**
2. Group sentences by **semantic similarity**
3. Respect size limits (400-600 words per chunk)
4. Add overlap for context continuity

**Pros:**
- ✅ Works for any format (not just markdown)
- ✅ Research-proven effectiveness
- ✅ Consistent chunk sizes
- ✅ Semantic coherence via embeddings

**Cons:**
- ⚠️ Requires embedding model for similarity
- ⚠️ More computationally expensive
- ⚠️ Complexity in implementation
- ❌ **Extra API calls**: Requires embedding each sentence for similarity comparison (costly at scale)

**Best for:** General-purpose document chunking

**Note:** While research-proven, this approach requires additional OpenAI API calls to embed every sentence for similarity calculation, which adds latency and cost. Not recommended unless dealing with unstructured documents where markdown headers are unavailable.

---

### Option 4: Hybrid Adaptive Strategy (Recommended)

**Approach:**
Combine multiple strategies based on content type:

```python
def adaptive_chunk_strategy(content: str, content_type: str) -> List[str]:
    """
    Adaptive chunking based on content characteristics
    """
    word_count = count_words(content)
    
    # Short content: No chunking needed
    if word_count < 400:
        return [content]
    
    # Markdown content with headers
    if has_markdown_headers(content):
        if word_count < 6000:
            return [content]  # Store whole
        else:
            return hierarchical_markdown_split(content, max_words=500)
    
    # Long unstructured content
    elif word_count > 2000:
        return semantic_sentence_split(content, max_words=500)
    
    # Medium unstructured content
    else:
        return sentence_split_with_overlap(content, max_words=500, overlap=50)
```

**Pros:**
- ✅ Best of all approaches
- ✅ Handles all content types
- ✅ Optimal for each scenario
- ✅ Future-proof

**Cons:**
- ⚠️ Most complex implementation
- ⚠️ Requires multiple chunking utilities

---

## Comparison Matrix

| Strategy | Semantic Coherence | Chunk Size Consistency | Implementation Complexity | Works for All Content | Research-Backed |
|----------|-------------------|----------------------|--------------------------|---------------------|-----------------|
| **Current (Fixed 900 chars)** | ❌ Poor | ✅ Excellent | ✅ Simple | ✅ Yes | ❌ No |
| **Option 1: Markdown Headers** | ✅ Good | ⚠️ Variable | ✅ Simple | ⚠️ Markdown only | ⚠️ Partial |
| **Option 2: Hierarchical Markdown** | ✅ Excellent | ✅ Good | ⚠️ Moderate | ⚠️ Markdown only | ✅ Yes |
| **Option 3: Semantic Sentences** | ✅ Excellent | ✅ Good | ⚠️ Complex | ✅ Yes | ✅ Yes |
| **Option 4: Hybrid Adaptive** | ✅ Excellent | ✅ Excellent | ❌ Complex | ✅ Yes | ✅ Yes |

---

## Research Findings

### Best Practices from Industry Leaders

**From LlamaIndex Study:**
- Optimal chunk size: **512-1024 tokens** (~400-800 words)
- Chunk overlap: **10-20%** of chunk size
- **Semantic splitting outperforms** fixed-size splitting
- Larger chunks (1024) showed **best faithfulness scores**

**From Pinecone Research:**
- **Sentence-based chunking** preferred over character-based
- **Recursive splitting** with separators: `["\n\n", "\n", ". ", " ", ""]`
- **Context expansion** at query time improves results

**From Anthropic (Contextual Retrieval):**
- Add **contextual headers** to each chunk
- Example: "This section from 'AgenticRAG Documentation' discusses..."
- Improves retrieval accuracy by **35%**

---

## Recommended Implementation Plan

### ✅ **Recommended: Option 2 - Hierarchical Markdown Splitting**

**Why Option 2?**
- ✅ Balances semantic coherence with size control
- ✅ Handles edge cases (oversized sections)
- ✅ No extra API calls (unlike Option 3)
- ✅ Production-ready with reasonable complexity
- ✅ Works well for LLM-generated markdown content

**Implementation Timeline: 1 week**

**Changes:**
1. **Update system prompts** to request markdown format (storage only, not for reasoning)
2. **Install markdown parser** (`pip install markdown-it-py`)
3. **Implement hierarchical splitting** with size constraints:
   - Primary split: `##` (H2 headers)
   - Secondary split: `###` (H3 headers) if section too large
   - Fallback: Sentence-based split for oversized subsections
4. **Add context preservation** (include parent headers in chunks)
5. **Add token counting** with `tiktoken` for safety
6. **Implement validation** to ensure chunks fit within embedding limits

**Code Locations:**
- `services/api-service/utils/chunk.py` - New hierarchical chunking functions
- `services/api-service/main.py` - Update answer storage logic
- `services/api-service/agentic/prompts.py` - Update prompts (post-generation formatting)
- `services/vector-service/main.py` - Add token validation

**Benefits:**
- Handles edge cases (huge sections split into smaller chunks)
- More consistent chunk sizes (400-800 words)
- Better retrieval quality (semantic sections preserved)
- No additional API costs

**Risk:** Low | **Effort:** Medium (1 week) | **Impact:** High

---

### Alternative: Option 3 (Not Recommended for Initial Implementation)

**Why not Option 3?**
- ❌ **Requires extra API calls** for embedding each sentence
- ❌ Higher latency and cost at scale
- ❌ More complex implementation
- ⚠️ Only necessary for unstructured content without markdown

**When to consider Option 3:**
- If markdown format proves unreliable
- For processing external documents (PDFs, emails, etc.)
- As a future enhancement for specific use cases

**Note:** Keep Option 3 as a **future enhancement** for document ingestion, not for LLM answer chunking

---

## Implementation Details

### Phase 1 Code Sketch

```python
# services/api-service/utils/chunk.py

import re
from typing import List

def chunk_markdown_by_headers(
    text: str,
    max_words: int = 6000,
    header_level: str = "##"
) -> List[str]:
    """
    Split markdown text by headers if content exceeds max_words
    
    Args:
        text: Markdown formatted text
        max_words: Word threshold for splitting
        header_level: Markdown header level to split on (default: ##)
    
    Returns:
        List of text chunks
    """
    word_count = len(text.split())
    
    # Short content: no splitting
    if word_count < max_words:
        return [text]
    
    # Split by H2 headers
    pattern = re.compile(f'^{header_level} .+$', re.MULTILINE)
    splits = pattern.split(text)
    headers = pattern.findall(text)
    
    # Reconstruct chunks with headers
    chunks = []
    for i, split in enumerate(splits):
        if split.strip():  # Skip empty splits
            if i < len(headers):
                chunk = f"{headers[i]}\n{split.strip()}"
            else:
                chunk = split.strip()
            chunks.append(chunk)
    
    return chunks if chunks else [text]


def adaptive_chunk_text(
    text: str,
    content_type: str = "answer",  # "answer" or "document"
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> List[str]:
    """
    Adaptive chunking based on content type and characteristics
    """
    # Short content
    if len(text) <= chunk_size:
        return [text]
    
    # LLM answers: Try markdown splitting first
    if content_type == "answer" and "##" in text:
        return chunk_markdown_by_headers(text, max_words=6000)
    
    # Fallback to existing recursive chunking
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
```

### Update System Prompts

**Important:** Markdown formatting should be requested as a **post-processing instruction**, NOT as a reasoning constraint.

```python
# services/api-service/agentic/prompts.py

ANSWER_SYSTEM_PROMPT = """
You are a helpful AI assistant in a Second Brain system.

{context}

Generate a comprehensive, well-structured answer based on the above context.

IMPORTANT - FORMATTING INSTRUCTION (for storage purposes only):
After generating your complete answer, format it in clean markdown structure:
- Use ## for main topic sections (if answer is long)
- Use ### for subsections where appropriate
- Use bullet points and numbered lists for clarity
- Use **bold** and *italic* for emphasis
- Use code blocks for code examples

Note: This formatting is for better storage and retrieval. Focus on accuracy and completeness first.
"""

# Alternative approach: Apply markdown formatting in a separate step
def format_answer_for_storage(answer: str) -> str:
    """
    Optional: Use a separate LLM call to format the answer in markdown
    This completely separates reasoning from formatting
    """
    formatting_prompt = f"""
Format the following answer in clean markdown with appropriate headers.
Do not change the content, only add markdown formatting.

Answer:
{answer}

Return the formatted version.
"""
    # Make separate LLM call for formatting only
    return format_with_llm(formatting_prompt)
```

### Update Storage Logic

```python
# services/api-service/main.py

from utils.chunk import adaptive_chunk_text

# In the answer storage section:
try:
    # Use adaptive chunking for answers
    chunks = adaptive_chunk_text(
        content=f"Q: {request.user_input}\nA: {summary}",
        content_type="answer"  # Signal this is an LLM answer
    )
    
    chunk_total = len(chunks)
    concepts = []
    base_id = f"qa_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{user.id[:8]}"
    
    for idx, chunk in enumerate(chunks):
        concepts.append({
            "id": f"{base_id}_c{idx}",
            "content": chunk,
            "type": "qa_concept",
            "metadata": {
                "user_id": user.id,
                "question": request.user_input,
                "summary": summary,
                "chunk_index": idx,
                "chunk_total": chunk_total,
                "chunking_method": "adaptive_markdown",  # Track method used
            }
        })
```

---

## Evaluation Metrics

To measure improvement, track these metrics:

### 1. Chunk Quality Metrics
- **Average chunk size** (words/tokens)
- **Chunk size variance** (lower is better)
- **Chunks per answer** (lower is better for short answers)

### 2. Retrieval Quality Metrics
- **Chunk Attribution Rate**: % of retrieved chunks used in final answer
- **Chunk Utilization**: Fraction of chunk text that influenced response
- **Answer Completeness**: Can full context be retrieved?

### 3. Performance Metrics
- **Storage cost** (number of vectors)
- **Retrieval latency**
- **Embedding API costs**

---

## Migration Strategy

### Option A: Gradual Migration
- Deploy new chunking for **new content only**
- Keep existing chunks unchanged
- Slowly improves over time as new Q&A added

**Pros:** Zero downtime, no migrations
**Cons:** Inconsistent chunking across content

### Option B: Full Re-indexing
- Re-chunk all existing Q&A in `prompt_logs` table
- Rebuild Qdrant index
- Clear old vectors, insert new ones

**Pros:** Consistent chunking strategy
**Cons:** Downtime required, computational cost

### Recommended: **Option A** initially, then **Option B** when strategy is proven

---

## Testing Plan

### Unit Tests
```python
def test_markdown_chunking_short_content():
    text = "Short answer without headers"
    chunks = chunk_markdown_by_headers(text)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_markdown_chunking_long_content():
    text = """
    ## Introduction
    """ + ("word " * 4000) + """
    ## Details
    """ + ("word " * 3000)
    chunks = chunk_markdown_by_headers(text, max_words=6000)
    assert len(chunks) == 2
    assert all("##" in chunk for chunk in chunks)

def test_adaptive_fallback():
    # No markdown headers
    text = "Long text without structure. " * 500
    chunks = adaptive_chunk_text(text, content_type="answer")
    assert len(chunks) > 1  # Should fall back to recursive splitting
```

### Integration Tests
- Store answer with markdown format
- Retrieve and verify chunk quality
- Test with various answer lengths
- Verify embedding within token limits

---

## Rollout Timeline

### Recommended: Direct Implementation of Option 2

| Phase | Duration | Deliverables |
|-------|----------|-------------|
| **Implementation** | 1 week | Hierarchical markdown splitting with size constraints |
| **Testing & Validation** | 3 days | Unit tests, integration tests, metrics collection |
| **Deployment** | 1 day | Deploy to production with gradual rollout |
| **Monitoring** | Ongoing | Track chunk quality metrics, retrieval performance |
| **Migration (Optional)** | 1 week | Re-index existing content if needed |

**Total Time:** ~2 weeks including testing

### Future Enhancements (Optional)

| Enhancement | Estimated Effort | When to Consider |
|-------------|-----------------|------------------|
| **Option 3: Semantic Splitting** | 2 weeks | For document ingestion (PDFs, docs) |
| **Option 4: Hybrid Strategy** | 3 weeks | When handling diverse content types |
| **Contextual Headers** | 1 week | To improve retrieval accuracy by 30%+ |
| **Chunk Quality Dashboard** | 1 week | For ongoing optimization |

---

## Success Criteria

✅ **Must Have:**
- Reduce average chunks per short answer (<1000 words) by 50%
- No mid-sentence splits in markdown-formatted content
- Zero embedding API failures due to oversized chunks

✅ **Should Have:**
- Improve chunk attribution rate by 20%
- Reduce chunk utilization waste by 30%
- Maintain or improve retrieval quality

✅ **Nice to Have:**
- Reduce total vector count by 20%
- Automatic chunk quality monitoring dashboard

---

## Risks & Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|-----------|------------|
| LLMs don't follow markdown format | High | Medium | Add format validation & retry logic |
| Chunks exceed embedding limits | High | Low | Implement token counting + truncation |
| Retrieval quality degrades | High | Low | A/B test with metrics before full rollout |
| Complex implementation bugs | Medium | Medium | Comprehensive testing + gradual rollout |
| Performance degradation | Medium | Low | Benchmark and optimize critical paths |

---

## Conclusion

### ✅ **Recommendation: Implement Option 2 (Hierarchical Markdown Splitting)**

**Verdict:** Your idea of using markdown headers for semantic chunking is **excellent** and aligns with best practices. We recommend implementing **Option 2** directly:

**Why Option 2?**
1. ✅ **Semantic coherence** - Preserves complete thoughts/sections
2. ✅ **Size control** - Prevents oversized chunks via hierarchical splitting
3. ✅ **No extra API costs** - Unlike semantic sentence splitting (Option 3)
4. ✅ **Production-ready** - Handles edge cases from day one
5. ✅ **Separation of concerns** - Markdown is for storage, not reasoning

### Key Design Principles

1. **Markdown for Storage Only**
   - Answer generation should focus on accuracy and completeness
   - Markdown formatting applied post-generation (or as light instruction)
   - This prevents markdown structure from influencing reasoning

2. **Hierarchical Fallback**
   - Split by H2 (`##`) first
   - If section too large → split by H3 (`###`)
   - If still too large → sentence-based split
   - Always preserve context with parent headers

3. **No Extra API Calls**
   - Option 3 (semantic similarity) requires embedding every sentence
   - Our approach: zero extra embeddings for chunking logic
   - Cost-effective at scale

### Next Steps

1. ✅ **Approve implementation plan** for Option 2
2. 🔧 **Implement hierarchical chunking** (~1 week)
3. 📝 **Update system prompts** (post-generation markdown formatting)
4. 🧪 **Test with real data** (metrics collection)
5. 🚀 **Deploy with gradual rollout** (new content first)
6. 📊 **Monitor & optimize** based on retrieval performance

### Estimated Impact

- 📉 **50-70% reduction** in unnecessary chunks for short answers
- 📈 **30-40% improvement** in retrieval relevance (semantic sections)
- ⚡ **No latency increase** (no extra API calls)
- 💰 **Cost neutral** (same number of embeddings, better quality)
- ✅ **Better user experience** with coherent, complete context retrieval

### Future Enhancements

**Later (if needed):**
- **Option 3 (Semantic splitting)**: For document ingestion only
- **Option 4 (Hybrid strategy)**: When handling diverse content types
- **Contextual headers**: Add document context to each chunk (Anthropic pattern)

**Ready to implement?** Option 2 provides the best balance of quality, cost, and complexity for LLM answer chunking.
