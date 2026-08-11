"""AI Engine — Groq LLM extraction & Whisper transcription, with an
offline deterministic fallback so the demo runs with zero API keys.

Modes:
  * groq    — live API calls (llama-3.3-70b-versatile + whisper-large-v3)
  * offline — rule-based extractor (fully functional demo)
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from config import (
    AI_MODE,
    DEPARTMENT_NAMES,
    GROQ_API_KEY,
    GROQ_LLM_MODEL,
    GROQ_WHISPER_MODEL,
)
from schemas import AIExtractionOutput

# ============================================================================
# Groq integration (live mode)
# ============================================================================

SYSTEM_PROMPT = """You are an expert AI clinical feedback analyst for University of Benin Teaching Hospital (UBTH).
Your task is to analyze patient feedback comments and extract structured operational metadata.

STRICT RULES:
1. MEDICAL GUARDRAIL: If the user is asking for medical advice, prescription guidelines, dosage instructions, or diagnosis, set "is_medical_query": true.
2. DEPARTMENT MAPPING: Map the comment to exactly ONE valid department ID: ["OPD", "EMERGENCY", "PHARMACY", "BILLING", "WARDS"]. If unclear, default to "OPD".
3. RATING EXTRACTION: Extract an overall rating from 1 (terrible) to 5 (excellent). If not explicitly stated, infer based on tone.
4. SENTIMENT SCORE: Return a floating number between -1.00 (extremely negative) and +1.00 (extremely positive).
5. CATEGORY TAGS: Choose relevant tags from: ["LONG_WAIT", "STAFF_COURTESY", "CLEANLINESS", "DRUG_AVAILABILITY", "BILLING_DELAY", "QUALITY_OF_CARE", "DIRTY_FACILITY"].
6. CRITICAL ISSUE: Set "is_critical_issue": true ONLY if there is an explicit mention of staff abuse, severe medical negligence, or extreme physical hazard.

OUTPUT FORMAT: You MUST return a valid JSON object matching this schema exactly:
{"is_medical_query": bool, "department_id": str, "overall_rating": int, "sentiment_score": float, "category_tags": [str], "summary": str, "is_critical_issue": bool}"""

_groq_client: Optional[Any] = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq

        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _process_with_groq(raw_text: str) -> Dict[str, Any]:
    """Invokes Groq API with JSON mode for deterministic response parsing."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=GROQ_LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )
    data = json.loads(response.choices[0].message.content)
    # Defensive coercion so the pipeline always receives a valid contract
    return AIExtractionOutput(**data).model_dump()


def transcribe_with_groq(file_bytes: bytes, filename: str) -> str:
    """Transcribes patient audio via Groq Whisper API."""
    client = _get_groq_client()
    transcription = client.audio.transcriptions.create(
        file=(filename, file_bytes),
        model=GROQ_WHISPER_MODEL,
        response_format="text",
    )
    return transcription


# ============================================================================
# Bot reply generation (live AI)
# ============================================================================

REPLY_SYSTEM_PROMPT = """You are the warm, professional WhatsApp assistant for the
University of Benin Teaching Hospital (UBTH) patient feedback service.

Write a brief, empathetic WhatsApp reply (2-3 sentences) to the patient's feedback.

Rules:
- Acknowledge the SPECIFIC issue(s) they mentioned (wait times, staff courtesy,
  billing, cleanliness, drug availability, quality of care, etc.) by name.
- Confirm their feedback has been logged and will be reviewed by the hospital.
- If an escalation alert was triggered, mention management has been alerted and
  will follow up directly.
- Always include the feedback reference number (Ref: #...) exactly as provided.
- NEVER give medical advice, diagnoses, or dosage guidance.
- NEVER mention "extraction", "JSON", "LLM", or any technical pipeline detail.
- Sound like a caring, human hospital staff member. Use one emoji maximum, or none.
- End with "— UBTH Care Team".
"""


def _template_reply(department_name: str, escalation_triggered: bool, feedback_id: str, channel: str) -> str:
    """Deterministic fallback reply (offline mode or API failure)."""
    prefix = "Thank you for your voice note." if channel == "voice" else "Thank you for sharing."
    base = (
        f"{prefix} Your feedback regarding {department_name} has been "
        f"logged (Ref: #{feedback_id.upper()})."
    )
    if escalation_triggered:
        base += " Our management team has been alerted and will follow up."
    return base


