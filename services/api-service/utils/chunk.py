"""
Lightweight text chunking helper for vector upserts.
Uses RecursiveCharacterTextSplitter to handle arbitrary, unstructured text.
"""
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter


def chunk_text(
    text: str,
    chunk_size: int = 900,
    chunk_overlap: int = 150,
) -> List[str]:
    """Split text into overlapping chunks. Returns the original text if short."""
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_text(text)
