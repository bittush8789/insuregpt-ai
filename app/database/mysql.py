"""
MySQL Database Manager and SQLAlchemy ORM Models for InsureGPT.
Handles connection, initialization, session management, and persistence.
"""
import uuid
from datetime import datetime, timezone
from typing import Generator
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    DateTime,
    Integer,
    ForeignKey,
    text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from app.config import get_settings

settings = get_settings()

# Engine and Session
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def utc_now():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def generate_uuid() -> str:
    """Generate a clean UUID string."""
    return str(uuid.uuid4())


# ============================================================================
# ORM Models (Matching Specification Section 10)
# ============================================================================

class User(Base):
    """User account entity."""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    conversations = relationship("Conversation", back_populates="user", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="user", cascade="all, delete-orphan")


class Conversation(Base):
    """Chat conversation session."""
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False, default="New Insurance Inquiry")
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    """Message exchanged in a conversation."""
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # "user", "assistant", "system"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")
    citations = relationship("Citation", back_populates="message", cascade="all, delete-orphan")
    feedback = relationship("Feedback", back_populates="message", cascade="all, delete-orphan")


class Memory(Base):
    """Conversational user memory / preference (non-sensitive)."""
    __tablename__ = "memories"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    memory_type = Column(String(50), nullable=False)  # e.g., "preference", "context"
    memory_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = relationship("User", back_populates="memories")


class Document(Base):
    """Policy or insurance document record."""
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    filename = Column(String(255), nullable=False)
    document_type = Column(String(50), nullable=False, default="policy")  # policy, endorsement, guideline
    policy_id = Column(String(100), nullable=True, index=True)
    version = Column(String(50), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, indexed, failed
    storage_path = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    versions = relationship("DocumentVersion", back_populates="document", cascade="all, delete-orphan")
    citations = relationship("Citation", back_populates="document")


class DocumentVersion(Base):
    """Specific revision of an insurance policy."""
    __tablename__ = "document_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    effective_date = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    document = relationship("Document", back_populates="versions")


class Citation(Base):
    """Grounding source citation for an assistant message claim."""
    __tablename__ = "citations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    chunk_id = Column(String(100), nullable=False)
    page_number = Column(Integer, nullable=True)
    section = Column(String(255), nullable=True)
    source_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    message = relationship("Message", back_populates="citations")
    document = relationship("Document", back_populates="citations")


class Feedback(Base):
    """User feedback on an assistant response."""
    __tablename__ = "feedback"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    message_id = Column(String(36), ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1 for thumbs up, -1 for thumbs down
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)

    message = relationship("Message", back_populates="feedback")


class AuditLog(Base):
    """Audit log for system activity and queries."""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), nullable=True, index=True)
    action = Column(String(100), nullable=False)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


# ============================================================================
# Database Initializer & Dependency
# ============================================================================

def init_db() -> bool:
    """
    Ensure the MySQL database exists and create all tables.
    Returns True if successfully initialized.
    """
    try:
        # Step 1: Ensure database exists
        server_engine = create_engine(settings.server_database_url, isolation_level="AUTOCOMMIT")
        with server_engine.connect() as conn:
            conn.execute(text(
                f"CREATE DATABASE IF NOT EXISTS `{settings.mysql_database}` "
                f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
            ))
        server_engine.dispose()

        # Step 2: Create all tables defined in Base
        Base.metadata.create_all(bind=engine)

        # Step 3: Seed initial insurance documents if empty
        seed_default_documents()

        return True
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
        return False


def seed_default_documents():
    """Seed initial insurance policies and guidelines into the database."""
    session = SessionLocal()
    try:
        default_docs = [
            {
                "filename": "health_comprehensive_policy_2026.txt",
                "document_type": "policy",
                "policy_id": "POL-HLT-2026-V1",
                "version": "2026.1",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/health_comprehensive_policy_2026.txt"
            },
            {
                "filename": "claims_procedure_and_guidelines.txt",
                "document_type": "guideline",
                "policy_id": "GUIDE-CLM-2026",
                "version": "2026.2",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/claims_procedure_and_guidelines.txt"
            },
            {
                "filename": "motor_private_car_policy.txt",
                "document_type": "policy",
                "policy_id": "POL-MOT-2026-V1",
                "version": "2026.1",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/motor_private_car_policy.txt"
            },
            {
                "filename": "term_life_and_critical_illness_policy_2026.txt",
                "document_type": "policy",
                "policy_id": "POL-LIF-2026-V1",
                "version": "2026.1",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/term_life_and_critical_illness_policy_2026.txt"
            },
            {
                "filename": "commercial_property_and_fire_policy_2026.txt",
                "document_type": "policy",
                "policy_id": "POL-PRP-2026-V1",
                "version": "2026.1",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/commercial_property_and_fire_policy_2026.txt"
            },
            {
                "filename": "travel_international_insurance_policy_2026.txt",
                "document_type": "policy",
                "policy_id": "POL-TRV-2026-V1",
                "version": "2026.1",
                "effective_date": "2026-01-01",
                "status": "indexed",
                "storage_path": "data/documents/travel_international_insurance_policy_2026.txt"
            }
        ]

        for doc_info in default_docs:
            existing = session.query(Document).filter(Document.filename == doc_info["filename"]).first()
            if not existing:
                doc_id = generate_uuid()
                new_doc = Document(
                    id=doc_id,
                    filename=doc_info["filename"],
                    document_type=doc_info["document_type"],
                    policy_id=doc_info["policy_id"],
                    version=doc_info["version"],
                    status=doc_info["status"],
                    storage_path=doc_info["storage_path"]
                )
                session.add(new_doc)
                
                version_record = DocumentVersion(
                    document_id=doc_id,
                    version=doc_info["version"],
                    effective_date=doc_info["effective_date"]
                )
                session.add(version_record)
        session.commit()
    except Exception as e:
        print(f"[WARN] Could not seed default documents: {e}")
        session.rollback()
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
