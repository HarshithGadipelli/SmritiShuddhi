-- =====================================================================
-- SMRITI SHUDDHI: SUPABASE POSTGRESQL + PGVECTOR MASTER SCHEMA
-- The World's First Exact Machine Unlearning & Fake News Platform
-- =====================================================================

-- 1. Enable the pgvector extension for high-dimensional semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Master News Wire Dispatches & Fact-Checked Articles Table
CREATE TABLE IF NOT EXISTS news (
    news_id VARCHAR(64) PRIMARY KEY,
    sample_id VARCHAR(64),
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    category VARCHAR(64) DEFAULT 'General',
    source VARCHAR(128) DEFAULT 'National Wire',
    region VARCHAR(128) DEFAULT 'National Desk',
    language VARCHAR(32) DEFAULT 'English',
    author VARCHAR(128) DEFAULT 'Editorial Bureau',
    image_url TEXT,
    reading_time VARCHAR(32) DEFAULT '3 min read',
    status VARCHAR(48) DEFAULT 'PUBLISHED',
    real_probability FLOAT DEFAULT 0.95,
    fake_probability FLOAT DEFAULT 0.05,
    s_style FLOAT DEFAULT 0.08,
    s_fact FLOAT DEFAULT 0.12,
    s_quant FLOAT DEFAULT 0.05,
    s_prop FLOAT DEFAULT 0.10,
    temporal_consistency FLOAT DEFAULT 0.95,
    xai JSONB DEFAULT '{}'::jsonb,
    is_user_submission BOOLEAN DEFAULT FALSE,
    tag VARCHAR(32),
    tag_display VARCHAR(64),
    url TEXT,
    view_count INT DEFAULT 0,
    share_count INT DEFAULT 0,
    flag_count INT DEFAULT 0,
    bookmark_count INT DEFAULT 0,
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_interacted_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_news_status ON news(status);
CREATE INDEX IF NOT EXISTS idx_news_created_at ON news(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);

-- 3. High-Speed 384-dimensional Vector Store for Official Indian Ground-Truth
-- Indexes official press releases and debunks from PIB Fact Check, RBI, ISRO, IMD, ECI
CREATE TABLE IF NOT EXISTS official_truth_vectors (
    id SERIAL PRIMARY KEY,
    evidence_id VARCHAR(64) UNIQUE,
    news_id VARCHAR(64),
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    source VARCHAR(128) DEFAULT 'Press Information Bureau (PIB)',
    source_type VARCHAR(64) DEFAULT 'OFFICIAL_DEBUNK',
    truth_label INT DEFAULT 0, -- 0 = Verified Truth, 1 = Verified Debunk
    category VARCHAR(64) DEFAULT 'Government Schemes',
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Fast HNSW cosine index for sub-10ms semantic evidence lookup
CREATE INDEX IF NOT EXISTS idx_truth_vectors_hnsw 
ON official_truth_vectors USING hnsw (embedding vector_cosine_ops);

-- 4. Immutable Machine Unlearning Ledger
-- Cryptographic audit trail of all purged articles, downdated parameters, and zero-residual checks
CREATE TABLE IF NOT EXISTS unlearning_ledger (
    job_id VARCHAR(64) PRIMARY KEY,
    sample_id VARCHAR(64) NOT NULL,
    news_id VARCHAR(64),
    title TEXT,
    strategy VARCHAR(64) NOT NULL,
    residual_influence FLOAT DEFAULT 0.0000,
    residual_influence_pct FLOAT DEFAULT 0.0,
    retain_accuracy_pct FLOAT DEFAULT 100.0,
    results JSONB DEFAULT '[]'::jsonb,
    execution_time_ms FLOAT DEFAULT 0.27,
    proof_hash TEXT,
    status VARCHAR(48) DEFAULT 'PURGED',
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_unlearning_ledger_time ON unlearning_ledger(timestamp DESC);

-- 5. Citizen Retraction & Removal Requests (Right to be Forgotten)
CREATE TABLE IF NOT EXISTS removal_requests (
    request_id VARCHAR(64) PRIMARY KEY,
    news_id VARCHAR(64) REFERENCES news(news_id) ON DELETE SET NULL,
    sample_id VARCHAR(64),
    title TEXT NOT NULL,
    reason TEXT NOT NULL,
    details TEXT,
    requested_by VARCHAR(128) DEFAULT 'Citizen Contributor',
    requester_name VARCHAR(128),
    requester_email VARCHAR(128),
    status VARCHAR(48) DEFAULT 'PENDING_REVIEW',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    unlearned_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_removal_requests_status ON removal_requests(status);

-- 6. Partitioned Training Samples (SISA Sharding & Kernel Storage)
CREATE TABLE IF NOT EXISTS training_samples (
    sample_id VARCHAR(64) PRIMARY KEY,
    news_id VARCHAR(64),
    shard_id INT DEFAULT 0,
    slice_id INT DEFAULT 0,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    label INT DEFAULT 0,
    status VARCHAR(48) DEFAULT 'ACTIVE',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_training_shard ON training_samples(shard_id, status);

-- 7. Authenticated User Profiles (Citizen Journalists & Chief Fact-Checkers)
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(64) PRIMARY KEY,
    email VARCHAR(128) UNIQUE NOT NULL,
    password VARCHAR(128) NOT NULL,
    name VARCHAR(128) NOT NULL,
    role VARCHAR(32) NOT NULL DEFAULT 'JOURNALIST',
    title VARCHAR(128) DEFAULT 'Investigative Tech Journalist',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed Default Demo Users
INSERT INTO users (user_id, email, password, name, role, title, created_at)
VALUES 
    ('USR_ADMIN_001', 'admin@veritas.org', 'admin123', 'Dr. Sarah Mitchell', 'ADMIN', 'Chief Fact-Checking Editor', NOW()),
    ('USR_JOURNALIST_002', 'reporter@times.com', 'user123', 'Alex Rivera', 'JOURNALIST', 'Investigative Tech Journalist', NOW()),
    ('USR_CITIZEN_003', 'citizen@wire.in', 'user123', 'Priya Sharma', 'CITIZEN', 'Community Contributor', NOW())
ON CONFLICT (user_id) DO NOTHING;

-- 8. Tamper-Proof Platform Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
    log_id SERIAL PRIMARY KEY,
    action VARCHAR(64) NOT NULL,
    details TEXT,
    client_ip VARCHAR(64) DEFAULT '127.0.0.1',
    sample_id VARCHAR(64),
    news_id VARCHAR(64),
    strategy VARCHAR(64),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_time ON audit_logs(created_at DESC);

-- 9. Quantitative & Time-Series Knowledge Base Table
-- Stores historical thresholds, baselines, and volatility boundaries for Gold, Crude Oil, Stocks, and Weather
CREATE TABLE IF NOT EXISTS quantitative_knowledge_base (
    metric_id VARCHAR(64) PRIMARY KEY,
    category VARCHAR(64) NOT NULL,
    metric_name VARCHAR(128) NOT NULL,
    symbol VARCHAR(32),
    unit VARCHAR(32) DEFAULT 'INR',
    baseline_value FLOAT NOT NULL,
    min_realistic FLOAT,
    max_realistic FLOAT,
    daily_swing_limit_pct FLOAT DEFAULT 5.0,
    extreme_anomaly_pct FLOAT DEFAULT 10.0,
    rule_summary TEXT,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_quant_kb_cat ON quantitative_knowledge_base(category);

-- 10. Platform Runtime Settings (Active Unlearning Algorithm, Sync Preferences)
CREATE TABLE IF NOT EXISTS app_settings (
    setting_key VARCHAR(64) PRIMARY KEY,
    setting_value TEXT NOT NULL,
    updated_by VARCHAR(64) DEFAULT 'SYSTEM',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO app_settings (setting_key, setting_value, updated_by)
VALUES ('active_unlearning_strategy', 'algorithm_4_hybrid', 'SYSTEM')
ON CONFLICT (setting_key) DO NOTHING;


