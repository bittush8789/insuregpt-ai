"""
InsureGPT Configuration Module
Centralized configuration management with validation using pydantic-settings.
"""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application / Server
    app_name: str = "InsureGPT"
    app_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = True
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # MySQL Configuration
    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "insuregpt"
    mysql_user: str = "root"
    mysql_password: str = "root"

    @property
    def database_url(self) -> str:
        """Construct the SQLAlchemy MySQL database URL."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}?charset=utf8mb4"
        )

    @property
    def server_database_url(self) -> str:
        """Server-level connection URL used for database creation if needed."""
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/?charset=utf8mb4"
        )

    # Pinecone Configuration (Phase 2+)
    pinecone_api_key: str = "dummy_key"
    pinecone_index_name: str = "insuregpt-index"
    pinecone_namespace: str = "default"
    pinecone_dimension: int = 1024

    # LLM Service Configuration
    llm_provider: str = "groq"  # "groq" or "openai"
    llm_api_key: str = "dummy_key"
    llm_model: str = "openai/gpt-oss-120b"
    llm_temperature: float = 0.1
    llm_max_tokens: int = 2048

    # Groq & GPTMode 120B Configuration
    groq_api_key: Optional[str] = None
    groq_model: str = "openai/gpt-oss-120b"  # Groq model: openai/gpt-oss-120b
    output_format: str = "bullet"  # Strictly enforces bullet-point output structure

    # Embeddings & Reranker Configuration
    embedding_model: str = "text-embedding-3-small"
    reranker_model: str = "BAAI/bge-reranker-base"

    # RAG Settings
    retrieval_k: int = 8
    rerank_top_k: int = 4
    chunk_size: int = 800
    chunk_overlap: int = 150
    min_evidence_score: float = 0.65

    # Memory Settings
    short_term_memory_window: int = 10
    max_memory_tokens: int = 2000

    # Guardrails Configuration
    enable_prompt_injection_detection: bool = True
    enable_pii_detection: bool = True
    enable_grounding_validation: bool = True
    max_query_length: int = 2000

    # Knowledge Base Only Configuration (Web Search Disabled)
    web_search_enabled: bool = False

    # Storage Paths
    documents_storage_path: str = "data/documents"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    """Singleton getter for cached application settings."""
    return Settings()
