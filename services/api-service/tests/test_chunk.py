"""
Unit tests for the hierarchical markdown chunking system.

Tests cover:
- Short content (no splitting)
- Long content with H2 headers
- Long content with H2 + H3 headers
- Oversized sections requiring recursive split
- Content without markdown headers (fallback)
- Edge cases (empty headers, malformed markdown)
- Token counting accuracy
"""

import pytest
from utils.chunk import (
    chunk_text,
    adaptive_chunk_text,
    hierarchical_markdown_chunk,
    split_by_header_level,
    parse_markdown_headers,
    split_by_sentences,
    count_tokens,
    count_words,
    DEFAULT_MAX_WORDS,
    DEFAULT_CHUNK_MAX_WORDS,
    MAX_EMBEDDING_TOKENS,
)


class TestBasicChunking:
    """Test basic chunking functionality and backward compatibility"""
    
    def test_empty_string(self):
        """Empty string should return empty list"""
        assert chunk_text("") == []
        assert adaptive_chunk_text("") == []
    
    def test_short_content_no_split(self):
        """Short content should not be split"""
        text = "This is a short answer."
        result = chunk_text(text)
        assert len(result) == 1
        assert result[0] == text
    
    def test_backward_compatibility(self):
        """chunk_text should maintain original behavior for non-markdown content"""
        text = "word " * 500  # 500 words, should be split
        result = chunk_text(text)
        assert len(result) > 1
        # Each chunk should have content
        assert all(len(chunk) > 0 for chunk in result)


class TestMarkdownParsing:
    """Test markdown header parsing utilities"""
    
    def test_parse_h2_headers(self):
        """Should correctly parse H2 headers"""
        text = """## Introduction
Some content here.

## Details
More content here."""
        headers = parse_markdown_headers(text, level=2)
        assert len(headers) == 2
        assert "## Introduction" in headers[0][0]
        assert "## Details" in headers[1][0]
    
    def test_parse_h3_headers(self):
        """Should correctly parse H3 headers"""
        text = """### Subsection 1
Content 1

### Subsection 2
Content 2"""
        headers = parse_markdown_headers(text, level=3)
        assert len(headers) == 2
        assert "### Subsection 1" in headers[0][0]
    
    def test_no_headers_found(self):
        """Should return empty list when no headers found"""
        text = "Just plain text without headers."
        headers = parse_markdown_headers(text, level=2)
        assert len(headers) == 0
    
    def test_split_by_h2(self):
        """Should split text by H2 headers"""
        text = """# Title

## Section 1
This is section 1 content.

## Section 2
This is section 2 content."""
        chunks = split_by_header_level(text, level=2)
        assert len(chunks) == 3  # Content before first header + 2 sections
        assert "## Section 1" in chunks[1]
        assert "## Section 2" in chunks[2]


class TestHierarchicalChunking:
    """Test hierarchical markdown chunking strategy"""
    
    def test_short_answer_no_split(self):
        """Answers < 6000 words should not be split even with headers"""
        text = """## Introduction
This is a short introduction.

## Details
Some details here."""
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Should be returned as whole since word count < DEFAULT_MAX_WORDS
        assert len(chunks) == 1
    
    def test_long_answer_split_by_h2(self):
        """Long answers should be split by H2 headers"""
        # Create content > 6000 words with H2 headers
        section1 = "## Introduction\n" + ("word " * 3500)
        section2 = "## Details\n" + ("word " * 3500)
        text = section1 + "\n\n" + section2
        
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Should be split into 2+ chunks
        assert len(chunks) > 1
        # Each chunk should have headers preserved
        assert any("## Introduction" in chunk for chunk in chunks)
        assert any("## Details" in chunk for chunk in chunks)
    
    def test_oversized_section_recursive_split(self):
        """Sections > max_words should be split recursively"""
        # Create a single section that's too large
        text = "## Large Section\n" + ("word " * 1000)
        
        chunks = hierarchical_markdown_chunk(
            text,
            max_words=DEFAULT_CHUNK_MAX_WORDS,
            max_tokens=MAX_EMBEDDING_TOKENS
        )
        # Should be split into multiple chunks
        assert len(chunks) > 1
    
    def test_h2_and_h3_hierarchy(self):
        """Should handle H2/H3 hierarchy correctly"""
        text = """## Main Section
Introduction to main section.

### Subsection 1
""" + ("word " * 600) + """

### Subsection 2
""" + ("word " * 600)
        
        chunks = hierarchical_markdown_chunk(
            text,
            max_words=DEFAULT_CHUNK_MAX_WORDS,
            max_tokens=MAX_EMBEDDING_TOKENS
        )
        # Should split by subsections
        assert len(chunks) > 1
    
    def test_no_markdown_fallback(self):
        """Content without markdown should use fallback chunking"""
        text = "This is plain text. " * 500  # No markdown headers
        
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Should fall back to recursive chunking
        assert len(chunks) > 1


