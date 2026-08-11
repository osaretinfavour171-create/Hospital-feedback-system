"""Pydantic models for request/response validation at system boundaries."""
import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from config import VALID_DEPARTMENTS

PHONE_PATTERN = r"^\+[1-9]\d{1,14}$"


# ---------------------------------------------------------------------------
# Inbound
# ---------------------------------------------------------------------------
class NurseFeedbackRequest(BaseModel):
    visit_id: str = Field(..., min_length=3, max_length=50, example="VIS-2026-104")
    department_id: str = Field(..., example="PHARMACY")
    overall_rating: int = Field(..., ge=1, le=5)
    category_tags: List[str] = Field(default_factory=list)
    raw_comment: Optional[str] = Field(None, max_length=1000)
    is_anonymous: bool = False
    patient_phone: Optional[str] = None

    @field_validator("department_id")
    @classmethod
    def validate_department(cls, value: str) -> str:
        v = value.strip().upper()
        if v not in VALID_DEPARTMENTS:
            raise ValueError(f"Invalid department. Must be one of {sorted(VALID_DEPARTMENTS)}")
        return v

    @field_validator("patient_phone")
    @classmethod
    def validate_phone_optional(cls, value: Optional[str]) -> Optional[str]:
        if value and not re.match(PHONE_PATTERN, value):
            raise ValueError("Phone number must adhere to E.164 format (e.g., +2348012345678)")
        return value


class WhatsAppTextRequest(BaseModel):
    phone_number: str = Field(..., example="+2348012345678")
    message_text: str = Field(..., min_length=1, max_length=2000)

    @field_validator("phone_number")
    @classmethod
    def validate_e164_phone(cls, value: str) -> str:
        if not re.match(PHONE_PATTERN, value):
            raise ValueError("Phone number must adhere to strict E.164 format (e.g., +2348012345678)")
        return value


class AlertStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(OPEN|RESOLVED)$")


# ---------------------------------------------------------------------------
# AI engine output
#
# This is the contract for UNSTRUCTURED LLM output, so validation is deliberately
# lenient: missing/null fields from the model are coerced to safe defaults rather
# than failing the whole extraction (which would silently downgrade to offline).
# ---------------------------------------------------------------------------
class AIExtractionOutput(BaseModel):
    is_medical_query: bool = Field(False, description="True if patient asks for diagnosis, dosage, or medical advice")
    department_id: str = Field("OPD", description="One of: OPD, EMERGENCY, PHARMACY, BILLING, WARDS")
    overall_rating: int = Field(3, ge=1, le=5)
    sentiment_score: float = Field(0.0, ge=-1.0, le=1.0)
    category_tags: List[str] = Field(default_factory=list)
    summary: str = ""
    is_critical_issue: bool = False

    @field_validator("overall_rating", mode="before")
    @classmethod
    def coerce_rating(cls, value) -> int:
        if value is None:
            return 3
        try:
            return max(1, min(5, round(float(value))))
        except (TypeError, ValueError):
            return 3

    @field_validator("sentiment_score", mode="before")
    @classmethod
    def coerce_sentiment(cls, value) -> float:
        if value is None:
            return 0.0
        try:
            return max(-1.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return 0.0

    @field_validator("is_medical_query", "is_critical_issue", mode="before")
    @classmethod
    def coerce_bool(cls, value) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        return bool(value)

    @field_validator("category_tags", mode="before")
    @classmethod
    def coerce_tags(cls, value) -> List[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(t) for t in value]
        # Guard against the LLM emitting a comma-joined string instead of a list.
        if isinstance(value, str):
            return [t.strip() for t in value.split(",") if t.strip()]
        return [str(value)]

    @field_validator("department_id", mode="before")
    @classmethod
    def validate_department(cls, value) -> str:
        v = str(value or "").strip().upper()
        if v not in VALID_DEPARTMENTS:
            return "OPD"
        return v

    @field_validator("summary", mode="before")
    @classmethod
    def coerce_summary(cls, value) -> str:
        if value is None:
            return ""
        return str(value)


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------
class FeedbackResponse(BaseModel):
    status: str
    feedback_id: Optional[str] = None
    guardrail_triggered: bool = False
    escalation_triggered: bool = False
    message: str = ""
    extracted_data: Optional[dict] = None
    alert_id: Optional[str] = None
    phone_hash: Optional[str] = None
    # Conversational intake: true while the bot is still asking questions;
    # feedback_id is null until the patient confirms and the record is logged.
    conversational: bool = False
    conversation_step: Optional[str] = None
