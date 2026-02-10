"""
Advanced text chunking with hierarchical markdown splitting.

Implements Option 2 from CHUNKING_IMPROVEMENT_PLAN.md:
- Hierarchical markdown splitting for semantic coherence
- Token counting for embedding limit safety
- Adaptive strategy based on content type and structure
"""
from typing import List, Tuple, Optional
import re
import logging
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Configure logging
logger = logging.getLogger(__name__)

try:
    import tiktoken
    TIKTOKEN_AVAILABLE = True
except ImportError:
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available - using approximate token counting")


# Constants
MAX_EMBEDDING_TOKENS = 8191  # OpenAI text-embedding-ada-002 limit
DEFAULT_MAX_WORDS = 6000  # Threshold for splitting answers
DEFAULT_CHUNK_MAX_WORDS = 500  # Target chunk size in words
DEFAULT_CHUNK_SIZE_CHARS = 900  # Fallback character-based chunk size
DEFAULT_OVERLAP = 150  # Character overlap for context continuity


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """
    Count tokens in text using tiktoken for accurate token counting.
    
    Args:
        text: Text to count tokens for
        model: Tiktoken encoding model (default: cl100k_base for ada-002)
    
    Returns:
        Number of tokens in the text
    """
    if not TIKTOKEN_AVAILABLE:
        # Fallback: rough estimation (1 token ≈ 4 characters)
        return len(text) // 4
    
    try:
        encoding = tiktoken.get_encoding(model)
        return len(encoding.encode(text))
    except Exception:
        # Fallback to character-based estimation
        return len(text) // 4


