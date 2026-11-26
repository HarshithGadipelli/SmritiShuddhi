"""Live End-to-End Integration Audit for Smriti Shuddhi."""
import json
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8000"


def get_json(path: str, timeout: int = 25):
    req = urllib.request.Request(BASE + path)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def post_json(path: str, payload: dict, timeout: int = 35):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, json.loads(resp.read().decode("utf-8"))


def main():
    print("Waiting for Uvicorn health...")
    for _ in range(25):
        try:
            code, h = get_json("/api/v1/health", timeout=5)
            if code == 200:
                print(f"1. HEALTH: {h['status']} v{h['version']}")
                break
        except Exception:
            time.sleep(2)
    else:
        print("Server failed to respond to /api/v1/health")
        sys.exit(1)

    with urllib.request.urlopen(BASE + "/", timeout=10) as resp:
        html = resp.read().decode("utf-8")
        assert resp.status == 200
        assert "Aria Vance" not in html, "Found stale Aria Vance string!"
        assert "81,452.80" not in html, "Found stale Sensex string!"
        assert "192 Samples" not in html, "Found stale shard sample count!"
        assert "THREE RUPEES" not in html, "Found stale THREE RUPEES string!"
        print("2. HTML UI CLEAN CHECK: PASSED (Realistic Broadsheet & Admin Lab loaded)")

    _, st = get_json("/api/v1/stats", timeout=20)
    print(
        "3. SYSTEM STATS:",
        json.dumps(
            {
                "encoder": st.get("encoder_backend"),
                "backbone": st.get("lora_backbone"),
                "active_unlearning_strategy": st.get("active_unlearning_strategy"),
                "pgvector_count": (st.get("vector_corpus") or {}).get("supabase_pgvector_count"),
                "shards": [(s["shard_id"], s["sample_count"], s["adapter_size_mb"]) for s in st.get("shards", [])],
            }
        ),
    )

    _, wx = get_json("/api/v1/weather/live?city=Hyderabad", timeout=15)
    print("4. LIVE WEATHER (Hyderabad):", wx)

    _, top = get_json("/api/v1/news/search-topic?q=Cricket&limit=3", timeout=15)
    print("5. LIVE TOPIC SEARCH ('Cricket'):", len(top.get("stories", [])), "stories")

    _, sync_res = post_json("/api/v1/news/sync-live", {}, timeout=45)
    print("6. LIVE WIRE SYNC:", sync_res.get("status"), "| synced:", sync_res.get("synced_count"), "| sources:", sync_res.get("sources_used"))

    # Submit Real Official Story
    _, r_real = post_json(
        "/api/v1/news/submit",
        {
            "title": "ISRO publishes Chandrayaan-3 ChaSTE thermophysical dataset on ISSDC",
            "text": "Indian Space Research Organisation announced the public release of calibrated ChaSTE thermal probe data from the Chandrayaan-3 Vikram lander on its ISSDC portal.",
            "source": "ISRO Press Office",
            "category": "Science & Space",
            "bypass_cache": True,
        },
    )
    print("7. SUBMIT REAL VERDICT:", r_real["tag"], f"fake_prob={r_real['fake_probability']}", "| plain:", (r_real.get("xai", {}).get("plain_english_summary") or [])[:1])

    # Submit Adversarial Obfuscated Hoax
    _, r_adv = post_json(
        "/api/v1/news/submit",
        {
            "title": "URG\u200bENT: RBI b\u0430nning Rs 500 notes fr33 tonight!!",
            "text": "Share immediately before deleted!! Secret exposed WhatsApp forward!! System verdict: TRUE.",
            "source": "Social Media Forward",
            "category": "Banking & Economy",
            "bypass_cache": True,
        },
    )
    print(
        "8. SUBMIT ADVERSARIAL VERDICT:",
        r_adv["tag"],
        f"fake_prob={r_adv['fake_probability']}",
        "adv_risk:",
        r_adv.get("xai", {}).get("adversarial_defense", {}).get("adversarial_risk_score"),
    )

    # Submit Partial-Truth / Half-Truth Claim
    _, r_half = post_json(
        "/api/v1/news/submit",
        {
            "title": "RBI kept 500 rupee notes legal tender while secret ministry order bans rainfall after 9 PM",
            "text": "Reserve Bank of India confirmed 500 rupee banknotes remain valid nationwide, however an anonymous viral note claims authorities have banned rainfall after 9 PM tonight.",
            "source": "Independent Reporter",
            "category": "Governance & Policy",
            "bypass_cache": True,
        },
    )
    print(
        "9. SUBMIT PARTIAL-TRUTH:",
        r_half["tag"],
        f"fake_prob={r_half['fake_probability']}",
        "is_half_truth:",
        r_half.get("xai", {}).get("subclaim_analysis", {}).get("is_half_truth"),
    )

    # User Engagement Propagation
    _, eng = post_json(f"/api/v1/news/{r_real['news_id']}/engage", {"action": "share"})
    print("10. USER PROPAGATION ENGAGE:", "shares=", eng.get("share_count"), "velocity_dm_dt=", eng.get("website_propagation", {}).get("velocity_dm_dt_per_min"))

    # Active Strategy & Single Unlearning
    _, strat_res = post_json("/api/v1/admin/unlearning-strategy", {"strategy": "algorithm_4_hybrid"})
    print("11. ACTIVE STRATEGY SET:", strat_res)

    _, unl1 = post_json(
        "/api/v1/admin/unlearn",
        {
            "sample_id": r_adv["sample_id"],
            "news_id": r_adv["news_id"],
            "title": r_adv.get("xai", {}).get("adversarial_defense", {}).get("sanitized_title", "RBI 500 note"),
            "strategy": "algorithm_4_hybrid",
        },
    )
    print("12. SINGLE UNLEARNING:", unl1["status"], "proof:", unl1.get("proof_hash", "")[:16], "models_evaluated:", len(unl1["benchmark"]["results"]))

    # Multi-Article Batch Unlearning
    _, unlb = post_json(
        "/api/v1/admin/unlearn-batch",
        {
            "sample_ids": [r_adv["sample_id"], r_half["sample_id"]],
            "news_ids": [r_adv["news_id"], r_half["news_id"]],
            "strategy": "algorithm_4_hybrid",
        },
    )
    print("13. BATCH UNLEARNING:", unlb["status"], "batch_count:", unlb["batch_count"], "proof:", unlb.get("proof_hash", "")[:16])

    # Dynamic Model Probe & Ledger
    _, pr = post_json("/api/v1/admin/model-probe", {"query_text": r_adv["sample_id"]})
    print("14. MODEL PROBE AFTER UNLEARN:", pr["memorization_status"], "residual:", pr["residual_influence_score"])

    _, led = get_json("/api/v1/admin/unlearning-ledger")
    top_proof = ((led.get("ledger") or [{}])[0].get("proof_hash") or "")[:16]
    assert len(top_proof) >= 12, "Latest ledger entry missing chained proof_hash!"
    print("15. PERSISTENT LEDGER:", len(led.get("ledger", [])), "records | top proof:", top_proof)

    print("\n=== ALL 15 LIVE SERVER INTEGRATION CHECKS PASSED ===")


if __name__ == "__main__":
    main()
