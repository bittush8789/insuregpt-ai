"""
Conversation Management API Router for InsureGPT.
Handles CRUD operations for chat conversations and message history.
"""
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.database.mysql import get_db, Conversation, Message, Citation

router = APIRouter(prefix="/api/conversations", tags=["Conversations"])


# ============================================================================
# Schemas
# ============================================================================

class ConversationCreateRequest(BaseModel):
    title: Optional[str] = Field(default="New Insurance Inquiry", max_length=255)


class ConversationUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    summary: Optional[str] = None


class CitationResponse(BaseModel):
    id: str
    chunk_id: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime
    citations: List[CitationResponse] = []

    model_config = ConfigDict(from_attributes=True)


class ConversationSummaryResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(BaseModel):
    id: str
    title: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Endpoints
# ============================================================================

@router.post("", response_model=ConversationSummaryResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: Optional[ConversationCreateRequest] = None,
    db: Session = Depends(get_db)
):
    """Create a new conversation session."""
    title = payload.title if payload and payload.title else "New Insurance Inquiry"
    conv = Conversation(title=title)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.get("", response_model=List[ConversationSummaryResponse])
def list_conversations(db: Session = Depends(get_db)):
    """List all conversations ordered by recent activity."""
    return db.query(Conversation).order_by(Conversation.updated_at.desc()).all()


@router.get("/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Retrieve full conversation details including messages and citations."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found."
        )
    return conv


@router.patch("/{conversation_id}", response_model=ConversationSummaryResponse)
def update_conversation(
    conversation_id: str,
    payload: ConversationUpdateRequest,
    db: Session = Depends(get_db)
):
    """Rename or update conversation metadata."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found."
        )

    if payload.title is not None:
        conv.title = payload.title.strip() or "Untitled Inquiry"
    if payload.summary is not None:
        conv.summary = payload.summary
    conv.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(conv)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(conversation_id: str, db: Session = Depends(get_db)):
    """Delete a conversation and all its associated messages."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation {conversation_id} not found."
        )
    db.delete(conv)
    db.commit()
    return {"message": "Conversation deleted successfully", "id": conversation_id}
