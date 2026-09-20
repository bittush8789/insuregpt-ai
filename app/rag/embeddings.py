"""
Embeddings Integration Module for InsureGPT.
Wraps dense and sparse embedding models using LangChain in Phase 2.
"""
from typing import List


class EmbeddingService:
    """Generates dense vector representations for insurance queries and chunks."""

    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.model_name = model_name

    def embed_query(self, text: str) -> List[float]:
        """Generate embedding vector for a user query."""
        return []

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate embedding vectors for document chunks."""
        return []
