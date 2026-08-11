-- ============================================================================
-- HFD — Omnichannel Hospital Feedback & Care Quality Platform (Demo Edition)
-- SQLite Schema (hospital_demo.db)
-- ============================================================================

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- 1. DEPARTMENTS TABLE (Lookup table for hospital wards & service areas)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS departments (
    id TEXT PRIMARY KEY CHECK (length(id) <= 20),
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seed initial default departments
INSERT OR IGNORE INTO departments (id, name) VALUES
    ('OPD',       'Outpatient Department'),
    ('EMERGENCY', 'Accident & Emergency'),
    ('PHARMACY',  'Main Pharmacy'),
    ('BILLING',   'Accounts & Revenue'),
    ('WARDS',     'Inpatient Wards');

-- ----------------------------------------------------------------------------
-- 2. PATIENT_FEEDBACK TABLE (Core table storing raw & AI-classified reviews)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS patient_feedback (
    id TEXT PRIMARY KEY,                        -- UUID v4 string (e.g. 'fb-uuid-9921')
    visit_id TEXT NOT NULL,                     -- Patient visit identifier (e.g. 'VIS-2026-104')
    department_id TEXT NOT NULL,                -- Foreign key to departments(id)
    channel TEXT NOT NULL CHECK (
        channel IN ('NURSE_ASSISTED', 'WHATSAPP_BOT')
    ),
    patient_phone_hash TEXT,                    -- SHA-256 hashed phone number for PII masking
    overall_rating INTEGER NOT NULL CHECK (
        overall_rating >= 1 AND overall_rating <= 5
    ),
    sentiment_score REAL DEFAULT 0.0 CHECK (
        sentiment_score >= -1.0 AND sentiment_score <= 1.0
    ),
    category_tags TEXT DEFAULT '[]',            -- Stored as JSON string array
    raw_comment TEXT,                           -- Plaintext feedback narrative or audio transcript
    summary TEXT,                               -- LLM generated concise issue summary
    is_anonymous INTEGER DEFAULT 0 CHECK (      -- Boolean integer (0 = False, 1 = True)
        is_anonymous IN (0, 1)
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
);

-- Indexes for rapid dashboard queries & filtering
CREATE INDEX IF NOT EXISTS idx_feedback_department ON patient_feedback(department_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON patient_feedback(overall_rating);
CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON patient_feedback(created_at);

-- ----------------------------------------------------------------------------
-- 3. HOSPITAL_ALERTS TABLE (Real-time escalation queue for low ratings)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hospital_alerts (
    id TEXT PRIMARY KEY,                        -- UUID v4 string (e.g. 'alt-uuid-4412')
    feedback_id TEXT NOT NULL,                  -- Foreign key to patient_feedback(id)
    department_id TEXT NOT NULL,                -- Foreign key to departments(id)
    severity TEXT NOT NULL CHECK (
        severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')
    ),
    issue_summary TEXT NOT NULL,                -- Brief explanation of the safety or delay issue
    status TEXT DEFAULT 'OPEN' CHECK (
        status IN ('OPEN', 'RESOLVED')
    ),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (feedback_id) REFERENCES patient_feedback(id) ON DELETE CASCADE,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
);

-- Indexes for alert monitoring & escalation management
CREATE INDEX IF NOT EXISTS idx_alerts_status ON hospital_alerts(status);
CREATE INDEX IF NOT EXISTS idx_alerts_department ON hospital_alerts(department_id);

-- ----------------------------------------------------------------------------
-- 4. ANALYTICAL VIEW — Executive Dashboard Metrics
-- ----------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS v_dashboard_metrics AS
SELECT
    d.id AS department_id,
    d.name AS department_name,
    COUNT(f.id) AS total_feedback_count,
    ROUND(AVG(f.overall_rating), 2) AS average_csat,
    ROUND(AVG(f.sentiment_score), 2) AS average_sentiment,
    SUM(CASE WHEN f.overall_rating <= 2 THEN 1 ELSE 0 END) AS negative_reviews_count,
    SUM(CASE WHEN a.status = 'OPEN' THEN 1 ELSE 0 END) AS active_alerts_count
FROM departments d
LEFT JOIN patient_feedback f ON d.id = f.department_id
LEFT JOIN hospital_alerts a ON f.id = a.feedback_id
GROUP BY d.id, d.name;

-- ----------------------------------------------------------------------------
-- 5. CONVERSATION SESSIONS TABLE (serverless-safe multi-turn WhatsApp intake)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS conversation_sessions (
    phone_hash TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'start',
    collected TEXT NOT NULL DEFAULT '{}',
    history TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL
);