def generate_bot_reply(
    patient_text: str,
    department_name: str,
    escalation_triggered: bool,
    feedback_id: str,
    channel: str = "text",
) -> str:
    """Generates a personalized, empathetic WhatsApp reply via Groq.

    Falls back to the deterministic template when offline, when the call
    fails, or when the model returns empty output.
    """
    fallback = lambda: _template_reply(department_name, escalation_triggered, feedback_id, channel)
    if AI_MODE != "groq":
        return fallback()
    try:
        client = _get_groq_client()
        escalation_line = (
            "ESCALATION: yes - feedback triggered an escalation alert for management review."
            if escalation_triggered
            else "ESCALATION: no"
        )
        user_msg = "\n".join(
            [
                "Patient feedback: " + repr(patient_text),
                "Department: " + department_name,
                "Feedback reference: " + feedback_id,
                escalation_line,
            ]
        )
        response = client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=[
                {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=240,
        )
        reply = (response.choices[0].message.content or "").strip()
        return reply if reply else fallback()
    except Exception as exc:
        print(f"[ai_engine] Reply generation failed ({exc}); using template.")
        return fallback()


# ============================================================================
# Offline fallback (rule-based extractor)
# ============================================================================

# Terms that indicate the message is about medical treatment / advice topics
_MEDICAL_TERMS = [
    "dosage", "dose", "prescription", "diagnos", "symptom", "treatment",
    "cure", "side effect", "antibiotic", "amoxicillin", "paracetamol",
    "panadol", "aspirin", "ibuprofen", "medicine", "medication", "tablet",
    "capsule", "syrup", "infection", "malaria", "fever", "cough",
    "headache", "insulin", "vaccine", "injection", "painkiller",
    "blood pressure", "mg of", "milligram", "ml of",
]

# Phrases that signal the patient is ASKING for medical advice (not just
# describing an operational issue).
_MEDICAL_REQUEST_PATTERNS = [
    "should i take", "should i give", "can i take", "can i give",
    "should my child", "can my child", "should my baby", "can my baby",
    "what medicine should", "what drug should", "what dosage",
    "how much should", "how many mg", "how much mg", "is it safe",
    "is it ok to", "what should i", "how do i treat", "do i need",
    "tell me what", "what do i do", "is it normal",
    "should i be worried", "what is wrong with", "what's wrong with",
    "can you prescribe",
]

_DEPARTMENT_KEYWORDS = {
    "PHARMACY": ["pharmac", "drug", "medicine", "medication", "prescription",
                 "chemist", "tablet", "refill"],
    "EMERGENCY": ["emergency", " casualty", "accident", "ambulance",
                  "triage", "trauma", "resuscitation"],
    "BILLING": ["billing", "bill", "payment", "invoice", "receipt", "charge",
                "refund", "cashier", "account", "fee", "cost", "nhis", "hmo"],
    "WARDS": ["ward", "admission", "inpatient", "bed", "room", "nurse care",
              "admitted", "ward rounds"],
    "OPD": ["outpatient", "clinic", "consultation", "doctor visit", "opd",
            "general practice"],
}

_POSITIVE_WORDS = {
    "great": 1.0, "excellent": 1.0, "good": 0.7, "nice": 0.6, "wonderful": 1.0,
    "amazing": 1.0, "helpful": 0.8, "friendly": 0.7, "polite": 0.7, "caring": 0.8,
    "professional": 0.7, "clean": 0.6, "fast": 0.5, "quick": 0.5, "thank": 0.6,
    "love": 0.9, "best": 0.9, "kind": 0.7, "smiling": 0.6, "attentive": 0.7,
    "efficient": 0.6, "smooth": 0.5, "happy": 0.8, "satisfied": 0.7,
}

_NEGATIVE_WORDS = {
    "terrible": -1.0, "awful": -1.0, "bad": -0.7, "poor": -0.7, "horrible": -1.0,
    "worst": -1.0, "rude": -0.8, "unfriendly": -0.8, "unprofessional": -0.7,
    "dirty": -0.8, "filthy": -0.9, "unclean": -0.8, "slow": -0.5, "wait": -0.4,
    "delay": -0.5, "long": -0.3, "hours": -0.3, "negligence": -1.0, "abuse": -1.0,
    "neglect": -0.9, "disrespect": -0.9, "shout": -0.7, "scream": -0.7,
    "scam": -0.9, "overcharge": -0.7, "cheated": -0.8, "cold": -0.5,
    "unhelpful": -0.7, "disappointed": -0.7, "frustrated": -0.7, "angry": -0.8,
    "fed up": -0.7, "expensive": -0.5, "out of stock": -0.7, "lack": -0.5,
    "missing": -0.5, "insult": -0.8, "ignored": -0.7, "ignor": -0.7,
    "yell": -0.7, "threaten": -0.9, "harass": -0.9,
}

_NEGATIONS = {"not", "no", "never", "didn't", "doesn't", "wasn't", "isn't", "hardly", "without"}

# Word stems for critical safety issues (matched with \b boundaries and
# inflection-tolerant suffixes).
_CRITICAL_STEMS = [
    "abus",        # abuse / abusive / abusing
    "beat",        # beaten / beating
    "assault",     # assaulted
    "neglig",      # negligence / negligent
    "neglect",     # neglected
    "died",        # died / dies
    "death",
    "misdiagnos",
    "hazard",
    "collaps",     # collapsed
    "unresponsive",
    "no oxygen",
    "wrong drug",
    "overdose",
    "discriminat",
]

_CRITICAL_EXTRA = [
    "wrong treatment", "severe medical", "physical hazard", "safety concern",
]

_TAG_KEYWORDS = {
    "LONG_WAIT": ["wait", "delay", "hours", "queue", "long time", "slow service", "stuck"],
    "STAFF_COURTESY": ["rude", "unfriendly", "polite", "friendly", "courtesy", "helpful",
                       "unprofessional", "shout", "scream", "disrespect", "kind", "attentive"],
    "CLEANLINESS": ["dirty", "filthy", "unclean", "clean", "hygiene", "smell", "toilet", "stain"],
    "DIRTY_FACILITY": ["dirty", "filthy", "unclean", "dusty", "stain", "unsanitary"],
    "DRUG_AVAILABILITY": ["drug", "medicine", "medication", "out of stock", "no drugs",
                          "pharmac", "prescription", "unavailable", "shortage", "stock",
                          "antibiotic"],
    "BILLING_DELAY": ["billing", "bill", "payment", "receipt", "overcharge", "charge",
                      "refund", "invoice", "cashier", "nhis", "hmo"],
    "QUALITY_OF_CARE": ["doctor", "nurse", "care", "treatment", "diagnosis", "attention",
                        "examination", "test result", "follow-up", "professional"],
}


def _is_medical_query(text: str) -> bool:
    """True only when the patient is ASKING for medical advice.

    Requires both a medical topic term AND an advice-request signal, so
    operational feedback like \"pharmacy was out of antibiotics\" is not
    blocked by the guardrail.
    """
    low = text.lower()
    has_medical = any(term in low for term in _MEDICAL_TERMS)
    if not has_medical:
        return False
    return any(pattern in low for pattern in _MEDICAL_REQUEST_PATTERNS)


def _detect_department(text: str) -> str:
    low = text.lower()
    best, best_score = "OPD", 0
    for dept, kws in _DEPARTMENT_KEYWORDS.items():
        score = sum(1 for kw in kws if kw in low)
        if score > best_score:
            best, best_score = dept, score
    return best


def _lookup_word(word: str) -> float | None:
    """Look up a word in the sentiment lexicons, tolerating common suffixes
    and stem inflections (e.g. 'shouted' -> 'shout', 'abusive' -> 'abus')."""
    if word in _POSITIVE_WORDS:
        return _POSITIVE_WORDS[word]
    if word in _NEGATIVE_WORDS:
        return _NEGATIVE_WORDS[word]

    # Strip common suffixes: shouted -> shout, waiting -> wait
    for suffix in ("ed", "ing", "es", "er", "ly", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            base = word[: -len(suffix)]
            if base in _POSITIVE_WORDS:
                return _POSITIVE_WORDS[base]
            if base in _NEGATIVE_WORDS:
                return _NEGATIVE_WORDS[base]

    # Stem prefix matching: abusive -> abus, ignored -> ignor, yelling -> yell
    for key in _NEGATIVE_WORDS:
        if word.startswith(key) and len(word) - len(key) <= 4 and len(word) > len(key):
            return _NEGATIVE_WORDS[key]
    for key in _POSITIVE_WORDS:
        if word.startswith(key) and len(word) - len(key) <= 4 and len(word) > len(key):
            return _POSITIVE_WORDS[key]
    return None


def _score_sentiment(text: str) -> float:
    """Lexicon-based sentiment with inflection-tolerant matching and
    negation handling; returns -1.0..1.0."""
    low = text.lower()
    tokens = re.findall(r"[a-zA-Z']+", low)
    score, hits = 0.0, 0
    for i, tok in enumerate(tokens):
        val = _lookup_word(tok)
        if val is None:
            continue
        # Negation flips polarity (e.g. "not good")
        if i > 0 and tokens[i - 1] in _NEGATIONS:
            val = -val
        score += val
        hits += 1
    if hits == 0:
        return 0.0
    return max(-1.0, min(1.0, score / max(hits, 3)))


def _rating_from_sentiment(sentiment: float) -> int:
    if sentiment <= -0.5:
        return 1
    if sentiment < -0.15:
        return 2
    if sentiment < 0.4:
        return 3
    if sentiment < 0.7:
        return 4
    return 5


def _detect_tags(text: str) -> list[str]:
    low = text.lower()
    tags = []
    for tag, kws in _TAG_KEYWORDS.items():
        if any(kw in low for kw in kws):
            if tag not in tags:
                tags.append(tag)
    return tags


def _is_critical(text: str) -> bool:
    """Detects explicit staff abuse, negligence or physical hazard mentions."""
    low = text.lower()
    if any(kw in low for kw in _CRITICAL_EXTRA):
        return True
    for stem in _CRITICAL_STEMS:
        for match in re.finditer(r"\b" + re.escape(stem), low):
            suffix = low[match.end():match.end() + 4]
            if any(suffix.startswith(s) for s in ("", "e", "ed", "ing", "es", "al", "iv", "ant", "en")):
                return True
    return False


def _make_summary(text: str, dept: str, rating: int) -> str:
    dept_name = DEPARTMENT_NAMES.get(dept, dept)
    cleaned = re.sub(r"\s+", " ", text).strip()
    snippet = cleaned[:160]
    if not snippet:
        snippet = "No additional detail provided."
    if rating <= 2:
        return f"Low satisfaction ({rating}/5) reported for {dept_name}: {snippet}"
    return f"Feedback for {dept_name} ({rating}/5): {snippet}"


def _process_offline(raw_text: str) -> Dict[str, Any]:
    """Deterministic rule-based extraction — zero API cost, offline-safe."""
    text = (raw_text or "").strip()
    if not text:
        return AIExtractionOutput(
            is_medical_query=False,
            department_id="OPD",
            overall_rating=3,
            sentiment_score=0.0,
            category_tags=[],
            summary="Empty message.",
            is_critical_issue=False,
        ).model_dump()

    if _is_medical_query(text):
        return AIExtractionOutput(
            is_medical_query=True,
            department_id="OPD",
            overall_rating=3,
            sentiment_score=0.0,
            category_tags=[],
            summary="Medical advice request — not logged as feedback.",
            is_critical_issue=False,
        ).model_dump()

    dept = _detect_department(text)
    sentiment = _score_sentiment(text)
    rating = _rating_from_sentiment(sentiment)
    tags = _detect_tags(text)
    critical = _is_critical(text)
    summary = _make_summary(text, dept, rating)

    return AIExtractionOutput(
        is_medical_query=False,
        department_id=dept,
        overall_rating=rating,
        sentiment_score=round(sentiment, 2),
        category_tags=tags,
        summary=summary,
        is_critical_issue=critical,
    ).model_dump()


# ============================================================================
# Public API
# ============================================================================

def process_patient_text(raw_text: str) -> Dict[str, Any]:
    """Extracts structured metadata from unstructured patient text.

    Uses live Groq LLM when GROQ_API_KEY is set; otherwise the offline
    rule-based extractor keeps the demo fully functional.
    """
    if AI_MODE == "groq":
        try:
            return _process_with_groq(raw_text)
        except Exception as exc:  # network / quota errors -> graceful fallback
            print(f"[ai_engine] Groq call failed ({exc}); using offline extractor.")
    return _process_offline(raw_text)


def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    """Transcribes audio. Requires a Groq API key (Whisper)."""
    if AI_MODE != "groq":
        raise RuntimeError(
            "Audio transcription requires a Groq API key. "
            "Add GROQ_API_KEY to backend/.env to enable Whisper transcription."
        )
    return transcribe_with_groq(file_bytes, filename)


