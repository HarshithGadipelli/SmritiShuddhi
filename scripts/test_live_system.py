import urllib.request
import json
import sys

def run_tests():
    base = "http://127.0.0.1:8000"
    print("=== SMRITI SHUDDHI FULL PLATFORM TEST ===")
    
    # 1. Health
    r = urllib.request.urlopen(f"{base}/api/v1/health")
    health = json.loads(r.read())
    print(f"1. Health: {health['status']}")
    
    # 2. Benchmark All
    r = urllib.request.urlopen(f"{base}/api/v1/unlearning/benchmark/all")
    bench = json.loads(r.read())
    print(f"2. Benchmark All: Recommended = {bench.get('recommended_algorithm')}")
    print(f"   Summary: {bench.get('recommendation_summary')}")
    for res in bench.get("results", []):
        print(f"   - {res['algorithm_name']}: Latency={res['execution_time_ms']}ms, Acc={res.get('retain_accuracy_after')}, Prec={res.get('precision_after')}, Rec={res.get('recall_after')}, F1={res.get('f1_after')}")
    
    # 3. News Feed
    r = urllib.request.urlopen(f"{base}/api/v1/news")
    news = json.loads(r.read())
    news_items = news.get("news", [])
    print(f"3. Live News Feed: {len(news_items)} stories fetched.")
    sources = set(n.get("source") for n in news_items)
    langs = set(n.get("language") for n in news_items)
    print(f"   Sources: {sources}")
    print(f"   Languages: {langs}")
    
    # 4. Auth Register
    import time
    test_email = f"priya_{int(time.time())}@smritishuddhi.org"
    req = urllib.request.Request(
        f"{base}/api/v1/auth/register",
        data=json.dumps({"email": test_email, "password": "pass", "name": "Priya Nair", "role": "JOURNALIST"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    reg_data = json.loads(r.read())
    print(f"4. Register User: Success={reg_data['success']}, Name={reg_data['user']['name']}, Role={reg_data['user']['role']}")
    
    # 5. Auth Login
    req = urllib.request.Request(
        f"{base}/api/v1/auth/login",
        data=json.dumps({"email": test_email, "password": "pass"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    login_data = json.loads(r.read())
    print(f"5. Login User: Success={login_data['success']}, Role={login_data['user']['role']}")
    
    # 6. Submit News (User Scan)
    req = urllib.request.Request(
        f"{base}/api/v1/news/submit",
        data=json.dumps({
            "title": "PIB ALERT: Viral WhatsApp Message on New Bank Charge is False",
            "text": "A viral audio claim stating that all digital banking transactions will attract a flat fee of 50 rupees from next month is fake. PIB Fact Check confirms zero such proposal exists.",
            "author": "Priya Nair",
            "category": "Banking & Economy"
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    sub_data = json.loads(r.read())
    print(f"6. User Submission: Status={sub_data['status']}, Risk={sub_data['risk_band']}, RealProb={sub_data['real_probability']}")
    
    # 7. Admin Queue Check
    r = urllib.request.urlopen(f"{base}/api/v1/admin/queue")
    queue_data = json.loads(r.read())
    print(f"7. Admin Queue: Blocked Fake={len(queue_data.get('blocked_fake_news', []))}, Pending={len(queue_data.get('pending_review', []))}, Published={len(queue_data.get('recent_verified_news', []))}")
    
    # 8. Admin Exact Machine Unlearning with Recommended Model (Algorithm 2: Decremental Closed-Form SVM)
    req = urllib.request.Request(
        f"{base}/api/v1/admin/unlearn",
        data=json.dumps({
            "sample_id": "SYN_R_00445",
            "strategy": "algorithm_2_svm",
            "title": "VIRAL ALERT: RBI Invaliding All 500 Rupee Currency Notes Tonight",
            "text": "Urgent WhatsApp warning: Reserve Bank of India is withdrawing all 500 currency notes from circulation midnight."
        }).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    unlearn_data = json.loads(r.read())
    print(f"8. Machine Unlearning Executed: Status={unlearn_data['status']}, Strategy={unlearn_data['strategy']}")
    
    # 9. Audit & Ledger
    r = urllib.request.urlopen(f"{base}/api/v1/admin/unlearning-ledger")
    ledger_data = json.loads(r.read())
    print(f"9. Audit Ledger: {len(ledger_data.get('ledger', []))} historical exact unlearning entries logged.")
    print("=== ALL SYSTEM LIFECYCLE TESTS COMPLETED SUCCESSFULLY ===")

if __name__ == "__main__":
    run_tests()
