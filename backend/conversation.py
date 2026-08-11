"""Conversational feedback intake for the WhatsApp channel.

Turns the single-shot "send feedback -> thank you" flow into a warm,
multi-turn interview so patients feel heard before anything is logged.

Flow:  start -> department -> rating -> issues -> detail -> confirm -> done

Sessions are persisted to the database (Postgres on Vercel, SQLite
locally), keyed by phone hash, with an idle TTL — so conversations
survive serverless cold starts. Every turn is guardrailed (medical
advice requests are refused) and a cancel word resets the session
without logging anything.
"""

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import ai_engine
import database
from config import AI_MODE, DEPARTMENT_NAMES, GROQ_LLM_MODEL

# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------
SESSION_TTL_SECONDS = 900  # 15 min of idle time -> session expires

RATING_WORDS = {
    "terrible": 1, "awful": 1, "horrible": 1, "worst": 1, "poor": 1,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "bad": 2, "fair": 2, "below average": 2,
    "okay": 3, "ok": 3, "good": 3, "fine": 3, "average": 3, "decent": 3,
    "great": 4, "nice": 4, "very good": 4, "above average": 4,
    "excellent": 5, "amazing": 5, "wonderful": 5, "best": 5, "perfect": 5,
}

# Tokens (not substrings) that signal an affirmative / negative answer.
_YES_TOKENS = {
    "yes", "yeah", "yep", "yup", "correct", "right", "confirm", "confirmed",
    "sure", "ok", "okay", "alright", "fine", "go", "proceed", "please",
}
_NO_TOKENS = {
    "no", "nope", "not", "never", "wrong", "incorrect", "fix", "change",
    "skip", "cancel",
}

CANCEL_WORDS = {
    "cancel", "stop", "quit", "start over", "restart", "abort",
    "forget it", "never mind this", "end", "bye", "goodbye",
}

CANNED_QUESTIONS = {
    "department": (
        "Which department did you visit? Reply with one of:\n"
        "OPD, Emergency, Pharmacy, Billing, or Wards."
    ),
    "rating": (
        "On a scale of 1 to 5, how would you rate your overall experience? "
        "(1 = poor, 5 = excellent)"
    ),
    "issues": (
        "What mattered most to you? Reply with any of:\n"
        "wait time, staff courtesy, cleanliness, drug availability, billing, "
        "or quality of care."
    ),
    "detail": (
        "Anything else you'd like us to know about your visit? "
        "Reply with details, or type \"no\" to skip."
    ),
}

QUESTION_SYSTEM_PROMPT = """You are the warm, caring WhatsApp assistant for the University of Benin Teaching Hospital (UBTH) patient feedback service. You are collecting feedback through a short conversation, one question at a time.

Rules:
- Reply with ONLY the next question, short and natural (1-2 sentences), like a friendly human.
- Briefly acknowledge what the patient just said so they feel heard.
- Never give medical advice, and never mention extraction, JSON, LLM, or pipeline details.
- Ask the specific thing described under "Next thing to ask".
"""


@dataclass
class Session:
    phone_hash: str
    state: str = "start"  # start | department | rating | issues | detail | confirm | done
    collected: Dict[str, Any] = field(default_factory=dict)
    history: List[str] = field(default_factory=list)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()


def _load_session(phone_hash: str) -> Optional[Session]:
    """Loads a session from the database, or None."""
    row = database.get_session(phone_hash)
    if row is None:
        return None
    try:
        return Session(
            phone_hash=phone_hash,
            state=row["state"],
            collected=json.loads(row["collected"] or "{}"),
            history=json.loads(row["history"] or "[]"),
            updated_at=row["updated_at"],
        )
    except (ValueError, TypeError):
        return None


def _save_session(session: Session) -> None:
    """Persists the session so it survives serverless cold starts."""
    database.upsert_session(
        session.phone_hash,
        session.state,
        json.dumps(session.collected),
        json.dumps(session.history),
        session.updated_at,
    )


def get_or_create_session(phone_hash: str) -> Session:
    now = time.time()
    database.prune_sessions(now - SESSION_TTL_SECONDS)
    sess = _load_session(phone_hash)
    if sess is None or now - sess.updated_at > SESSION_TTL_SECONDS:
        sess = Session(phone_hash=phone_hash)
        _save_session(sess)  # persist new sessions immediately
    sess.touch()
    return sess


