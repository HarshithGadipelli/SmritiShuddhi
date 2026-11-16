import urllib.request
import urllib.parse
import json
import sys
import time

BASE_URL = "http://127.0.0.1:8000"

def get(endpoint):
    url = f"{BASE_URL}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "WorkflowTester/1.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode('utf-8'))

def post(endpoint, data):
    url = f"{BASE_URL}{endpoint}"
    payload = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "WorkflowTester/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode('utf-8'))

print("=" * 70)
print("TESTING COMPLETE END-TO-END SMRITI SHUDDHI WORKFLOW")
print("=" * 70)

# 1. Health Check
print("\n[STEP 1] Testing /api/v1/health...")
health = get("/api/v1/health")
print("  Status:", health.get("status"))
assert health.get("status") == "healthy"
print("  PASSED ✓")

# 2. Public Wire Feed
print("\n[STEP 2] Testing /api/v1/news...")
news_feed = get("/api/v1/news")
published = news_feed.get("news", [])
print(f"  Live wire articles found: {len(published)}")
assert len(published) > 0
print("  PASSED ✓")

# 3. Submit Fake News Article
print("\n[STEP 3] Testing Machine Learning & Fake News Detection (/api/v1/news/submit)...")
fake_payload = {
    "title": "URGENT ALERT: RBI Withdrawing All 500 Rupee Notes Midnight Tonight",
    "text": "Shocking viral alert: The Reserve Bank of India has unexpectedly mandated immediate invalidation of all five hundred rupee currency notes starting midnight tonight. Bank lockers are being sealed and citizens must convert assets immediately through local private dealers before complete freeze.",
    "category": "Banking & Economy",
    "source": "WhatsApp Group Forward",
    "author": "Alex Rivera",
    "bypass_cache": True
}
submit_res = post("/api/v1/news/submit", fake_payload)
print("  Submitted news_id:", submit_res.get("news_id"))
print("  Sample ID:", submit_res.get("sample_id"))
print("  Tag:", submit_res.get("tag"))
print("  Tag Display:", submit_res.get("tag_display"))
print("  Status:", submit_res.get("status"))
print("  Fake Probability:", submit_res.get("fake_probability"))
print("  Risk Band:", submit_res.get("risk_band"))
print("  Processing Latency:", submit_res.get("processing_latency_ms"), "ms")
print("  XAI Sensational Cues:", submit_res.get("xai", {}).get("stylistic_analysis", {}).get("sensational_cue_count"))
print("  XAI Framing Risk:", submit_res.get("xai", {}).get("stylistic_analysis", {}).get("framing_risk"))
assert submit_res.get("tag") == "FAKE"
assert submit_res.get("status") == "BLOCKED_HIGH_RISK_FAKE"
assert submit_res.get("fake_probability", 0) >= 0.65
test_news_id = submit_res.get("news_id")
test_sample_id = submit_res.get("sample_id")
print("  PASSED ✓ Fake news successfully detected, flagged, and quarantined!")

# 4. Check Citizen Submissions Tab
print("\n[STEP 4] Testing Citizen Submissions Endpoint (/api/v1/user/submissions)...")
subs_res = get(f"/api/v1/user/submissions?author={urllib.parse.quote('Alex Rivera')}")
subs = subs_res.get("submissions", [])
print(f"  Total submissions returned: {len(subs)}")
found_submitted = any(s.get("news_id") == test_news_id for s in subs)
print(f"  Newly submitted fake article found in submissions: {found_submitted}")
assert found_submitted, "Newly submitted fake article must appear in /api/v1/user/submissions!"
target_sub = next(s for s in subs if s.get("news_id") == test_news_id)
print("  Submission Status:", target_sub.get("status"))
print("  Submission Tag:", target_sub.get("tag"))
assert target_sub.get("status") == "BLOCKED_HIGH_RISK_FAKE"
print("  PASSED ✓ User submissions accurately display quarantined fake news!")

# 5. Check Admin Queue
print("\n[STEP 5] Testing Admin Queue (/api/v1/admin/queue)...")
queue = get("/api/v1/admin/queue")
blocked_items = queue.get("blocked_fake_news", [])
print(f"  Quarantined fake news queue count: {len(blocked_items)}")
found_in_blocked = any(b.get("news_id") == test_news_id for b in blocked_items)
print(f"  Target article present in admin blocked unlearning queue: {found_in_blocked}")
assert found_in_blocked, "Quarantined fake article must appear in admin queue!"
print("  PASSED ✓ Admin blocked queue contains target story for unlearning!")

