"""
Pinecone Vector Database Client for InsureGPT.
Manages vector indexing, upserts, queries, and metadata filtering.
"""
import logging
from typing import List, Dict, Any, Optional
from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from pinecone import Pinecone
    PINECONE_AVAILABLE = True
except ImportError:
    PINECONE_AVAILABLE = False
    Pinecone = None


class PineconeVectorClient:
    """Manages Pinecone index lifecycle, embeddings, and vector operations."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        namespace: Optional[str] = None
    ):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.pinecone_api_key
        self.index_name = index_name or self.settings.pinecone_index_name
        self.namespace = namespace or self.settings.pinecone_namespace

        self.pc: Optional[Pinecone] = None
        self.index = None

        if PINECONE_AVAILABLE and self.api_key and not self.api_key.startswith("dummy_"):
            try:
                self.pc = Pinecone(api_key=self.api_key)
                self.index = self.pc.Index(self.index_name)
            except Exception as e:
                logger.warning(f"Pinecone initialization failed: {e}")

    def embed_query(self, query: str) -> List[float]:
        """Generate 1024-d embedding for query using Pinecone Inference."""
        if not self.pc or not query or not query.strip():
            return []
        try:
            embs = self.pc.inference.embed(
                model="multilingual-e5-large",
                inputs=[query.strip()],
                parameters={"input_type": "query"}
            )
            return embs[0].values
        except Exception as e:
            logger.error(f"Pinecone query embedding failed: {e}")
            return []

    def query_vectors(
        self,
        vector: List[float],
        top_k: int = 8,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query nearest neighbor vectors with metadata filtering."""
        if not self.index or not vector:
            return []
        try:
            res = self.index.query(
                vector=vector,
                top_k=top_k,
                filter=filter_metadata,
                include_metadata=True,
                namespace=self.namespace
            )
            matches = []
            for m in res.matches:
                matches.append({
                    "id": m.id,
                    "score": m.score,
                    "metadata": m.metadata or {}
                })
            return matches
        except Exception as e:
            logger.error(f"Pinecone query failed: {e}")
            return []
