import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from app.main import app

def main():
    client = TestClient(app)

    print("1. Testing GET /api/v1/news...")
    res_news = client.get("/api/v1/news")
    assert res_news.status_code == 200, f"Error {res_news.status_code}: {res_news.text}"
    news_items = res_news.json().get("news", [])
    print(f"   Success: {len(news_items)} published articles on news wire.")

    print("\n2. Testing POST /api/v1/news/submit (Authentic Verified News)...")
    res_real = client.post("/api/v1/news/submit", json={
        "title": "ISRO Releases Scientific Data Archive on ISSDC",
        "text": "Indian Space Research Organisation has officially released data from Chandrayaan missions.",
        "category": "Science & Space",
        "source": "ISRO Official Press",
        "author": "Dr. S. Nair"
    })
    assert res_real.status_code == 200, f"Error {res_real.status_code}: {res_real.text}"
    r_data = res_real.json()
    print(f"   Status: {r_data['status']} | Risk: {r_data['risk_band']} | Latency: {r_data['processing_latency_ms']}ms")
    print(f"   Action: {r_data['message']}")

    print("\n3. Testing POST /api/v1/news/submit (High-Risk Viral Fake News)...")
    res_fake = client.post("/api/v1/news/submit", json={
        "title": "Free 5000 Rs Laptop Scheme Under Prime Minister Scheme is Fake",
        "text": "Viral message claiming government is giving 5000 rupees and laptops to all students under PM Free Laptop Yojana. Apply now immediately before link expires!",
        "category": "Governance",
        "source": "WhatsApp Group Forward",
        "author": "Anonymous Viral"
    })
    assert res_fake.status_code == 200, f"Error {res_fake.status_code}: {res_fake.text}"
    f_data = res_fake.json()
    print(f"   Status: {f_data['status']} | Risk: {f_data['risk_band']} | Fake Score: {f_data['fake_probability']*100:.1f}%")
    print(f"   Action: {f_data['message']}")

    print("\n4. Testing GET /api/v1/admin/queue...")
    res_queue = client.get("/api/v1/admin/queue")
    assert res_queue.status_code == 200
    q_data = res_queue.json()
    print(f"   Pending Review: {len(q_data['pending_review'])} | Blocked Fake News: {len(q_data['blocked_fake_news'])}")

    print("\n5. Testing POST /api/v1/admin/unlearn (All 4 Structural Families Benchmark)...")
    res_unl = client.post("/api/v1/admin/unlearn", json={
        "sample_id": "SYN_R_00445",
        "title": "VIRAL ALERT: RBI Invaliding All 500 Rupee Currency Notes Tonight",
        "strategy": "all_benchmark"
    })
    assert res_unl.status_code == 200, f"Error {res_unl.status_code}: {res_unl.text}"
    u_data = res_unl.json()
    print(f"   Unlearning Status: {u_data['status']}")
    print("   === BENCHMARK COMPARATIVE RESULTS ===")
    for r in u_data["benchmark"]["results"]:
        name = r["algorithm_name"]
        t_ms = r["execution_time_ms"]
        speed = r["speedup_vs_retrain"]
        ret = r["retain_accuracy_after"] * 100
        inf = r["forget_influence_remaining_pct"]
        param = r["parameters_modified_pct"]
        print(f"   * {name}")
        print(f"     Time: {t_ms}ms ({speed}) | Retain Accuracy: {ret:.1f}% | Residual Influence: {inf}% | Weights Modified: {param}%")

    print("\nALL INTEGRATION TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    main()