def reset_session(phone_hash: str) -> None:
    database.delete_session(phone_hash)


# ---------------------------------------------------------------------------
# Parsing helpers (deterministic, offline-safe)
# ---------------------------------------------------------------------------
def _parse_department(text: str) -> Optional[str]:
    low = text.lower()
    for dept, keywords in ai_engine._DEPARTMENT_KEYWORDS.items():
        if any(kw in low for kw in keywords):
            return dept
    # Loose name / alias matching
    aliases = {
        "outpatient": "OPD",
        "opd": "OPD",
        "emergency": "EMERGENCY",
        "accident": "EMERGENCY",
        "a&e": "EMERGENCY",
        "casualty": "EMERGENCY",
        "pharmacy": "PHARMACY",
        "pharmacist": "PHARMACY",
        "drug": "PHARMACY",
        "billing": "BILLING",
        "accounts": "BILLING",
        "payment": "BILLING",
        "ward": "WARDS",
        "inpatient": "WARDS",
        "admission": "WARDS",
    }
    for alias, dept in aliases.items():
        if alias in low:
            return dept
    return None


def _parse_rating(text: str) -> Optional[int]:
    low = text.lower().strip()
    # Word map with WORD BOUNDARIES so "ok" doesn't match inside "smoke"
    # and "fine" doesn't match inside "define".
    for word, value in sorted(RATING_WORDS.items(), key=lambda kv: -len(kv[0])):
        pattern = r"\b" + re.escape(word) + r"\b"
        if re.search(pattern, low):
            return value
    # Strip duration phrases so "waited 2 hours" is not read as a rating of 2
    cleaned = re.sub(
        r"\b\d+\s*(hours?|hrs?|minutes?|mins?|days?|weeks?|months?|times?)\b",
        "",
        low,
    )
    m = re.search(r"(?:^|[^\d])([1-5])(?:[^\d]|$)", cleaned)
    if m:
        return int(m.group(1))
    return None


def _strip_punct(text: str) -> List[str]:
    """Lowercase, drop punctuation, return whitespace tokens."""
    return re.sub(r"[^\w\s']", " ", text.lower()).split()


def _is_affirmative(text: str) -> bool:
    tokens = _strip_punct(text)
    if not tokens:
        return False
    # A leading negation overrides ("not right", "no thanks")
    if tokens[0] in {"no", "nope", "not", "never"}:
        return False
    return any(t in _YES_TOKENS for t in tokens[:3])


def _is_negative(text: str) -> bool:
    tokens = _strip_punct(text)
    return any(t in _NO_TOKENS for t in tokens[:3])


def _build_summary(session: Session) -> str:
    c = session.collected
    dept_id = c.get("department_id")
    dept_name = DEPARTMENT_NAMES.get(dept_id, dept_id or "—")
    rating = c.get("overall_rating")
    tags = c.get("category_tags") or []
    lines = [
        f"• Department: {dept_name}",
        f"• Rating: {rating}/5" if rating else "• Rating: —",
    ]
    if tags:
        lines.append("• Priorities: " + ", ".join(tags))
    if c.get("detail"):
        lines.append(f'• Note: "{c["detail"]}"')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Question generation (Groq-warmed, canned fallback)
# ---------------------------------------------------------------------------
def _generate_question(step: str, session: Session, canned: str) -> str:
    if AI_MODE != "groq":
        return canned
    try:
        client = ai_engine._get_groq_client()
        last = session.history[-1] if session.history else ""
        response = client.chat.completions.create(
            model=GROQ_LLM_MODEL,
            messages=[
                {"role": "system", "content": QUESTION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Patient just said: \"{last}\"\n"
                        f"Next thing to ask: {canned}"
                    ),
                },
            ],
            temperature=0.7,
            max_tokens=120,
        )
        reply = (response.choices[0].message.content or "").strip()
        return reply if reply else canned
    except Exception as exc:
        print(f"[conversation] question generation failed ({exc}); using canned.")
        return canned


def _question(step: str, session: Session, canned: str) -> dict:
    return {
        "type": "question",
        "message": _generate_question(step, session, canned),
        "conversation_step": step,
    }


