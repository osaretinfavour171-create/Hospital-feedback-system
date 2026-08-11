"""PII anonymization — SHA-256 phone number hashing.

Masks personally identifiable information (patient phone numbers) prior to
persistence, while keeping records linkable for follow-up care.
"""
import hashlib

from config import SALT_SECRET


def hash_phone(phone_number: str | None) -> str | None:
    """Hash a phone number with salted SHA-256. Returns None for empty input."""
    if not phone_number:
        return None
    normalized = "".join(ch for ch in phone_number if ch.isdigit() or ch == "+")
    return hashlib.sha256((normalized + SALT_SECRET).encode("utf-8")).hexdigest()
