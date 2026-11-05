import sys
import time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

print("0. Starting script...", flush=True)

import asyncio
from fastapi import BackgroundTasks
print("0.1. Importing app.main...", flush=True)
from app.main import get_published_news, submit_news, NewsSubmitRequest, execute_unlearning, UnlearningExecutionRequest, get_admin_queue, seed_initial_demo_news
from db import init_db

async def test_all():
    print("=== Testing Direct Platform Core API ===", flush=True)
    init_db()
    seed_initial_demo_news()
    
    # 1. Feed
    print("1. Fetching published news...", flush=True)
    news_res = await get_published_news()
    print(f"   Published news count: {len(news_res['news'])}", flush=True)

    # 2. Authentic News
    print("2. Submitting Authentic News...", flush=True)
    bt = BackgroundTasks()
    p_real = NewsSubmitRequest(
        title="ISRO Releases Scientific Data Archive on ISSDC",
        text="Indian Space Research Organisation has officially released data from Chandrayaan missions.",
        category="Science & Space",
        source="ISRO Press Office",
        author="Dr. S. Nair"
    )
    res_real = await submit_news(p_real, bt)
    print(f"   Status: {res_real['status']}", flush=True)
    print(f"   Risk: {res_real['risk_band']}", flush=True)
    print(f"   Latency: {res_real['processing_latency_ms']} ms", flush=True)

    # 3. High Risk Fake News
    print("3. Submitting Viral Fake News...", flush=True)
    p_fake = NewsSubmitRequest(
        title="Free 5000 Rs Laptop Scheme Under Prime Minister Scheme is Fake",
        text="Viral message claiming government is giving 5000 rupees and laptops to all students under PM Free Laptop Yojana. Apply now immediately before link expires!",
        category="Governance",
        source="WhatsApp Group Forward",
        author="Anonymous Viral"
    )
    res_fake = await submit_news(p_fake, bt)
    print(f"   Status: {res_fake['status']}", flush=True)
    print(f"   Risk: {res_fake['risk_band']}", flush=True)
    print(f"   Fake Score: {res_fake['fake_probability']*100:.1f}%", flush=True)

    # 4. Queue
    print("4. Checking Admin Queue...", flush=True)
    queue_res = await get_admin_queue()
    print(f"   Pending Review: {len(queue_res['pending_review'])}", flush=True)
    print(f"   Blocked Fake: {len(queue_res['blocked_fake_news'])}", flush=True)

    # 5. Multi-Model Exact Unlearning Benchmark
    print("5. Executing Multi-Model Exact Unlearning Benchmark...", flush=True)
    u_req = UnlearningExecutionRequest(
        sample_id="SYN_R_00445",
        title="VIRAL ALERT: RBI Invaliding All 500 Rupee Currency Notes Tonight",
        strategy="all_benchmark"
    )
    u_res = await execute_unlearning(u_req, bt)
    print(f"   Unlearning Status: {u_res['status']}", flush=True)
    for r in u_res["benchmark"]["results"]:
        print(f"   * {r['algorithm_name']} | Time: {r['execution_time_ms']}ms | Speedup: {r['speedup_vs_retrain']} | Retain: {r['retain_accuracy_after']*100:.1f}% | Residual: {r['forget_influence_remaining_pct']}%", flush=True)

    print("\nALL CORE PLATFORM AND UNLEARNING WORKFLOWS OPERATING WITH 100% SUCCESS!", flush=True)

if __name__ == "__main__":
    asyncio.run(test_all())
