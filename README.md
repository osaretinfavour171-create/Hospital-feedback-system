# 🏥 HFD — Omnichannel Hospital Feedback & Care Quality Platform (Demo Edition)

A lightweight proof-of-concept that demonstrates end-to-end hospital feedback collection:
**dual-channel ingestion → AI extraction → safety guardrails → real-time alert escalation →
executive quality dashboard** — all running locally on a single PC at **$0 hosting cost**.

Built from the specifications in the `HFD` design documents (PRD, SDD, Engineering Plan,
Database Schema, Appflow, Design Brief).

---

## ✨ What it does

| Tab | Channel | What you can do |
| --- | --- | --- |
| **Nurse-Assisted Entry** | SmartClinic EHR modal | Log a patient rating in a 3-step form (< 30 s): context → color-coded rating cards → issue chips |
| **WhatsApp Simulator** | Patient WhatsApp channel | Type a message or record a voice note; watch the Groq AI pipeline extract structured JSON, hash the phone, and evaluate escalation |
| **Executive Dashboard** | Quality management | Live CSAT KPIs, department heatmap, and a real-time escalation alert queue with in-place "Mark Resolved" |

**Automatic behaviors (per the spec):**
- 🛡️ **Medical guardrail** — advice/dosage questions get a friendly refusal and are **never logged**
- 🔴 **Auto-escalation** — rating ≤ 2 or a critical issue creates a `HIGH`/`CRITICAL` alert in `hospital_alerts`
- 🔐 **PII protection** — phone numbers are salted SHA-256 hashed before storage
- 📊 **Live dashboard** — CSAT, NPS proxy, per-department heatmap, alert queue (auto-refresh)

---

## 🚀 Quickstart

### Prerequisites
- **Python 3.10+** (tested on 3.13)
- **Node.js 18+** (tested on 26)

### 1. Start the backend

```bash
cd backend
py -3 -m pip install -r requirements.txt
py -3 -m uvicorn main:app --reload --port 8000
```

> Swagger docs: http://127.0.0.1:8000/docs
>
> The first run auto-creates `hospital_demo.db` and seeds the 5 departments.

### 2. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

### 3. Open the app

**http://localhost:5173**

Suggested demo flow:
1. **Nurse tab** → department → rating **1** → chip **Long Wait** → Submit → watch the toast
2. **Dashboard tab** → see the new `HIGH` alert appear instantly → **Mark Resolved**
3. **WhatsApp tab** → send *"The pharmacy wait time was 2 hours today!"* → watch the AI pipeline log
4. **WhatsApp tab** → send *"What dosage of Amoxicillin should I give my child?"* → guardrail refusal

---

## 🤖 AI modes

| Mode | When | Capabilities |
| --- | --- | --- |
| **Groq (live)** | `GROQ_API_KEY` set in `backend/.env` | LLM extraction (`llama-3.3-70b-versatile`), voice transcription (`whisper-large-v3`) |
| **Offline (fallback)** | No key | Deterministic rule-based extraction — everything works **except voice-note transcription** |

Get a free key at <https://console.groq.com/keys> (free tier ≈ 14,400 requests/day), then:

```bash
cp backend/.env.example backend/.env   # then paste your key
```

---

## 🗄️ Database

Single-file SQLite (`backend/hospital_demo.db`) with 3 tables + 1 view:

- `departments` — OPD, EMERGENCY, PHARMACY, BILLING, WARDS
- `patient_feedback` — core feedback records (rating, sentiment, tags, summary, phone hash)
- `hospital_alerts` — escalation queue (severity, status OPEN/RESOLVED)
- `v_dashboard_metrics` — executive metrics view

Schema lives in [`schema.sql`](schema.sql).

---

## 🔌 API surface

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/feedback/nurse` | Nurse-assisted structured feedback |
| `POST` | `/api/v1/feedback/whatsapp/text` | Patient text → AI extraction |
| `POST` | `/api/v1/feedback/whatsapp/audio` | Voice note → Whisper → AI extraction |
| `GET` | `/api/v1/dashboard/metrics` | CSAT / sentiment / heatmap aggregates |
| `GET` | `/api/v1/dashboard/alerts` | Alert queue (`?status=OPEN`) |
| `PATCH` | `/api/v1/alerts/{id}` | Resolve an alert |
| `GET` | `/api/v1/health` | Health + AI mode |

---

## 📁 Structure

```
hospital-feedback-demo/
├── backend/
│   ├── main.py          # FastAPI app & routes
│   ├── database.py      # SQLite connection, schema init, CRUD
│   ├── ai_engine.py     # Groq LLM/Whisper + offline fallback extractor
│   ├── schemas.py       # Pydantic contracts
│   ├── anonymizer.py    # SHA-256 phone hashing
│   ├── config.py        # Env vars & constants
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx                  # Tab shell
│       ├── components/
│       │   ├── NurseEntryModal.jsx    # 3-step nurse form
│       │   ├── WhatsAppSimulator.jsx  # Chat + AI pipeline log + voice
│       │   └── ExecutiveDashboard.jsx # KPIs, heatmap, alerts
│       └── api.js                   # API client
├── schema.sql
└── README.md
```

---

## 🎨 Design

"Healing Teal" design system per the design brief: warm sand canvas (`#FDFBF7`),
deep teal primary (`#0D9488`), rose/amber/emerald rating tiers, Inter typography,
12px card radius, WCAG-AA text contrast, 44px touch targets.

## 📝 Notes & limitations (PoC)

- WhatsApp is a **simulator**, not a live Meta Business API integration.
- Voice transcription needs a Groq API key (offline mode falls back gracefully).
- Data is local-only SQLite; no auth — fine for a demo, not for production.