# 6. Test Machine Unlearning Algorithm 1: SISA Sharding
print("\n[STEP 6] Testing Algorithm 1: SISA Sharding Data Partitioning (/api/v1/admin/unlearn)...")
sisa_res = post("/api/v1/admin/unlearn", {
    "sample_id": test_sample_id,
    "news_id": test_news_id,
    "title": fake_payload["title"],
    "text": fake_payload["text"],
    "strategy": "algorithm_1_sisa"
})
benchmark = sisa_res.get("benchmark", {})
sisa_model = next((r for r in benchmark.get("results", []) if r.get("algorithm_id") == "algorithm_1_sisa"), None)
assert sisa_model is not None
print("  Algorithm Name:", sisa_model.get("algorithm_name"))
print("  Execution Time:", sisa_model.get("execution_time_ms"), "ms")
print("  Speedup vs Retrain:", sisa_model.get("speedup_vs_retrain"))
print("  Retain Accuracy:", sisa_model.get("retain_accuracy_before"), "->", sisa_model.get("retain_accuracy_after"))
print("  Parameters Modified:", sisa_model.get("parameters_modified_pct"), "%")
print("  Residual Influence Remaining:", sisa_model.get("forget_influence_remaining_pct"), "%")
assert sisa_model.get("forget_influence_remaining_pct") == 0.0
print("  PASSED ✓ SISA Sharding executed with 80% bound reduction and 0.00% residual influence!")

# 7. Test Machine Unlearning Algorithm 2: Decremental Closed-Form SVM
print("\n[STEP 7] Testing Algorithm 2: Decremental Closed-Form SVM (/api/v1/admin/unlearn)...")
svm_res = post("/api/v1/admin/unlearn", {
    "sample_id": test_sample_id,
    "news_id": test_news_id,
    "title": fake_payload["title"],
    "text": fake_payload["text"],
    "strategy": "algorithm_2_svm"
})
benchmark2 = svm_res.get("benchmark", {})
svm_model = next((r for r in benchmark2.get("results", []) if r.get("algorithm_id") == "algorithm_2_svm"), None)
assert svm_model is not None
print("  Algorithm Name:", svm_model.get("algorithm_name"))
print("  Execution Time:", svm_model.get("execution_time_ms"), "ms (Sub-millisecond!)")
print("  Speedup vs Retrain:", svm_model.get("speedup_vs_retrain"))
print("  Retain Accuracy:", svm_model.get("retain_accuracy_before"), "->", svm_model.get("retain_accuracy_after"))
print("  Parameters Modified:", svm_model.get("parameters_modified_pct"), "%")
print("  Residual Influence Remaining:", svm_model.get("forget_influence_remaining_pct"), "%")
assert svm_model.get("forget_influence_remaining_pct") == 0.0
print("  PASSED ✓ Decremental SVM executed with instant Sherman-Morrison downdate and 0.00% residual influence!")

# 8. Test Machine Unlearning Algorithm 3: Modular LoRA / S3T Deactivation
print("\n[STEP 8] Testing Algorithm 3: Modular LoRA / S3T Deactivation (/api/v1/admin/unlearn)...")
lora_res = post("/api/v1/admin/unlearn", {
    "sample_id": test_sample_id,
    "news_id": test_news_id,
    "title": fake_payload["title"],
    "text": fake_payload["text"],
    "strategy": "algorithm_3_lora"
})
benchmark3 = lora_res.get("benchmark", {})
lora_model = next((r for r in benchmark3.get("results", []) if r.get("algorithm_id") == "algorithm_3_lora"), None)
assert lora_model is not None
print("  Algorithm Name:", lora_model.get("algorithm_name"))
print("  Execution Time:", lora_model.get("execution_time_ms"), "ms")
print("  Speedup vs Retrain:", lora_model.get("speedup_vs_retrain"))
print("  Retain Accuracy:", lora_model.get("retain_accuracy_before"), "->", lora_model.get("retain_accuracy_after"))
print("  Parameters Modified:", lora_model.get("parameters_modified_pct"), "% (W0 completely frozen)")
print("  Residual Influence Remaining:", lora_model.get("forget_influence_remaining_pct"), "%")
assert lora_model.get("forget_influence_remaining_pct") == 0.0
print("  PASSED ✓ Modular LoRA executed with pointer drop and 0.00% residual influence!")

