"""
Conversational Memory Manager for InsureGPT.
Handles short-term dialogue context and non-sensitive preference persistence in Phase 4.
"""
from typing import List, Dict, Any


class ConversationalMemoryManager:
    """Manages short-term conversation context and query rewriting."""

    def __init__(self, window_size: int = 10):
        self.window_size = window_size

    def get_conversation_context(self, conversation_id: str) -> List[Dict[str, Any]]:
        """Retrieve recent conversation turns for context augmentation."""
        return []

    def rewrite_query_with_memory(self, query: str, conversation_id: str) -> str:
        """Rewrite conversational queries (e.g. 'What about diabetes?'). Activated in Phase 4."""
        return query
