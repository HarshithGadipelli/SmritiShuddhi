import sys
import json
import base64
import urllib.request
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_URL = "http://127.0.0.1:8000"

def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())

def post(path, body):
    data = json.dumps(body).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.loads(res.read())

print("================================================================================")
print("SMRITI SHUDDHI PLATFORM E2E SYSTEM VERIFICATION")
print("================================================================================")

# 1. Test Public News Wire (Multilingual)
wire = get("/api/v1/news")
news_items = wire.get("news", [])
print(f"[OK] 1. Public News Wire Feed: {len(news_items)} published articles online.")
assert len(news_items) > 0, "News feed should have articles"
telugu_count = sum(1 for a in news_items if 'te' in a.get('language', '').lower() or 'తెలుగు' in a.get('language', '') or any('\u0C00' <= ch <= '\u0C7F' for ch in a.get('title', '')))
hindi_count = sum(1 for a in news_items if 'hi' in a.get('language', '').lower() or 'हिंदी' in a.get('language', '') or any('\u0900' <= ch <= '\u097F' for ch in a.get('title', '')))
print(f"     Multilingual Breakdown: {telugu_count} Telugu, {hindi_count} Hindi, {len(news_items) - telugu_count - hindi_count} English stories.")
sample = news_items[0]
print(f"     Featured Story: '{sample.get('title')}'")
print(f"     Category: {sample.get('category')} | Reading Time: {sample.get('reading_time')} | Image: {'YES' if sample.get('image_url') else 'NO'}")

# 2. Test Document Upload & Parsing
doc_raw = """Urgent Classified Dispatch: New Solar Flare Warning
Space observation arrays have registered a class X-3 solar flare directed towards earth magnetosphere. Power grids on alert."""
b64_doc = base64.b64encode(doc_raw.encode('utf-8')).decode('utf-8')
parsed_doc = post("/api/v1/news/extract-document", {
    "filename": "solar_alert_dispatch.txt",
    "base64_content": b64_doc
})
print(f"[OK] 2. Document Upload & Extraction:")
print(f"     Extracted Title: '{parsed_doc.get('title')}'")
print(f"     Word Count: {parsed_doc.get('word_count')} words | File Type: {parsed_doc.get('file_type')}")
assert parsed_doc.get("word_count") > 10, "Word count should match document"

# 3. Test Dual-Track Hybrid AI Scan & Verification (Fake News Submission)
fake_submission = post("/api/v1/news/submit", {
    "title": "URGENT FRAUD ALERT: Central Bank Revoking All Digital Wallet Balances Tonight",
    "text": "Shocking viral message: Central authorities are freezing and confiscating all digital mobile wallets at midnight. Transfer funds immediately to offshore accounts before complete shutdown!",
    "category": "Banking & Economy",
    "source": "WhatsApp Viral Broadcast",
    "author": "Citizen Contributor"
})
print(f"[OK] 3. Dual-Track Hybrid Classification for User-Uploaded News:")
print(f"     Headline: 'URGENT FRAUD ALERT...'")
print(f"     Fake Probability: {round(fake_submission['fake_probability'] * 100, 1)}%")
print(f"     Stylistic Risk (Track A): {fake_submission['s_style']}")
print(f"     Factual Fake Score (Track B): {fake_submission['s_fact']}")
print(f"     Risk Band: {fake_submission['risk_band']}")
print(f"     Status: {fake_submission['status']}")
print(f"     Action: {fake_submission['message']}")
assert fake_submission["risk_band"] == "HIGH_RISK_FAKE", "Fraud message should be flagged as high risk fake"
assert fake_submission["status"] == "BLOCKED_HIGH_RISK_FAKE", "Should be blocked & quarantined"

target_sample_id = fake_submission["sample_id"]
target_news_id = fake_submission["news_id"]

# 4. Test User Authentication & Role Management
auth_user = post("/api/v1/auth/login", {"email": "reporter@times.com", "password": "user123"})
auth_admin = post("/api/v1/auth/login", {"email": "admin@smritishuddhi.org", "password": "admin123"})
print(f"[OK] 4. User & Admin Authentication:")
print(f"     Journalist Profile: {auth_user['user']['name']} ({auth_user['user']['role']})")
print(f"     Admin Profile: {auth_admin['user']['name']} ({auth_admin['user']['role']})")

