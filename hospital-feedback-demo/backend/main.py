"""FastAPI application & REST endpoints for the HFD demo platform.

Run:  python -m uvicorn main:app --reload --port 8000
Docs: http://127.0.0.1:8000/docs
"""
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import ai_engine
import conversation
import database

# Maximum accepted voice-note upload (protects the Groq budget on a public host).
MAX_AUDIO_UPLOAD_BYTES = 10 * 1024 * 1024
from anonymizer import hash_phone
from config import AI_MODE, CORS_ORIGINS, DEPARTMENT_NAMES
from schemas import (
    AlertStatusUpdate,
    FeedbackResponse,
    NurseFeedbackRequest,
    WhatsAppTextRequest,
)

app = FastAPI(
    title="Omnichannel Hospital Feedback API (Lightweight Demo)",
    description="Dual-channel hospital feedback ingestion, AI classification, "
    "and escalation management — local PoC edition.",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    database.init_db()


# ============================================================================
# Ingestion endpoints
# ============================================================================
@app.post(
    "/api/v1/feedback/nurse",
    response_model=FeedbackResponse,
    status_code=201,
    summary="Log Nurse-Assisted Feedback",
)
def log_nurse_feedback(req: NurseFeedbackRequest) -> FeedbackResponse:
    """Ingests structured feedback collected by clinical staff."""
    phone_hash = hash_phone(req.patient_phone)
    data = {
        "visit_id": req.visit_id,
        "department_id": req.department_id,
        "channel": "NURSE_ASSISTED",
        "patient_phone_hash": phone_hash,
        "overall_rating": req.overall_rating,
        "sentiment_score": (req.overall_rating - 3) / 2.0,
        "category_tags": req.category_tags,
        "raw_comment": req.raw_comment,
        "summary": req.raw_comment or "Nurse-assisted entry.",
        "is_anonymous": req.is_anonymous,
    }
    result = database.insert_feedback(data)

    if result["alert_generated"]:
        message = "Feedback logged and alert dispatched."
    else:
        message = "Feedback logged successfully."

    return FeedbackResponse(
        status="success",
        feedback_id=result["feedback_id"],
        escalation_triggered=result["alert_generated"],
        alert_id=result.get("alert_id"),
        message=message,
    )


def _log_whatsapp_feedback(phone_hash: str, extracted: dict, narrative: str) -> FeedbackResponse:
    """Persists a completed conversational feedback record."""
    if extracted["is_medical_query"]:
        return FeedbackResponse(
            status="success",
            guardrail_triggered=True,
            message=(
                "I am an automated assistant, not a doctor. For medical advice, "
                "diagnosis, or dosage questions, please consult a qualified "
                "healthcare professional at the hospital immediately."
            ),
        )

    data = {
        "visit_id": f"VIS-2026-{_next_visit_suffix()}",
        "department_id": extracted["department_id"],
        "channel": "WHATSAPP_BOT",
        "patient_phone_hash": phone_hash,
        "overall_rating": extracted["overall_rating"],
        "sentiment_score": extracted["sentiment_score"],
        "category_tags": extracted["category_tags"],
        "raw_comment": narrative,
        "summary": extracted["summary"],
        "is_anonymous": True,
    }
    result = database.insert_feedback(data)

    dept_name = DEPARTMENT_NAMES.get(extracted["department_id"], extracted["department_id"])
    reply = ai_engine.generate_bot_reply(
        narrative,
        dept_name,
        result["alert_generated"],
        result["feedback_id"],
    )

    return FeedbackResponse(
        status="success",
        feedback_id=result["feedback_id"],
        escalation_triggered=result["alert_generated"],
        alert_id=result.get("alert_id"),
        phone_hash=phone_hash,
        extracted_data=extracted,
        message=reply,
    )


@app.post(
    "/api/v1/feedback/whatsapp/text",
    response_model=FeedbackResponse,
    summary="Process WhatsApp Text Feedback (Conversational)",
)
def process_whatsapp_text(req: WhatsAppTextRequest) -> FeedbackResponse:
    """Runs a warm multi-turn interview; logs the feedback once confirmed."""
    phone_hash = hash_phone(req.phone_number)
    turn = conversation.handle_turn(phone_hash, req.message_text)

    if turn["type"] == "guardrail":
        return FeedbackResponse(
            status="success",
            guardrail_triggered=True,
            message=turn["message"],
            phone_hash=phone_hash,
        )

    if turn["type"] == "question":
        return FeedbackResponse(
            status="success",
            message=turn["message"],
            phone_hash=phone_hash,
            conversational=True,
            conversation_step=turn.get("conversation_step"),
        )

    # type == "done" — log the confirmed feedback
    return _log_whatsapp_feedback(phone_hash, turn["extracted"], turn["narrative"])


@app.post(
    "/api/v1/feedback/whatsapp/audio",
    response_model=FeedbackResponse,
    summary="Transcribe & Process WhatsApp Audio Note (Conversational)",
)
async def process_whatsapp_audio(
    phone_number: str = Form(..., pattern=r"^\+[1-9]\d{1,14}$"),
    audio_file: UploadFile = File(...),
) -> FeedbackResponse:
    """Transcribes an audio note (Whisper) and feeds it into the same
    conversational intake flow."""
    file_bytes = await audio_file.read()
    if len(file_bytes) > MAX_AUDIO_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Audio file too large (max 10 MB).",
        )
    phone_hash = hash_phone(phone_number)

    try:
        transcript = ai_engine.transcribe_audio(file_bytes, audio_file.filename or "audio.webm")
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    turn = conversation.handle_turn(phone_hash, transcript)

    if turn["type"] == "guardrail":
        return FeedbackResponse(
            status="success",
            guardrail_triggered=True,
            message=turn["message"],
            phone_hash=phone_hash,
        )

    if turn["type"] == "question":
        return FeedbackResponse(
            status="success",
            message=turn["message"],
            phone_hash=phone_hash,
            conversational=True,
            conversation_step=turn.get("conversation_step"),
        )

    # type == "done" — log the confirmed feedback
    return _log_whatsapp_feedback(phone_hash, turn["extracted"], turn["narrative"])


