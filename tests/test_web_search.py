"""
Unit Tests for WebSearchService with Tavily Integration.
"""
from unittest.mock import MagicMock, patch
import pytest

from app.services.web_search import WebSearchService


def test_web_search_unconfigured_or_dummy_key():
    """Verify that WebSearchService safely returns empty results without crashing when dummy key or missing key."""
    service = WebSearchService(api_key="dummy_key_for_phase1")
    assert service.client is None
    results = service.search("IRDAI guidelines for cashless health insurance 2026")
    assert results == []
    assert service.get_search_context("test query") == ""
    assert service.qna_search("test query") == ""


def test_web_search_disabled():
    """Verify that WebSearchService returns empty results when disabled."""
    service = WebSearchService(api_key="tvly-actual-key")
    service.enabled = False
    results = service.search("IRDAI guidelines")
    assert results == []


def test_web_search_with_mocked_tavily():
    """Verify that Tavily search returns normalized results with source_type='web'."""
    with patch("app.services.web_search.TavilyClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        mock_instance.search.return_value = {
            "query": "IRDAI health insurance regulations",
            "results": [
                {
                    "title": "IRDAI Master Circular on Health Insurance 2024",
                    "url": "https://irdai.gov.in/master-circular-health",
                    "content": "IRDAI mandates 100% cashless hospitalization turnaround in 3 hours.",
                    "score": 0.95
                },
                {
                    "title": "Health Insurance Portability Norms",
                    "url": "https://irdai.gov.in/portability",
                    "content": "Portability waiting periods credit must be granted continuously.",
                    "score": 0.88
                }
            ]
        }

        service = WebSearchService(api_key="tvly-test-12345")
        service.enabled = True
        service.client = mock_instance
        results = service.search("IRDAI health insurance regulations", max_results=2)

        assert len(results) == 2
        assert results[0]["title"] == "IRDAI Master Circular on Health Insurance 2024"
        assert results[0]["url"] == "https://irdai.gov.in/master-circular-health"
        assert results[0]["source_type"] == "web"
        assert results[0]["score"] == 0.95
        assert "cashless" in results[0]["content"]

        mock_instance.search.assert_called_once_with(
            query="IRDAI health insurance regulations",
            max_results=2,
            search_depth="basic",
            include_answer=False,
            include_raw_content=False
        )


def test_web_search_context_and_qna():
    """Verify get_search_context and qna_search with mocked TavilyClient."""
    with patch("app.services.web_search.TavilyClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance

        mock_instance.get_search_context.return_value = "Aggregated context from IRDAI regulations."
        mock_instance.qna_search.return_value = "The waiting period moratorium is 36 months under IRDAI norms."

        service = WebSearchService(api_key="tvly-test-12345")
        service.enabled = True
        service.client = mock_instance

        ctx = service.get_search_context("IRDAI norms")
        assert ctx == "Aggregated context from IRDAI regulations."

        answer = service.qna_search("What is the waiting period?")
        assert "36 months" in answer


def test_web_search_exception_handling():
    """Verify that exceptions raised by TavilyClient are caught gracefully."""
    with patch("app.services.web_search.TavilyClient") as mock_client_cls:
        mock_instance = MagicMock()
        mock_client_cls.return_value = mock_instance
        mock_instance.search.side_effect = Exception("Tavily API timeout error")
        mock_instance.get_search_context.side_effect = Exception("API rate limited")
        mock_instance.qna_search.side_effect = Exception("Service unavailable")

        service = WebSearchService(api_key="tvly-test-12345")
        service.enabled = True
        service.client = mock_instance
        results = service.search("Insurance regulations")
        assert results == []

        ctx = service.get_search_context("Insurance regulations")
        assert ctx == ""

        ans = service.qna_search("Insurance regulations")
        assert ans == ""
