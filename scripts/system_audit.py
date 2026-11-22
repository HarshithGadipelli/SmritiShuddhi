import requests
import json
import time

BASE_URL = "http://127.0.0.1:8000"

print("==================================================")
print(" SMRITI SHUDDHI // SYSTEM COMPREHENSIVE AUDIT ")
print("==================================================")

def test_endpoint(name, method, url, payload=None, expected_status=200):
    start = time.perf_counter()
    try:
        if method == "GET":
            r = requests.get(f"{BASE_URL}{url}", timeout=10)
        elif method == "POST":
            r = requests.post(f"{BASE_URL}{url}", json=payload, timeout=10)
        elapsed = (time.perf_counter() - start) * 1000.0
        
        status_ok = (r.status_code == expected_status)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text[:100]
        
        result_str = "PASS" if status_ok else "FAIL"
        print(f"[{result_str}] {name} ({method} {url}) - Status: {r.status_code} ({elapsed:.1f}ms)")
        if not status_ok:
            print(f"       Response: {data}")
        return status_ok, data
    except Exception as e:
        print(f"[FAIL] {name} ({method} {url}) - Exception: {e}")
        return False, str(e)

# 1. Health check
test_endpoint("Health Check", "GET", "/api/v1/health")

# 2. Get published news
ok, news = test_endpoint("Get Published News", "GET", "/api/v1/news")
if ok and isinstance(news, list):
    print(f"       -> Retrieved {len(news)} published articles")

# 3. Submit Authentic News
ok, pub_res = test_endpoint("Submit Authentic News", "POST", "/api/v1/news/submit", {
    "title": "ISRO Commences Integration of Next-Generation Launch Vehicle Stages",
    "text": "Indian Space Research Organisation has officially started stage integration for its upcoming orbital heavy payload vehicle at Sriharikota.",
    "source": "ISRO Press Office",
    "author": "Bureau Reporter",
    "category": "Science & Space",
    "bypass_cache": True
})
if ok:
    print(f"       -> Tag: {pub_res.get('tag')} | Fake Prob: {pub_res.get('fake_probability')*100:.1f}%")

# 4. Submit Vague/Partial Truth (Inventor case)
ok, mod_res = test_endpoint("Submit Generic/Vague Claim", "POST", "/api/v1/news/submit", {
    "title": "an inventor invented an invention in india",
    "text": "an inventor invented an invention in india for rural technology and agricultural processing.",
    "source": "Citizen Post",
    "author": "Anonymous",
    "category": "Technology & AI",
    "bypass_cache": True
})
if ok:
    print(f"       -> Tag: {mod_res.get('tag')} | Risk: {mod_res.get('risk_band')} | Fake Prob: {mod_res.get('fake_probability')*100:.1f}%")

# 5. Submit Critical Commodity Anomaly (Fake crude crash)
ok, fake_res = test_endpoint("Submit Critical Commodity Anomaly", "POST", "/api/v1/news/submit", {
    "title": "Brent crude crashes to 12 dollars per barrel today",
    "text": "Energy markets shattered as crude plunges to 12 dollars per barrel overnight after surprise production surge.",
    "source": "Viral Blog",
    "author": "Anonymous",
    "category": "Banking & Economy",
    "bypass_cache": True
})
if ok:
    print(f"       -> Tag: {fake_res.get('tag')} | Status: {fake_res.get('status')} | Fake Prob: {fake_res.get('fake_probability')*100:.1f}%")

# 6. Admin Queue
ok, queue = test_endpoint("Get Admin Review Queue", "GET", "/api/v1/admin/queue")
if ok and isinstance(queue, list):
    print(f"       -> Queue has {len(queue)} pending items")

# 7. Unlearning Benchmark Test
if ok and fake_res and "sample_id" in fake_res:
    target_sample = fake_res["sample_id"]
    test_endpoint("Execute Unlearning Benchmark", "POST", "/api/v1/admin/unlearn", {
        "sample_id": target_sample,
        "strategy": "all_benchmark"
    })

# 8. Model Probe Verification
test_endpoint("Model Memory Probe", "POST", "/api/v1/admin/model-probe", {
    "query_text": "Brent crude crashes to 12 dollars per barrel"
})

# 9. AI Copilot
test_endpoint("Admin AI Copilot", "POST", "/api/v1/admin/copilot", {
    "query": "What is the status of the unlearning queue and model health?"
})

# 10. Audit Ledger
test_endpoint("Get Unlearning Audit Ledger", "GET", "/api/v1/admin/ledger")

print("\nAudit Complete.")
