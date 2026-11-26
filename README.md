---
title: Smriti Shuddhi
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8080
pinned: false
---

# Smriti Shuddhi (स्मृति शुद्धि) — AI Fact Verification & Exact Machine Unlearning

**Smriti Shuddhi** is a full-stack real-time news verification and **Right-to-be-Forgotten machine unlearning** platform:

- **Live Deployed Web Portal (Cloudflare Edge + Assets)**: `https://smritishuddhi.smritishuddhi.workers.dev`
- **Live FastAPI Backend (Google Cloud Run)**: `https://smriti-shuddhi-app-889339834867.asia-south1.run.app`
- **Full Technical, Algorithmic, API & Git Deployment Guide**: Read **[DOCUMENTATION.md](DOCUMENTATION.md)** for complete point-to-point documentation.

---

## Core Capabilities

- **Part 1 — Multi-Aspect Verification (Including Breaking & Future Claims)**:
  - **Track 1 & 2 Hybrid AI**: `deberta-v3-xsmall` + Rank-8 SISA LoRA adapters ($K=5$) + `BAAI/bge-small-en-v1.5` (384-dim) Qdrant HNSW + Supabase `pgvector` HNSW cosine evidence retrieval.
  - **Adversarial & Deep Forensic Layer**: Prompt-injection/leetspeak/homoglyph sanitizer, quantitative baseline anomaly detection (Sensex, Nifty, Gold, Crude Oil, USD/INR, RBI rates, weather bounds), temporal NetworkX/Neo4j knowledge graph + future-policy claim detector, sub-claim partial-truth decomposition, Schema.org `ClaimReview` JSON-LD, and Epistemic Calibration (`ECE` / Brier score).
  - **Real-Time Grounding**: The Guardian Open Platform, 19 multilingual RSS feeds (English/Hindi/Telugu), Google Fact Check Tools API (+ RSS fallback), Open-Meteo live telemetry, Wikidata entity checks, and Gemini (`gemini-3-flash-preview`) synthesis.
- **Part 2 — 5-Strategy Exact Machine Unlearning & Verification**:
  - Live side-by-side execution and evaluation across `baseline_retrain`, `algorithm_1_sisa` ($K=5$ isolated shard retrain), `algorithm_2_svm` (Sherman-Morrison-Woodbury $H^{-1}$ closed-form downdate with Gold $L_2$ parity), `algorithm_3_lora` (Rank-8 sub-slice deactivation with Supabase-persisted mask), and `algorithm_4_hybrid` (Unified Engine).
  - **System-Wide Purge & Clearance Certificate**: Atomically clears SISA shard weights/CSVs, SVM inverse Hessian, LoRA slices, Qdrant & Supabase `pgvector`, temporal graph nodes, `training_samples`, `news` status, and SHA-256 cache; writes chained SHA-256 proofs to `unlearning_ledger`; broadcasts live clearance notifications over WebSockets; and verifies `ZERO_RESIDUAL_MEMORIZATION` via the Interactive Model Memory Probe.

## Quick Start (Git Clone & Run Locally)

```powershell
git clone https://github.com/HarshithGadipelli/SmritiShuddhi.git
cd SmritiShuddhi
.\scripts\start_project.ps1
```

Or step-by-step:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Edit .env with your Supabase Session Pooler URI (port 5432) and optional API keys
python scripts\generate_demo_dataset.py --rows 1200
python training\train_sisa.py --data data\processed\train.csv
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

See **[DOCUMENTATION.md](DOCUMENTATION.md)** for full mathematical formulations, all 41 API routes, Supabase SQL setup, Cloudflare Workers sync, and GitHub Actions auto-deploy CI/CD instructions.