def count_words(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def parse_markdown_headers(text: str, level: int = 2) -> List[Tuple[str, int, int]]:
    """
    Parse markdown headers at a specific level.
    
    Args:
        text: Markdown text to parse
        level: Header level to extract (2 for ##, 3 for ###)
    
    Returns:
        List of tuples: (header_text, start_pos, end_pos)
    """
    header_pattern = re.compile(rf'^#{{{level}}}\s+(.+)$', re.MULTILINE)
    headers = []
    
    for match in header_pattern.finditer(text):
        headers.append((
            match.group(0),  # Full header line including ##
            match.start(),   # Start position
            match.end()      # End position
        ))
    
    return headers


def split_by_header_level(text: str, level: int = 2) -> List[str]:
    """
    Split text by markdown headers at a specific level.
    
    Args:
        text: Markdown text to split
        level: Header level to split on (2 for ##, 3 for ###)
    
    Returns:
        List of text chunks, each starting with a header (except maybe first)
    """
    headers = parse_markdown_headers(text, level)
    
    if not headers:
        return [text]
    
    chunks = []
    
    # Handle content before first header
    if headers[0][1] > 0:
        chunks.append(text[:headers[0][1]].strip())
    
    # Split by headers
    for i, (header, start, end) in enumerate(headers):
        # Get content from this header to next header (or end)
        if i < len(headers) - 1:
            next_start = headers[i + 1][1]
            chunk = text[start:next_start].strip()
        else:
            chunk = text[start:].strip()
        
        if chunk:
            chunks.append(chunk)
    
    return [c for c in chunks if c]  # Filter empty chunks


def split_by_sentences(text: str, max_words: int = DEFAULT_CHUNK_MAX_WORDS) -> List[str]:
    """
    Split text by sentences with word count constraints.
    
    Args:
        text: Text to split
        max_words: Maximum words per chunk
    
    Returns:
        List of sentence-based chunks
    """
    # Split by sentence boundaries
    sentence_pattern = re.compile(r'(?<=[.!?])\s+(?=[A-Z])')
    sentences = sentence_pattern.split(text)
    
    if not sentences:
        return [text]
    
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    for sentence in sentences:
        sentence_words = count_words(sentence)
        
        # If single sentence exceeds max, add it as its own chunk
        if sentence_words > max_words:
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            chunks.append(sentence)
            continue
        
        # If adding this sentence would exceed max, start new chunk
        if current_word_count + sentence_words > max_words and current_chunk:
            chunks.append(' '.join(current_chunk))
            current_chunk = [sentence]
            current_word_count = sentence_words
        else:
            current_chunk.append(sentence)
            current_word_count += sentence_words
    
    # Add remaining sentences
    if current_chunk:
        chunks.append(' '.join(current_chunk))
    
    return chunks


def hierarchical_markdown_chunk(
    text: str,
    max_words: int = DEFAULT_CHUNK_MAX_WORDS,
    max_tokens: int = MAX_EMBEDDING_TOKENS,
    parent_header: Optional[str] = None
) -> List[str]:
    """
    Hierarchical markdown chunking with size constraints.
    
    Strategy:
    1. Split by H2 (##) headers first
    2. If section > max_words, split by H3 (###) headers
    3. If still too large, split by sentences
    4. Preserve parent headers for context
    
    Args:
        text: Markdown text to chunk
        max_words: Maximum words per chunk
        max_tokens: Maximum tokens per chunk (for embedding safety)
        parent_header: Parent section header for context preservation
    
    Returns:
        List of text chunks with semantic coherence
    """
    if not text or not text.strip():
        return []
    
    word_count = count_words(text)
    token_count = count_tokens(text)
    
    # Short content: no splitting needed
    if word_count <= max_words:
        # Still validate token count
        if token_count <= max_tokens:
            logger.debug(
                f"📊 No chunking needed: {word_count} words, {token_count} tokens "
                f"(limits: {max_words} words, {max_tokens} tokens)"
            )
            return [text]
    
    logger.debug(
        f"📊 Starting hierarchical chunking: {word_count} words, {token_count} tokens"
    )
    
    # Try splitting by H2 headers
    h2_sections = split_by_header_level(text, level=2)
    
    if len(h2_sections) > 1:
        # Successfully split by H2
        logger.debug(f"✂️ Split by H2 headers: {len(h2_sections)} sections")
        chunks = []
        h3_splits = 0
        sentence_splits = 0
        
        for section in h2_sections:
            section_words = count_words(section)
            
            if section_words <= max_words and count_tokens(section) <= max_tokens:
                # Section fits in one chunk
                chunks.append(section)
            else:
                # Section too large: try H3 split
                h3_sections = split_by_header_level(section, level=3)
                
                if len(h3_sections) > 1:
                    # Successfully split by H3
                    h3_splits += 1
                    for subsection in h3_sections:
                        subsection_words = count_words(subsection)
                        
                        if subsection_words <= max_words and count_tokens(subsection) <= max_tokens:
                            chunks.append(subsection)
                        else:
                            # Still too large: sentence-based split
                            sentence_splits += 1
                            sentence_chunks = split_by_sentences(subsection, max_words)
                            chunks.extend(sentence_chunks)
                else:
                    # No H3 headers: fallback to sentence split
                    sentence_splits += 1
                    sentence_chunks = split_by_sentences(section, max_words)
                    chunks.extend(sentence_chunks)
        
        logger.info(
            f"✅ Hierarchical chunking complete: {len(chunks)} chunks created "
            f"(H2 splits: {len(h2_sections)}, H3 splits: {h3_splits}, sentence splits: {sentence_splits})"
        )
        _log_chunk_metrics(chunks)
        return chunks
    
    # No H2 headers found: try H3 headers
    h3_sections = split_by_header_level(text, level=3)
    
    if len(h3_sections) > 1:
        logger.debug(f"✂️ Split by H3 headers: {len(h3_sections)} sections")
        chunks = []
        for section in h3_sections:
            if count_words(section) <= max_words and count_tokens(section) <= max_tokens:
                chunks.append(section)
            else:
                sentence_chunks = split_by_sentences(section, max_words)
                chunks.extend(sentence_chunks)
        logger.info(f"✅ H3 chunking complete: {len(chunks)} chunks created")
        _log_chunk_metrics(chunks)
        return chunks
    
    # No headers at all: sentence-based split
    logger.debug("⚠️ No markdown headers found, using sentence-based fallback")
    chunks = split_by_sentences(text, max_words)
    logger.info(f"✅ Sentence-based chunking complete: {len(chunks)} chunks created")
    _log_chunk_metrics(chunks)
    return chunks


def adaptive_chunk_text(
    text: str,
    content_type: str = "answer",
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    chunk_overlap: int = DEFAULT_OVERLAP,
    max_words_before_split: int = DEFAULT_MAX_WORDS,
    chunk_target_words: int = DEFAULT_CHUNK_MAX_WORDS,
) -> List[str]:
    """
    Adaptive chunking based on content type and characteristics.
    
    This is the main entry point for chunking, providing backward compatibility
    with the old chunk_text() function while enabling hierarchical markdown splitting.
    
    Args:
        text: Text to chunk
        content_type: Type of content ("answer" for LLM responses, "document" for other)
        chunk_size: Character-based chunk size for fallback
        chunk_overlap: Character overlap for fallback chunking
        max_words_before_split: Word count threshold for splitting answers
        chunk_target_words: Target words per chunk in hierarchical splitting
    
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    word_count = count_words(text)
    text_length = len(text)
    
    # Very short content: no chunking needed
    if text_length <= chunk_size and word_count < chunk_target_words:
        logger.debug(f"📊 Short content, no chunking: {word_count} words, {text_length} chars")
        return [text]
    
    # LLM answers with markdown structure: use hierarchical splitting
    if content_type == "answer" and ("##" in text or "###" in text):
        logger.debug(
            f"📝 Processing answer with markdown structure: {word_count} words, content_type={content_type}"
        )
        
        # Short answers: store whole (no splitting)
        if word_count < max_words_before_split:
            # Validate token count for safety
            token_count = count_tokens(text)
            if token_count <= MAX_EMBEDDING_TOKENS:
                logger.info(
                    f"✅ Storing short answer as single chunk: {word_count} words, "
                    f"{token_count} tokens (threshold: {max_words_before_split} words)"
                )
                return [text]
            else:
                logger.warning(
                    f"⚠️ Short answer exceeds token limit ({token_count} > {MAX_EMBEDDING_TOKENS}), "
                    f"forcing hierarchical split"
                )
        
        # Long answers: hierarchical markdown split
        logger.info(f"✂️ Using hierarchical markdown chunking for long answer ({word_count} words)")
        chunks = hierarchical_markdown_chunk(
            text,
            max_words=chunk_target_words,
            max_tokens=MAX_EMBEDDING_TOKENS
        )
        return chunks
    
    # Fallback to recursive character splitting for unstructured content
    logger.info(
        f"📄 Using fallback recursive chunking: content_type={content_type}, "
        f"word_count={word_count}, has_markdown={'##' in text}"
    )
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(text)
    logger.info(f"✅ Recursive chunking complete: {len(chunks)} chunks created")
    _log_chunk_metrics(chunks)
    return chunks


def _log_chunk_metrics(chunks: List[str]) -> None:
    """
    Log metrics about chunk quality for monitoring.
    
    Args:
        chunks: List of text chunks to analyze
    """
    if not chunks:
        return
    
    chunk_word_counts = [count_words(chunk) for chunk in chunks]
    chunk_token_counts = [count_tokens(chunk) for chunk in chunks]
    
    avg_words = sum(chunk_word_counts) / len(chunk_word_counts)
    avg_tokens = sum(chunk_token_counts) / len(chunk_token_counts)
    max_words = max(chunk_word_counts)
    max_tokens = max(chunk_token_counts)
    min_words = min(chunk_word_counts)
    min_tokens = min(chunk_token_counts)
    
    # Calculate variance (simplified std dev)
    word_variance = sum((w - avg_words) ** 2 for w in chunk_word_counts) / len(chunk_word_counts)
    
    logger.debug(
        f"📊 Chunk metrics: count={len(chunks)}, "
        f"avg_words={avg_words:.1f} (min={min_words}, max={max_words}), "
        f"avg_tokens={avg_tokens:.1f} (min={min_tokens}, max={max_tokens}), "
        f"word_variance={word_variance:.1f}"
    )


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE_CHARS,
    chunk_overlap: int = DEFAULT_OVERLAP,
) -> List[str]:
    """
    Legacy chunking function for backward compatibility.
    
    This maintains the original API but delegates to adaptive_chunk_text
    with sensible defaults.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum characters per chunk
        chunk_overlap: Character overlap between chunks
    
    Returns:
        List of text chunks
    """
    return adaptive_chunk_text(
        text=text,
        content_type="document",  # Use fallback recursive splitting
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