# ============================================================================
# Dashboard & management endpoints
# ============================================================================
@app.get("/api/v1/dashboard/metrics", summary="Get Aggregate CSAT & Operational Metrics")
def get_dashboard_metrics():
    """Aggregated CSAT, sentiment, response counts and department heatmap."""
    return database.get_dashboard_metrics()


@app.get("/api/v1/dashboard/alerts", summary="List Hospital Escalation Alerts")
def get_hospital_alerts(status: Optional[str] = None):
    """Active or historical escalation alerts (defaults to all)."""
    return database.get_alerts(status)


@app.get("/api/v1/feedback/recent", summary="List Recent Feedback Records")
def get_recent_feedback(limit: int = 20):
    return database.get_recent_feedback(limit)


@app.patch("/api/v1/alerts/{alert_id}", summary="Update Alert Resolution Status")
def update_alert_status(alert_id: str, body: AlertStatusUpdate):
    """Marks an alert OPEN -> RESOLVED."""
    updated = database.resolve_alert(alert_id)
    if updated is None:
        raise HTTPException(status_code=404, detail="Alert not found or already resolved")
    return {
        "status": "success",
        "alert_id": alert_id,
        "new_status": updated["status"],
        "alert": updated,
    }


@app.get("/api/v1/health", summary="Health Check")
def health_check():
    return {
        "status": "ok",
        "ai_mode": AI_MODE,
        "db": database.DB_BACKEND,
    }


# ============================================================================
# Helpers
# ============================================================================
def _next_visit_suffix() -> str:
    import uuid

    return uuid.uuid4().hex[:4].upper()