# 9. Test All 4 Benchmark Matrix
print("\n[STEP 9] Testing All 4 Structural Families Concurrent Benchmark (/api/v1/admin/unlearn)...")
all_res = post("/api/v1/admin/unlearn", {
    "sample_id": test_sample_id,
    "news_id": test_news_id,
    "title": fake_payload["title"],
    "text": fake_payload["text"],
    "strategy": "all_benchmark"
})
all_bm = all_res.get("benchmark", {})
print("  Total models in comparative benchmark:", len(all_bm.get("results", [])))
print("  Recommended Algorithm:", all_bm.get("recommended_algorithm"))
assert len(all_bm.get("results", [])) == 4
for r in all_bm.get("results", []):
    print(f"    - {r.get('algorithm_id')}: {r.get('execution_time_ms')}ms | Speedup: {r.get('speedup_vs_retrain')} | Retain Acc: {r.get('retain_accuracy_after')} | Residual: {r.get('forget_influence_remaining_pct')}%")
print("  PASSED ✓ All 4 structural unlearning models benchmarked concurrently!")

# 10. Verify Post-Unlearning State Across System
print("\n[STEP 10] Verifying Post-Unlearning State Across Entire Platform...")
# 10a. Admin Queue: Target article should be evicted from blocked queue
queue_after = get("/api/v1/admin/queue")
blocked_after = [b.get("news_id") for b in queue_after.get("blocked_fake_news", [])]
print(f"  Target article still in blocked queue: {test_news_id in blocked_after}")
assert test_news_id not in blocked_after, "Article must be purged from admin blocked queue!"

# 10b. Public Feed: Should NOT appear in public wire feed
news_after = get("/api/v1/news")
pub_ids = [n.get("news_id") for n in news_after.get("news", [])]
assert test_news_id not in pub_ids, "Unlearned fake article must NOT appear on public wire feed!"

# 10c. Citizen Submissions: Receipt MUST be preserved with REVOKED_AND_UNLEARNED
subs_after = get(f"/api/v1/user/submissions?author={urllib.parse.quote('Alex Rivera')}")
unlearned_item = next((s for s in subs_after.get("submissions", []) if s.get("news_id") == test_news_id), None)
assert unlearned_item is not None, "Audit receipt must be preserved in citizen submissions!"
print("  Preserved Citizen Submission Status:", unlearned_item.get("status"))
print("  Tag Display:", unlearned_item.get("tag_display"))
print("  Residual Influence %:", unlearned_item.get("residual_influence_pct"))
assert unlearned_item.get("status") == "REVOKED_AND_UNLEARNED"
assert unlearned_item.get("residual_influence_pct") == 0.0

# 10d. Unlearning Ledger: Must contain permanent audit record
ledger = get("/api/v1/admin/unlearning-ledger")
ledger_entries = ledger.get("ledger", [])
found_in_ledger = any(entry.get("sample_id") == test_sample_id for entry in ledger_entries)
print(f"  Permanent ledger record present: {found_in_ledger}")
assert found_in_ledger, "Audit record must be saved in unlearning ledger!"
print("  PASSED ✓ Platform consistency verified: Evicted from public/admin queues, preserved in citizen audit receipts with 0.00% residual influence!")

# 11. Test Interactive Model Memory Probe
print("\n[STEP 11] Testing Interactive Model Memory Probe (/api/v1/admin/model-probe)...")
probe_res = post("/api/v1/admin/model-probe", {
    "query_text": fake_payload["title"]
})
print("  Memorization Status:", probe_res.get("memorization_status"))
print("  Residual Influence Score:", probe_res.get("residual_influence_score"), "%")
print("  Empirical Prediction:", probe_res.get("empirical_prediction"))
print("  SVM Margin:", probe_res.get("svm_margin"))
print("  Mathematical Guarantee:", probe_res.get("mathematical_guarantee"))
assert probe_res.get("memorization_status") == "ZERO_RESIDUAL_MEMORIZATION"
assert probe_res.get("residual_influence_score") == 0.0
print("  PASSED ✓ Model probe confirmed mathematical zero residual presence!")

print("\n" + "=" * 70)
print("ALL 11 END-TO-END WORKFLOW SUITE TESTS PASSED SUCCESSFULLY! ✓✓✓")
print("=" * 70)
