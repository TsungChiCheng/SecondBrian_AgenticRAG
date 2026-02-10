#!/usr/bin/env python
"""
Quick smoke test for chunking implementation
"""
import sys
sys.path.insert(0, '.')

from utils.chunk import (
    count_words, 
    count_tokens,
    parse_markdown_headers,
    adaptive_chunk_text
)

print('🧪 Testing chunking implementation...\n')

# Test 1: Short content
print('Test 1: Short content (no split)')
text1 = 'This is a short answer.'
result1 = adaptive_chunk_text(text1, content_type='answer')
print(f'  Result: {len(result1)} chunk(s)')
assert len(result1) == 1
print('  ✅ PASS\n')

# Test 2: Long markdown with headers
print('Test 2: Long markdown (should split)')
text2 = '## Introduction\nThis is section 1.\n\n## Details\nThis is section 2.\n' + ('word ' * 7000)
result2 = adaptive_chunk_text(text2, content_type='answer')
print(f'  Result: {len(result2)} chunk(s)')
assert len(result2) > 1
print('  ✅ PASS\n')

# Test 3: Header parsing
print('Test 3: Header parsing')
text3 = '## Header1\nContent\n\n## Header2\nMore content'
headers = parse_markdown_headers(text3, level=2)
print(f'  Found: {len(headers)} headers')
assert len(headers) == 2
print('  ✅ PASS\n')

# Test 4: Counting
print('Test 4: Word/token counting')
text4 = 'one two three four five'
words = count_words(text4)
tokens = count_tokens(text4)
print(f'  Words: {words}, Tokens: {tokens}')
assert words == 5
print('  ✅ PASS\n')

print('🎉 All tests passed! Chunking implementation is working correctly.')
