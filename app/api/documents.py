"""
Documents API Router for InsureGPT.
Handles document ingestion skeletons for Phase 1 and full ingestion in Phase 2.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from app.database.mysql import get_db, Document

router = APIRouter(prefix="/api/documents", tags=["Documents"])


class DocumentResponse(BaseModel):
    id: str
    filename: str
    document_type: str
    policy_id: Optional[str] = None
    version: Optional[str] = None
    status: str
    storage_path: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    """List all ingested insurance policy documents."""
    return db.query(Document).order_by(Document.created_at.desc()).all()


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str, db: Session = Depends(get_db)):
    """Get metadata for a specific document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found."
        )
    return doc


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    document_type: str = Form("policy"),
    policy_id: Optional[str] = Form(None),
    version: Optional[str] = Form("1.0"),
    db: Session = Depends(get_db)
):
    """
    Document upload endpoint.
    Skeleton in Phase 1; triggers parsing, chunking, and Pinecone ingestion in Phase 2.
    """
    return {
        "message": f"Document '{file.filename}' received. Full RAG ingestion pipeline activates in Phase 2.",
        "filename": file.filename,
        "document_type": document_type,
        "policy_id": policy_id,
        "version": version,
        "status": "ready_for_phase2"
    }
