"""
Chat API Router with Server-Sent Events (SSE) Streaming.
Handles user queries, message persistence, and streaming responses.
"""
import json
import asyncio
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.database.mysql import get_db, SessionLocal, Conversation, Message, Feedback, generate_uuid

router = APIRouter(prefix="/api", tags=["Chat"])


# ============================================================================
# Schemas
# ============================================================================

class ChatRequest(BaseModel):
    conversation_id: Optional[str] = Field(None, description="Active conversation UUID")
    message: str = Field(..., min_length=1, max_length=4000, description="User query")


class FeedbackRequest(BaseModel):
    message_id: str
    rating: int = Field(..., description="1 for thumbs up, -1 for thumbs down")
    comment: Optional[str] = None


# ============================================================================
# Response Generator for Phase 1
# ============================================================================

def generate_phase1_response(user_query: str) -> str:
    """
    Generate an intelligent decision-support introductory response for Phase 1.
    Explains the assistant's purpose, safety posture, and readiness for Phase 2 RAG.
    """
    query_lower = user_query.lower()

    if any(k in query_lower for k in ["hospital", "cover", "benefit", "room rent"]):
        return (
            "### Hospitalization & Inpatient Coverage (Decision Support Guidance)\n\n"
            "In insurance policies, **hospitalization coverage** generally encompasses:\n"
            "- **Inpatient Hospitalization**: Room rent, nursing charges, intensive care unit (ICU) charges, and doctor consultation fees for admissions exceeding 24 hours.\n"
            "- **Pre & Post Hospitalization**: Relevant medical expenses incurred 30–60 days prior and 60–90 days following discharge.\n"
            "- **Day Care Treatments**: Specific medical procedures not requiring 24-hour admission due to advanced medical technology.\n\n"
            "> [!NOTE]\n"
            "> Specific room rent caps, sub-limits, and co-payment percentages vary strictly by policy wording.\n\n"
            "**Next Step for Full Verification:**\n"
            "In **Phase 2**, upload your policy PDF via the attachment icon (`📎`). InsureGPT will extract the exact clauses, waiting periods, and deductible terms directly from your document with verified source citations."
        )

    if any(k in query_lower for k in ["claim", "document", "file", "reimbursement"]):
        return (
            "### Insurance Claims Procedure & Required Documentation\n\n"
            "To initiate a **health or general insurance claim**, insurers typically require the following primary dossier:\n\n"
            "1. **Completed & Signed Claim Form** (Part A & Part B)\n"
            "2. **Original Hospital Discharge Summary** detailing admission reason and clinical course\n"
            "3. **Original Final Hospital Bill** with itemized breakup and official payment receipts\n"
            "4. **Diagnostic Reports & Prescriptions** supporting the diagnosis and treatment\n"
            "5. **KYC Documents** (Government ID, PAN card, and cancelled cheque for NEFT settlement)\n\n"
            "> [!IMPORTANT]\n"
            "> **Notification Timelines**: Cashless claims usually require pre-authorization 48 hours prior for planned admission or within 24 hours for emergency admissions.\n\n"
            "*Once Phase 2 document ingestion is active, InsureGPT will verify your specific insurer's exact claims portal, turnaround times, and document checklist.*"
        )

    if any(k in query_lower for k in ["wait", "period", "diabetes", "pre-existing", "ped"]):
        return (
            "### Waiting Periods & Pre-Existing Conditions (PED)\n\n"
            "Insurance contracts typically enforce structured waiting periods:\n"
            "- **Initial Waiting Period**: 30 days from policy inception (accidents are usually covered from day one).\n"
            "- **Specific Disease Waiting Period**: 12 to 24 months for named ailments such as hernia, cataract, or joint replacement.\n"
            "- **Pre-Existing Disease (PED) Waiting Period**: Commonly 24 to 36 months for conditions diagnosed prior to inception (such as hypertension or diabetes mellitus).\n\n"
            "> [!NOTE]\n"
            "> Portability and continuous coverage benefits may reduce or waive waiting periods under regulatory portability rules.\n\n"
            "*Upload your specific policy schedule to inspect exact waiting period moratoriums and waiver clauses.*"
        )

    return (
        f"### InsureGPT Insurance Decision-Support Assistant\n\n"
        f"Thank you for your inquiry: *\"{user_query}\"*\n\n"
        f"I am designed to assist you with:\n"
        f"- **Policy Understanding**: Detailed breakdowns of inclusions, terms, and deductibles.\n"
        f"- **Exclusions & Waiting Periods**: Identifying specific disease waiting periods and non-payable items.\n"
        f"- **Claims Navigation**: Step-by-step guidance on cashless and reimbursement workflows.\n"
        f"- **Underwriting Guidelines**: Standard eligibility parameters and documentation prerequisites.\n\n"
        f"> [!IMPORTANT]\n"
        f"> **Safety & Decision Support Notice**: InsureGPT is a knowledge and decision-support assistant. "
        f"It does not autonomously approve or deny claims. Final decisions remain with your insurance company.\n\n"
        f"**System Status**: Phase 1 application skeleton, MySQL persistence, and SSE token streaming are fully functional. "
        f"In Phase 2, Pinecone hybrid retrieval and policy document parsing will be active for granular citations."
    )


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/chat")
async def chat_endpoint(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    SSE Chat streaming endpoint.
    Accepts user message, creates/retrieves conversation, streams tokens,
    and persists message history in MySQL.
    """
    # Validate or create conversation
    conv = None
    if payload.conversation_id:
        conv = db.query(Conversation).filter(Conversation.id == payload.conversation_id).first()

    if not conv:
        # Create new conversation with title inferred from first user message
        title_candidate = payload.message.strip().split("\n")[0][:60]
        conv = Conversation(
            id=payload.conversation_id or generate_uuid(),
            title=title_candidate or "Insurance Inquiry"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
    else:
        # Update title if it was default
        if conv.title in ["New Insurance Inquiry", "New Chat", "Untitled Inquiry"]:
            title_candidate = payload.message.strip().split("\n")[0][:60]
            conv.title = title_candidate
            conv.updated_at = datetime.now(timezone.utc)
            db.commit()

    conversation_id = conv.id

    # Persist User Message
    user_msg_id = generate_uuid()
    user_message = Message(
        id=user_msg_id,
        conversation_id=conversation_id,
        role="user",
        content=payload.message.strip()
    )
    db.add(user_message)
    conv.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Multi-layer AI Guardrails Check
    from app.guardrails.guardrails import AIGuardrails
    from app.services.llm import LLMService
    from app.vectorstore.retriever import HybridInsuranceRetriever
    from app.database.mysql import Citation

    guardrails = AIGuardrails()
    is_safe, guardrail_cat, guardrail_response = guardrails.validate_input(payload.message.strip())

    llm_service = LLMService()
    assistant_msg_id = generate_uuid()

    # If guardrails intercepted the query, skip retrieval & LLM
    if not is_safe:
        evidence = []
    else:
        retriever = HybridInsuranceRetriever()
        evidence = retriever.retrieve_evidence(payload.message.strip())

    async def sse_event_stream():
        """Generator that yields Server-Sent Events strictly grounded in knowledge base with guardrails."""
        try:
            # Send conversation and message metadata
            meta_payload = {
                "conversation_id": conversation_id,
                "message_id": assistant_msg_id,
                "user_message_id": user_msg_id,
                "title": conv.title,
                "citations_count": len(evidence),
                "guardrail_status": "blocked" if not is_safe else "passed",
                "guardrail_category": guardrail_cat
            }
            yield f"event: metadata\ndata: {json.dumps(meta_payload)}\n\n"

            accumulated_chunks = []

            if not is_safe:
                # Stream guardrail response cleanly
                words = guardrail_response.split(" ")
                for i, w in enumerate(words):
                    chunk = w + (" " if i < len(words) - 1 else "")
                    accumulated_chunks.append(chunk)
                    yield f"event: token\ndata: {json.dumps({'content': chunk})}\n\n"
                    await asyncio.sleep(0.012)
            else:
                # Stream tokens directly from LLM Service (strictly grounded on knowledge base evidence)
                async for token_chunk in llm_service.stream_chat(payload.message.strip(), evidence=evidence):
                    accumulated_chunks.append(token_chunk)
                    yield f"event: token\ndata: {json.dumps({'content': token_chunk})}\n\n"

            raw_response_text = "".join(accumulated_chunks)
            full_response_text = guardrails.validate_output(raw_response_text)

            # Persist assistant message and grounding citations in background session
            bg_db = SessionLocal()
            try:
                asst_msg = Message(
                    id=assistant_msg_id,
                    conversation_id=conversation_id,
                    role="assistant",
                    content=full_response_text
                )
                bg_db.add(asst_msg)

                # Persist grounding citations in MySQL
                for ev in evidence:
                    cit = Citation(
                        id=generate_uuid(),
                        message_id=assistant_msg_id,
                        chunk_id=ev.get("id") or "chunk_0",
                        section=ev.get("section") or "",
                        source_url=ev.get("policy_id") or ev.get("filename") or ""
                    )
                    bg_db.add(cit)

                c = bg_db.query(Conversation).filter(Conversation.id == conversation_id).first()
                if c:
                    c.updated_at = datetime.now(timezone.utc)
                bg_db.commit()
            finally:
                bg_db.close()

            # Send done event
            yield "event: done\ndata: [DONE]\n\n"

        except asyncio.CancelledError:
            pass
        except Exception as e:
            err_data = json.dumps({"error": f"Stream error: {str(e)}"})
            yield f"event: error\ndata: {err_data}\n\n"

    return StreamingResponse(
        sse_event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    """Record user feedback (thumbs up / thumbs down) for an assistant response."""
    msg = db.query(Message).filter(Message.id == payload.message_id).first()
    if not msg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message {payload.message_id} not found."
        )

    fb = Feedback(
        message_id=payload.message_id,
        rating=payload.rating,
        comment=payload.comment
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return {"message": "Feedback submitted successfully", "id": fb.id}
