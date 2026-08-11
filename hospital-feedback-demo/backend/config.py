"""Environment variables & constants for the HFD demo backend."""
import os

from dotenv import load_dotenv

# Load .env if present (no-op when absent)
load_dotenv()

# ---------------------------------------------------------------------------
# Core paths
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.getenv("SQLITE_DB_PATH", os.path.join(BASE_DIR, "hospital_demo.db"))
SCHEMA_FILE = os.path.join(os.path.dirname(BASE_DIR), "schema.sql")

# ---------------------------------------------------------------------------
# Database backend (Postgres on Vercel, SQLite for local dev)
# ---------------------------------------------------------------------------
# When DATABASE_URL is set (e.g. a Neon Postgres connection string) the app
# uses Postgres; otherwise it falls back to the local SQLite file. Neon
# requires TLS, so an explicit sslmode is appended when missing.
DATABASE_URL = os.getenv("DATABASE_URL", "")
if DATABASE_URL and "sslmode" not in DATABASE_URL:
    DATABASE_URL += ("&" if "?" in DATABASE_URL else "?") + "sslmode=require"

DB_BACKEND = "postgres" if DATABASE_URL else "sqlite"

# ---------------------------------------------------------------------------
# Groq Cloud API
# ---------------------------------------------------------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
GROQ_WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3")

# When no API key is configured the engine transparently falls back to a
# deterministic offline extractor so the demo remains fully functional.
AI_MODE = "groq" if GROQ_API_KEY else "offline"

# ---------------------------------------------------------------------------
# Security / PII
# ---------------------------------------------------------------------------
SALT_SECRET = os.getenv("SALT_SECRET", "demo_salt_123")

# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------
VALID_DEPARTMENTS = {"OPD", "EMERGENCY", "PHARMACY", "BILLING", "WARDS"}

DEPARTMENT_NAMES = {
    "OPD": "Outpatient Department",
    "EMERGENCY": "Accident & Emergency",
    "PHARMACY": "Main Pharmacy",
    "BILLING": "Accounts & Revenue",
    "WARDS": "Inpatient Wards",
}

ALLOWED_TAGS = [
    "LONG_WAIT",
    "STAFF_COURTESY",
    "CLEANLINESS",
    "DRUG_AVAILABILITY",
    "BILLING_DELAY",
    "QUALITY_OF_CARE",
    "DIRTY_FACILITY",
]

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