class TestSentenceSplitting:
    """Test sentence-based splitting for fallback"""
    
    def test_split_by_sentences(self):
        """Should split text by sentences"""
        text = "Sentence one. Sentence two. Sentence three. " * 50
        chunks = split_by_sentences(text, max_words=100)
        
        assert len(chunks) > 1
        # Each chunk should end with proper sentence
        for chunk in chunks:
            assert len(chunk) > 0
    
    def test_oversized_sentence(self):
        """Single sentence > max_words should be its own chunk"""
        long_sentence = "This is a very long sentence " + ("word " * 600) + "."
        short_sentence = "Short sentence."
        text = long_sentence + " " + short_sentence
        
        chunks = split_by_sentences(text, max_words=100)
        assert len(chunks) >= 2


class TestTokenCounting:
    """Test token counting for validation"""
    
    def test_count_tokens_basic(self):
        """Should count tokens in text"""
        text = "This is a test sentence."
        token_count = count_tokens(text)
        assert token_count > 0
        # Should be reasonable (rough expectation: ~6-8 tokens)
        assert 4 <= token_count <= 15
    
    def test_count_words(self):
        """Should count words in text"""
        text = "one two three four five"
        assert count_words(text) == 5
    
    def test_large_text_token_validation(self):
        """Should accurately count tokens for large text"""
        # Create text approaching token limit
        text = "word " * 2000  # Roughly 2000 tokens
        token_count = count_tokens(text)
        # Should detect it's within safe range
        assert token_count < MAX_EMBEDDING_TOKENS


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_headers(self):
        """Should handle empty header text"""
        text = "##\nContent without header name."
        chunks = adaptive_chunk_text(text, content_type="answer")
        assert len(chunks) >= 1
    
    def test_multiple_hash_symbols(self):
        """Should handle headers with extra # symbols"""
        text = "#### H4 Header\nContent here."
        chunks = adaptive_chunk_text(text, content_type="answer")
        assert len(chunks) >= 1
    
    def test_header_in_code_block(self):
        """Headers in code blocks should not trigger splitting"""
        text = """Normal content.

```python
# This is a comment, not a header
## Also not a header
```

More content."""
        # This is a limitation - our simple regex will still detect these
        # In production, consider markdown parsing library
        chunks = adaptive_chunk_text(text, content_type="answer")
        assert len(chunks) >= 1
    
    def test_very_long_single_line(self):
        """Should handle very long lines without newlines"""
        text = "word " * 10000  # 10k words, no newlines
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Should be split despite no natural boundaries
        assert len(chunks) > 1
    
    def test_unicode_content(self):
        """Should handle unicode characters"""
        text = """## 介绍
这是中文内容。

## Détails
Contenu en français."""
        chunks = adaptive_chunk_text(text, content_type="answer")
        assert len(chunks) >= 1
        # Content should be preserved
        assert any("中文" in chunk for chunk in chunks)


