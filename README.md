# Efficient Machine Unlearning for Fake News Detection

Laptop-first major project demonstrating:

- NLP fake-news risk prediction
- MongoDB + MongoDB Compass
- Risk-based admin review (only high-risk articles require admin action)
- Real-time multi-device content propagation with Flask-SocketIO
- SISA-style shard/slice machine unlearning
- Full retraining baseline
- Forget/retain evaluation and runtime benchmarking
- Model versioning and audit logs
- Optional DeBERTa-v3 upgrade path

## 1. Architecture

The default runnable model is a lightweight **HashingVectorizer + SGDClassifier (log-loss)** ensemble arranged as SISA shards/slices. This makes the complete unlearning demonstration practical on a normal laptop.

For research, a separate optional transformer training script is included for **DeBERTa-v3-base**. The transformer is intentionally not enabled by default because training multiple transformer shards can be too heavy for a CPU-only laptop.

Core flow:

User news -> NLP model -> fake probability -> risk band -> low-risk broadcast / high-risk admin queue -> admin remove or unlearn -> SISA selective update -> verification -> model version -> Socket.IO broadcast -> all connected clients.

## 2. Requirements

- Python 3.10+
- MongoDB 7/8 or Docker
- 8 GB RAM minimum recommended; 16 GB+ preferred for transformer experiments
- Windows, Linux, or macOS

## 3. Quick start on Windows

### Create environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Start MongoDB with Docker

```powershell
docker compose up -d mongodb
```

Or use a locally installed MongoDB service.

### Configure

```powershell
copy .env.example .env
```

### Create the runnable demo dataset

```powershell
python scripts/generate_demo_dataset.py --rows 1200
```

### Train the SISA model

```powershell
python training/train_sisa.py --data data/processed/train.csv
```

### Evaluate the base model

```powershell
python evaluation/evaluate_model.py
```

### Start the web application

```powershell
python app.py
```

Open:

- User UI: `http://127.0.0.1:5000/`
- Admin UI: `http://127.0.0.1:5000/admin`

Default demo admin credentials:

- username: `admin`
- password: `admin123`

For phones on the same Wi-Fi, open `http://<LAPTOP-IP>:5000`.

## 4. MongoDB Compass

Connect Compass to:

`mongodb://localhost:27017`

Database:

`fake_news_unlearning`

Useful collections:

- `news`
- `training_samples`
- `removal_requests`
- `unlearning_jobs`
- `model_versions`
- `admin_actions`
- `audit_logs`
- `devices`

## 5. Real datasets for serious experiments

This package contains a synthetic demo dataset so the project runs immediately. For the research evaluation, replace it with licensed/public datasets such as LIAR and FakeNewsNet after downloading them separately and mapping them into the normalized schema:

`sample_id,title,text,label,source,published_date,dataset_source`

The code intentionally does not redistribute external datasets.

## 6. Unlearning experiment

Train the SISA model first, then run:

```powershell
python evaluation/benchmark_unlearning.py --forget-count 1
python evaluation/benchmark_unlearning.py --forget-count 10
python evaluation/benchmark_unlearning.py --forget-count 50
```

The benchmark compares:

- original model
- SISA-unlearned model
- full-retrained reference model

It records runtime and retain/forget metrics in `artifacts/evaluation/`.

## 7. Demo an actual unlearning request

The application includes demo articles seeded from training data. When an admin unlearns a seeded training item, the system:

1. finds its training sample and shard/slice location;
2. reconstructs the affected shard from the affected slice onward;
3. produces a new model version;
4. marks the content revoked;
5. records the job in MongoDB;
6. broadcasts the removal to all connected browsers.

A user-submitted article that is **not** in the training registry can still be removed from the controlled news feed, but the system correctly reports that no model-level unlearning was necessary for that specific item.

## 8. Optional DeBERTa training

Install the optional requirements:

```powershell
pip install -r requirements-optional-transformer.txt
```

Then inspect:

`training/train_deberta.py`

The recommended research design is:

- keep SISA+SGD as the fully runnable laptop baseline;
- train DeBERTa-v3-base on the real historical dataset for classifier quality;
- compare accuracy/F1 and document that transformer-sharded unlearning is a heavier experimental extension.

## 9. Research metrics

The evaluation scripts cover:

- accuracy
- precision
- recall
- F1
- ROC-AUC (when probabilities are available)
- retain-set utility
- forget-set behavior
- SISA unlearning time
- full retraining time
- speed-up

Recommended paper experiments:

1. 1, 10, 50, 100 forgotten samples.
2. 3, 5, and 10 shards.
3. Compare SISA against full retraining.
4. Compare TF-IDF/LR-style baseline against the transformer model.
5. Add membership-inference verification as an advanced extension.

## 10. Important scientific boundary

The classifier predicts **fake-news risk**, not absolute factual truth. The real-time pipeline intentionally uses risk bands so normal low-risk news is not blocked by administrator review. Only high-risk items enter the admin queue in the default policy.
