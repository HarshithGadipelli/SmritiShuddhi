---
title: Smriti Shuddhi
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8080
pinned: false
---

# Smriti Shuddhi — Fake News Verification & Exact Machine Unlearning

Full-stack verification and right-to-be-forgotten platform powered by:
- **Part 1 (Detection & Real-Time Grounding)**: Frozen `deberta-v3-xsmall` + PyTorch Rank-8 LoRA adapters, `BAAI/bge-small-en-v1.5` vector retrieval across Qdrant + Supabase `pgvector`, adversarial obfuscation guard, structured NER/SPO & quote lineage, Google Fact Check API, Open-Meteo weather grounding, sub-claim partial-truth decomposition, live RSS/Guardian/TheNewsAPI ingestion, website diffusion tracking, and optional Gemini synthesis.
- **Part 2 (Exact Machine Unlearning)**: 5-strategy comparative suite (`baseline_retrain`, `algorithm_1_sisa`, `algorithm_2_svm` Sherman-Morrison-Woodbury downdates, `algorithm_3_lora` rank-8 sub-slice masking, and `algorithm_4_hybrid`), chained SHA-256 `unlearning_ledger`, Model Residual Memory Probe, and Supabase `app_settings` + `training_samples` persistence across stateless container restarts.

## Environment Secrets
Configure these runtime secrets in your Space Settings / Cloud Run service (never commit `.env`):
- `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY`
- `GUARDIAN_API_KEY`, `THE_NEWS_API_TOKEN`, `GOOGLE_FACTCHECK_API_KEY`, `GEMINI_API_KEY`
- Optional: `NEWS_API_KEY`, `GNEWS_API_KEY`, `SECRET_KEY`, `ALLOWED_ORIGINS`
