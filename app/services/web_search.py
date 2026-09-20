"""
External Web Search Tool for InsureGPT using Tavily.
Retrieves public insurance regulations, IRDAI notifications, and external evidence.
Distinguishes external web evidence from internal policy RAG documents.
"""
import logging
import os
from typing import Any, Dict, List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)

try:
    from tavily import TavilyClient
    TAVILY_AVAILABLE = True
except ImportError:
    TAVILY_AVAILABLE = False
    TavilyClient = None


class WebSearchService:
    """Performs targeted external web searches using Tavily for insurance regulatory norms and market context."""

    def __init__(self, api_key: Optional[str] = None):
        self.settings = get_settings()
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.enabled = getattr(self.settings, "web_search_enabled", False)
        self.client: Optional[TavilyClient] = None

        if TAVILY_AVAILABLE and self.enabled and self.api_key and not self.api_key.startswith("dummy_"):
            try:
                self.client = TavilyClient(api_key=self.api_key)
            except Exception as e:
                logger.warning(f"Failed to initialize TavilyClient: {e}")

    def search(
        self,
        query: str,
        max_results: int = 3,
        search_depth: str = "basic",
        include_answer: bool = False,
        include_raw_content: bool = False,
        **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """
        Execute an external web search using Tavily.
        Returns a normalized list of evidence items flagged as source_type='web'.
        """
        if not self.enabled:
            logger.info("Web search is disabled in configuration.")
            return []

        if not self.client:
            logger.warning("Tavily client is not configured or valid API key is missing.")
            return []

        query_clean = query.strip() if query else ""
        if not query_clean:
            return []

        try:
            response = self.client.search(
                query=query_clean,
                max_results=max_results,
                search_depth=search_depth,
                include_answer=include_answer,
                include_raw_content=include_raw_content,
                **kwargs
            )
            raw_results = response.get("results", [])
            normalized_results: List[Dict[str, Any]] = []

            for item in raw_results:
                normalized_results.append({
                    "title": item.get("title", ""),
                    "url": item.get("url", ""),
                    "content": item.get("content", ""),
                    "score": item.get("score", 0.0),
                    "source_type": "web"
                })

            return normalized_results
        except Exception as e:
            logger.error(f"Tavily search execution failed: {e}")
            return []

    def get_search_context(self, query: str, max_results: int = 3, **kwargs: Any) -> str:
        """
        Fetch aggregated web search context formatted for prompt augmentation.
        Uses Tavily's native get_search_context or synthesizes from normalized results.
        """
        if not self.enabled or not self.client or not query or not query.strip():
            return ""

        try:
            if hasattr(self.client, "get_search_context"):
                return self.client.get_search_context(
                    query=query.strip(),
                    max_results=max_results,
                    **kwargs
                )
            results = self.search(query=query, max_results=max_results, **kwargs)
            return "\n\n".join([f"Source ({r['url']}):\n{r['content']}" for r in results])
        except Exception as e:
            logger.error(f"Tavily get_search_context failed: {e}")
            return ""

    def qna_search(self, query: str) -> str:
        """Execute a quick direct Q&A search via Tavily."""
        if not self.enabled or not self.client or not query or not query.strip():
            return ""

        try:
            return self.client.qna_search(query=query.strip())
        except Exception as e:
            logger.error(f"Tavily qna_search failed: {e}")
            return ""