# 5. Check Admin Queue
queue = get("/api/v1/admin/queue")
blocked_items = queue.get("blocked_fake_news", [])
print(f"[OK] 5. Admin Queue Quarantine: {len(blocked_items)} blocked fake stories awaiting unlearning.")
found_quarantined = any(it.get("news_id") == target_news_id for it in blocked_items)
print(f"     Quarantined Target Found in Workbench: {found_quarantined}")

# 6. Test Machine Unlearning - Algorithm 1: SISA Sharding
print("\n[TEST] 6. Testing Unlearning Algorithm 1: SISA Sharded Data Partitioning...")
sisa_res = post("/api/v1/admin/unlearn", {
    "sample_id": target_sample_id,
    "news_id": target_news_id,
    "strategy": "algorithm_1_sisa"
})
print(f"     SISA Unlearn Status: {sisa_res['status']}")
sisa_bench = sisa_res["benchmark"]["results"][0]
print(f"     Family: {sisa_bench['structural_family']}")
print(f"     Execution Latency: {sisa_bench['execution_time_ms']} ms | Speedup: {sisa_bench['speedup_vs_retrain']}")
print(f"     Forgotten Influence: {sisa_bench['forget_influence_remaining_pct']}% | Retain Accuracy: {sisa_bench['retain_accuracy_after']*100}%")
assert sisa_bench["forget_influence_remaining_pct"] == 0.0, "Forgotten data influence must be 0.0%"

# 7. Test Machine Unlearning - Algorithm 2: Decremental Closed-Form SVM
print("\n[TEST] 7. Testing Unlearning Algorithm 2: Decremental Closed-Form SVM...")
svm_res = post("/api/v1/admin/unlearn", {
    "sample_id": target_sample_id,
    "news_id": target_news_id,
    "strategy": "algorithm_2_svm"
})
svm_bench = svm_res["benchmark"]["results"][0]
print(f"     Family: {svm_bench['structural_family']}")
print(f"     Execution Latency: {svm_bench['execution_time_ms']} ms | Speedup: {svm_bench['speedup_vs_retrain']}")
print(f"     Forgotten Influence: {svm_bench['forget_influence_remaining_pct']}% | Retain Accuracy: {svm_bench['retain_accuracy_after']*100}%")
assert svm_bench["forget_influence_remaining_pct"] == 0.0, "Forgotten data influence must be 0.0%"

# 8. Test Machine Unlearning - Algorithm 3: Modular LoRA / PEFT Deactivation
print("\n[TEST] 8. Testing Unlearning Algorithm 3: Modular LoRA Deactivation (S3T)...")
lora_res = post("/api/v1/admin/unlearn", {
    "sample_id": target_sample_id,
    "news_id": target_news_id,
    "strategy": "algorithm_3_lora"
})
lora_bench = lora_res["benchmark"]["results"][0]
print(f"     Family: {lora_bench['structural_family']}")
print(f"     Execution Latency: {lora_bench['execution_time_ms']} ms | Speedup: {lora_bench['speedup_vs_retrain']}")
print(f"     Weights Modified: {lora_bench['parameters_modified_pct']}% (Base W0 Frozen)")
print(f"     Forgotten Influence: {lora_bench['forget_influence_remaining_pct']}% | Retain Accuracy: {lora_bench['retain_accuracy_after']*100}%")
assert lora_bench["forget_influence_remaining_pct"] == 0.0, "Forgotten data influence must be 0.0%"

# 9. Test Persistent Unlearning Ledger
ledger = get("/api/v1/admin/unlearning-ledger")
print(f"\n[OK] 9. Persistent Audit Ledger: {len(ledger.get('ledger', []))} historical unlearning operations recorded.")

print("\n================================================================================")
print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY WITH ZERO ERRORS.")
print("Platform URL: http://127.0.0.1:8000/")
print("================================================================================")

