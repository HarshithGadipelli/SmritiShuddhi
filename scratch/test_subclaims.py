import sys
sys.path.insert(0, ".")
from app.main import execute_hybrid_inference

print("--- TEST 1: HALF-TRUTH / PARTIAL TRUTH ---")
r_half = execute_hybrid_inference(
    title="ISRO Releases Chandrayaan Data Archive but Leak Triggers Emergency",
    text="ISRO releases scientific payload data from Chandrayaan on the ISSDC portal, but toxic radiation leak threatens southern states causing midnight emergency panic.",
    source="Independent Online Post"
)
print("Half-Truth Verdict:", r_half["prediction"], "| Risk:", r_half["risk_band"], "| Fake Prob:", r_half["fake_probability"])
print("Sub-claim summary:", r_half.get("subclaim_analysis", {}).get("summary"))
print("Verified Clauses:", r_half.get("subclaim_analysis", {}).get("verified_clauses"))
print("Unverified/Contradicted Clauses:", r_half.get("subclaim_analysis", {}).get("unverified_clauses") or r_half.get("subclaim_analysis", {}).get("contradicted_clauses"))

print("\n--- TEST 2: INVENTOR ABSTRACT EXAMPLES ---")
headlines = [
    "an inventor invented an invention yesterday",
    "an inventor invented an invention in india",
    "a person invented an invention",
    "an inventor invented a car that runs on water without fuel and oil companies are hiding it"
]
for h in headlines:
    res = execute_hybrid_inference(title=h, text=h)
    print(f"Headline: '{h}'")
    print(f"  -> Prediction: {res['prediction']} | Risk: {res['risk_band']} | P(Fake): {res['fake_probability']}")
    print(f"  -> ZK Disposition: {res.get('zero_knowledge_analysis', {}).get('disposition')}")
    print(f"  -> Factors: {res['xai']['primary_verdict_factors'][:2]}")
