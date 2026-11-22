import sys
import os
sys.path.insert(0, os.path.abspath("."))
from app.main import execute_hybrid_inference

print("Testing 5-Pillar Multi-Aspect Fake News Detection Suite...\n")

test_cases = [
    {
        "name": "Case 1: Authentic Institutional Wire (ISRO payload release)",
        "title": "ISRO Releases Scientific Data Archive from Chandrayaan Mission on ISSDC",
        "text": "Indian Space Research Organisation (ISRO) has officially opened the scientific payload repository on the Indian Space Science Data Centre for researchers globally.",
        "source": "ISRO Press Office",
        "author": "Dr. S. Nair",
        "expected_pred": "REAL"
    },
    {
        "name": "Case 2: Quantitative Anomaly (Crude Oil Collapse)",
        "title": "Brent crude plunges to 14 dollars per barrel following OPEC meeting",
        "text": "Energy markets in turmoil as Brent crude crashes to 14 dollars per barrel today.",
        "source": "Market Wire",
        "author": "Trader",
        "expected_pred": "FAKE"
    },
    {
        "name": "Case 3: Forex Dislocation Anomaly (USD/INR)",
        "title": "US Dollar plunges to 22 rupees in dramatic currency crash",
        "text": "Forex markets stunned as USD drops to 22 rupees overnight in unprecedented currency collapse.",
        "source": "Forex Flash",
        "author": "Anonymous",
        "expected_pred": "FAKE"
    },
    {
        "name": "Case 4: Chronological Timeline Contradiction (Lockdown Rumor)",
        "title": "Ministry of Home Affairs announces strict nationwide lockdown starting tomorrow",
        "text": "Emergency announcement: National lockdown will happen tomorrow across all states. Everything closed.",
        "source": "WhatsApp Forward",
        "author": "Anonymous",
        "expected_pred": "FAKE"
    },
    {
        "name": "Case 5: Viral Propagation + Banknote Demonetization Hoax",
        "title": "URGENT ALERT: RBI Invaliding All 500 Rupee Currency Notes Tonight",
        "text": "Urgent warning! Reserve Bank of India is withdrawing all 500 currency notes from circulation midnight. Secret exposed! Forward to all friends before deleted!",
        "source": "WhatsApp Viral Post",
        "author": "Viral Forwarder",
        "expected_pred": "FAKE"
    }
]

all_passed = True
for tc in test_cases:
    print(f"--- Running: {tc['name']} ---")
    verdict = execute_hybrid_inference(tc["title"], tc["text"], source=tc["source"], author=tc["author"])
    pred = verdict["prediction"]
    prob = verdict["fake_probability"]
    pillars = verdict.get("five_pillar_breakdown", {})

    print(f"Prediction: {pred} (Fake Prob: {prob*100:.1f}%) | Risk: {verdict['risk_band']}")
    print(f"  Pillar 1 (Content-based):     s_content     = {verdict.get('s_content')}")
    print(f"  Pillar 2 (Context-based):     s_context     = {verdict.get('s_context')}")
    print(f"  Pillar 3 (Knowledge-based):   s_knowledge   = {verdict.get('s_knowledge')}")
    print(f"  Pillar 4 (Propagation-based): s_propagation = {verdict.get('s_propagation')}")
    print(f"  Pillar 5 (Source-based):      s_source      = {verdict.get('s_source')}")
    print(f"Primary XAI Factors: {verdict['xai']['primary_verdict_factors'][:2]}")

    if pred != tc["expected_pred"]:
        print(f"FAILED: Expected {tc['expected_pred']}, got {pred}")
        all_passed = False
    else:
        print("PASSED")
    print()

if all_passed:
    print("ALL 5-PILLAR MULTI-ASPECT FAKE NEWS DETECTION TESTS PASSED PERFECTLY!")
else:
    sys.exit(1)
