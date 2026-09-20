"""
Hybrid Retriever and Evidence Reranker Module for InsureGPT.
Coordinates dense semantic retrieval via Pinecone, local knowledge base fallback, and strict grounding.
"""
import os
import re
import logging
from typing import List, Dict, Any, Optional

from app.config import get_settings
from app.vectorstore.pinecone_client import PineconeVectorClient

logger = logging.getLogger(__name__)


class HybridInsuranceRetriever:
    """Retrieves grounded policy evidence chunks from Pinecone with local knowledge base fallback."""

    def __init__(self, top_k: int = 8, rerank_k: int = 4):
        self.settings = get_settings()
        self.top_k = top_k or self.settings.retrieval_k
        self.rerank_k = rerank_k or self.settings.rerank_top_k
        self.client = PineconeVectorClient()
        self.docs_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "data", "documents"
        )

    def retrieve_evidence(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve top-K evidence chunks from Pinecone vector store,
        with automatic fallback to local knowledge base documents if needed.
        """
        if not query or not query.strip():
            return []

        evidence_list = []

        # Step 1: Query Pinecone Vector Database
        try:
            query_vector = self.client.embed_query(query)
            if query_vector:
                matches = self.client.query_vectors(
                    vector=query_vector,
                    top_k=self.top_k,
                    filter_metadata=filters
                )
                for m in matches:
                    meta = m.get("metadata", {})
                    evidence_list.append({
                        "id": m.get("id"),
                        "score": float(m.get("score", 0.0)),
                        "policy_id": meta.get("policy_id", ""),
                        "section": meta.get("section", ""),
                        "filename": meta.get("filename", ""),
                        "text": meta.get("text", ""),
                        "source_type": "policy_rag"
                    })
        except Exception as e:
            logger.warning(f"Pinecone vector query encountered issue: {e}")

        # Step 2: Query Local Documents
        local_evidence = self._search_local_documents(query)
        for item in local_evidence:
            if not any(e.get("text") == item.get("text") for e in evidence_list):
                evidence_list.append(item)

        if not evidence_list:
            return []

        # Step 3: Hybrid Lexical & Section Reranking
        query_tokens = [t for t in re.findall(r"\w+", query.lower()) if len(t) > 2]

        def compute_rerank_score(item: Dict[str, Any]) -> float:
            sec = item.get("section", "").lower()
            txt = item.get("text", "").lower()
            header_hits = sum(3 for t in query_tokens if t in sec)
            body_hits = sum(1 for t in query_tokens if t in txt)
            lexical_score = (header_hits + body_hits) / (len(query_tokens) + 1) if query_tokens else 0.0
            dense_score = float(item.get("score", 0.5))
            return (dense_score * 0.4) + (lexical_score * 0.6)

        evidence_list.sort(key=compute_rerank_score, reverse=True)

        # Deduplicate overlapping chunks by text prefix
        seen_prefixes = set()
        deduped = []
        for cand in evidence_list:
            prefix = cand.get("text", "")[:60]
            if prefix not in seen_prefixes:
                seen_prefixes.add(prefix)
                deduped.append(cand)
            if len(deduped) >= self.rerank_k:
                break

        return deduped

    def _search_local_documents(self, query: str) -> List[Dict[str, Any]]:
        """Scan local documents in data/documents for keyword & clause relevance."""
        if not os.path.exists(self.docs_dir):
            return []

        query_tokens = set(re.findall(r"\w+", query.lower()))
        # Remove common stopwords
        stopwords = {"what", "is", "the", "in", "and", "of", "to", "a", "for", "are", "under", "does", "or", "how", "much", "covered"}
        meaningful_tokens = [t for t in query_tokens if t not in stopwords and len(t) > 2]

        if not meaningful_tokens:
            return []

        scored_chunks = []

        for fname in os.listdir(self.docs_dir):
            if not fname.endswith(".txt"):
                continue

            fpath = os.path.join(self.docs_dir, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Extract Policy ID
                pid_match = re.search(r"Policy Document ID:\s*([A-Z0-9\-]+)|Document ID:\s*([A-Z0-9\-]+)", content)
                policy_id = pid_match.group(1) or pid_match.group(2) if pid_match else fname.replace(".txt", "")

                # Split cleanly by lines starting with SECTION <number>
                sections = re.split(r"(?m)^(SECTION\s+\d+[^\r\n]*)", content)
                current_section = "General Overview"
                i = 0
                while i < len(sections):
                    part = sections[i].strip()
                    if not part:
                        i += 1
                        continue
                    if part.startswith("SECTION"):
                        current_section = part
                        body = sections[i + 1].strip() if i + 1 < len(sections) else ""
                        i += 2
                    else:
                        body = part
                        i += 1

                    # Clean divider lines
                    body = re.sub(r"^[-=]{5,}\s*", "", body)
                    body = re.sub(r"\s*[-=]{5,}$", "", body)
                    if not body:
                        continue

                    # Score clause: give extra weight if tokens match the section header
                    section_lower = current_section.lower()
                    body_lower = body.lower()
                    header_matches = sum(3 for token in meaningful_tokens if token in section_lower)
                    body_matches = sum(1 for token in meaningful_tokens if token in body_lower)
                    score = header_matches + body_matches

                    if score > 0 and len(body) > 40:
                        scored_chunks.append({
                            "id": f"{policy_id}#local_{len(scored_chunks)}",
                            "score": float(score) / (len(meaningful_tokens) + 1),
                            "policy_id": policy_id,
                            "section": current_section,
                            "filename": fname,
                            "text": body[:1800],
                            "source_type": "policy_rag"
                        })
            except Exception as e:
                logger.error(f"Error reading local document '{fname}': {e}")

        scored_chunks.sort(key=lambda x: x["score"], reverse=True)
        return scored_chunks[:self.rerank_k]
