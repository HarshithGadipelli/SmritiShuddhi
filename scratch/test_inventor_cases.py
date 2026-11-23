import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app.main import execute_hybrid_inference

cases = [
    ("an inventor invented an invention yesterday", "an inventor invented an invention yesterday in laboratory."),
    ("an inventor invented an invention in india", "an inventor invented an invention in india for rural technology."),
    ("a person invented an invention", "a person invented an invention."),
    ("URGENT: Indian inventor invented free fuel device yesterday government hiding it", "Breaking shocking news: An inventor invented miracle free fuel in India yesterday. Oil companies panicking! Forward to all before deleted!"),
    ("ISRO Announces Successful Testing of Semi-Cryogenic Pre-Burner Ignition at Mahendragiri", "Indian Space Research Organisation (ISRO) successfully completed the semi-cryogenic engine pre-burner ignition test at the IPRC test facility.")
]

for title, text in cases:
    res = execute_hybrid_inference(title, text)
    print(f"Title: {title}")
    print(f"  Prediction: {res['prediction']} | Fake Prob: {res['fake_probability']*100:.1f}% | Risk: {res['risk_band']}")
    print(f"  s_content: {res.get('s_content')} | s_context: {res.get('s_context')} | s_knowledge: {res.get('s_knowledge')} | s_propagation: {res.get('s_propagation')} | s_source: {res.get('s_source')}")
    print(f"  Primary XAI Factors:")
    for f in res['xai']['primary_verdict_factors']:
        print(f"    - {f}")
    print("-" * 65)