# ---------------------------------------------------------------------------
# Turn handling
# ---------------------------------------------------------------------------
def handle_turn(phone_hash: str, user_text: str) -> dict:
    session = get_or_create_session(phone_hash)
    text = (user_text or "").strip()
    session.history.append(text)
    session.touch()
    _save_session(session)

    # 1) Medical guardrail on every turn — never logged
    if ai_engine._is_medical_query(text):
        reset_session(phone_hash)
        return {
            "type": "guardrail",
            "message": (
                "I'm an automated assistant, not a doctor. For medical advice, "
                "diagnosis, or dosage questions, please consult a qualified "
                "healthcare professional at the hospital immediately."
            ),
        }

    # 2) Cancel — abandon the session, log nothing
    if text.lower() in CANCEL_WORDS:
        reset_session(phone_hash)
        return {
            "type": "question",
            "message": (
                "No problem — nothing has been logged. "
                "Is there anything else I can help you with?"
            ),
            "conversation_step": "reset",
        }

    state = session.state
    low = text.lower()

    # ------------------------------------------------------- start (expects department)
    if state == "start":
        dept = _parse_department(text)
        if dept is None:
            return _question("department", session, CANNED_QUESTIONS["department"])
        session.collected["department_id"] = dept
        session.state = "department"
        _save_session(session)
        return _question("rating", session, CANNED_QUESTIONS["rating"])

    # ------------------------------------------------------- department (expects rating)
    if state == "department":
        rating = _parse_rating(text)
        if rating is None:
            return _question("rating", session, CANNED_QUESTIONS["rating"])
        session.collected["overall_rating"] = rating
        session.state = "rating"
        _save_session(session)
        return _question("issues", session, CANNED_QUESTIONS["issues"])

    # ------------------------------------------------------- rating (expects priorities)
    if state == "rating":
        tags = ai_engine._detect_tags(text)
        session.collected["category_tags"] = tags
        session.state = "issues"
        _save_session(session)
        return _question("detail", session, CANNED_QUESTIONS["detail"])

    # ------------------------------------------------------- issues (expects extra detail)
    if state == "issues":
        if not _is_negative(text):
            session.collected["detail"] = text
        session.state = "detail"
        _save_session(session)
        summary = _build_summary(session)
        return {
            "type": "question",
            "message": (
                "Here's what I understood so far:\n"
                f"{summary}\n\n"
                "Is this correct? Reply YES to log your feedback, "
                "or tell me what to change."
            ),
            "conversation_step": "confirm",
        }

    # ------------------------------------------------------- detail (expects yes / change)
    if state == "detail":
        if _is_affirmative(text):
            extracted = _finalize_extraction(session)
            narrative = " ".join(session.history).strip()
            reset_session(phone_hash)
            return {
                "type": "done",
                "extracted": extracted,
                "narrative": narrative,
                "conversation_step": "done",
            }
        if _is_negative(text):
            # Correction path: let the patient redo the whole flow cleanly
            session.collected = {}
            session.state = "start"
            _save_session(session)
            return _question(
                "department",
                session,
                "No problem — let's start the details over. "
                + CANNED_QUESTIONS["department"],
            )
        # Any other reply is treated as a correction / extra note, then re-confirm
        previous = session.collected.get("detail") or ""
        session.collected["detail"] = (previous + " " + text).strip()
        _save_session(session)
        summary = _build_summary(session)
        return {
            "type": "question",
            "message": (
                "Thanks — I've updated the note. Here's what I have:\n"
                f"{summary}\n\n"
                "Reply YES to log your feedback, or keep telling me what to change."
            ),
            "conversation_step": "confirm",
        }

    # Unknown state — safe reset
    reset_session(phone_hash)
    return _question("department", session, CANNED_QUESTIONS["department"])


def _finalize_extraction(session: Session) -> dict:
    """Runs AI extraction over the conversation narrative, then overrides the
    structured fields with the patient's explicit answers."""
    narrative = " ".join(session.history).strip() or "Patient shared feedback through conversation."
    extracted = ai_engine.process_patient_text(narrative)
    if session.collected.get("department_id"):
        extracted["department_id"] = session.collected["department_id"]
    if session.collected.get("overall_rating"):
        extracted["overall_rating"] = session.collected["overall_rating"]
    explicit_tags = session.collected.get("category_tags") or []
    merged = list(dict.fromkeys(explicit_tags + extracted["category_tags"]))
    extracted["category_tags"] = merged
    return extracted