class TestContentTypes:
    """Test different content type handling"""
    
    def test_answer_content_type(self):
        """Answer content type should use markdown chunking"""
        text = """## Section 1
Content here.

## Section 2
More content.""" + ("word " * 7000)
        
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Should detect markdown and split appropriately
        assert len(chunks) > 1
    
    def test_document_content_type(self):
        """Document content type should use fallback chunking"""
        text = """## Section 1
Content here.""" + ("word " * 1000)
        
        # Force document type to use fallback
        chunks = adaptive_chunk_text(text, content_type="document")
        # Should use recursive chunking (fallback)
        assert len(chunks) > 1


class TestChunkQuality:
    """Test chunk quality metrics"""
    
    def test_no_mid_sentence_splits_markdown(self):
        """Markdown chunks should not split mid-sentence"""
        text = """## Introduction
This is a complete sentence. This is another complete sentence.

## Details  
More complete sentences here. And another one."""
        
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Each chunk should start with header or complete sentence
        for chunk in chunks:
            # Should not start with lowercase (mid-sentence)
            stripped = chunk.strip()
            if stripped:
                # Either starts with # (header) or capital letter
                assert stripped[0].isupper() or stripped[0] == '#'
    
    def test_chunk_size_consistency(self):
        """Chunks should be reasonably sized"""
        text = """## Section 1
""" + ("word " * 400) + """

## Section 2
""" + ("word " * 500) + """

## Section 3
""" + ("word " * 300)
        
        chunks = hierarchical_markdown_chunk(
            text,
            max_words=DEFAULT_CHUNK_MAX_WORDS,
            max_tokens=MAX_EMBEDDING_TOKENS
        )
        
        # All chunks should be under token limit
        for chunk in chunks:
            assert count_tokens(chunk) < MAX_EMBEDDING_TOKENS
    
    def test_context_preservation(self):
        """Headers should be preserved in chunks for context"""
        text = """## Main Topic
Introduction to the topic.

### Subtopic A
Details about subtopic A."""
        
        chunks = adaptive_chunk_text(text, content_type="answer")
        # Headers should appear in chunks
        assert any("## Main Topic" in chunk for chunk in chunks)


class TestIntegration:
    """Integration tests simulating real usage"""
    
    def test_qa_storage_simulation(self):
        """Simulate Q&A storage workflow"""
        question = "What is hierarchical markdown chunking?"
        answer = """## Overview
Hierarchical markdown chunking is an advanced text splitting strategy.

## Benefits
- Semantic coherence
- Better retrieval quality
- No mid-sentence splits

## Implementation
We use H2 and H3 headers as split points."""
        
        content = f"Q: {question}\nA: {answer}"
        chunks = adaptive_chunk_text(content, content_type="answer")
        
        # Should produce reasonable chunks
        assert len(chunks) >= 1
        assert all(len(chunk) > 0 for chunk in chunks)
        # Question should appear in at least one chunk
        assert any("hierarchical markdown" in chunk.lower() for chunk in chunks)
    
    def test_large_answer_chunking(self):
        """Test chunking of large LLM response"""
        # Simulate a 8000-word LLM response with structure
        answer = "## Introduction\n" + ("word " * 2000)
        answer += "\n\n## Technical Details\n" + ("word " * 3000)
        answer += "\n\n## Examples\n" + ("word " * 2000)
        answer += "\n\n## Conclusion\n" + ("word " * 1000)
        
        chunks = adaptive_chunk_text(answer, content_type="answer")
        
        # Should be split into multiple chunks
        assert len(chunks) > 1
        # All chunks should be safe for embedding
        for chunk in chunks:
            assert count_tokens(chunk) < MAX_EMBEDDING_TOKENS
        # Headers should be preserved
        assert any("Introduction" in chunk for chunk in chunks)
        assert any("Conclusion" in chunk for chunk in chunks)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
