import sys, os
sys.path.insert(0, os.path.abspath('.'))
from app.main import execute_hybrid_inference

res = execute_hybrid_inference(
    'ISRO Announces Successful Testing of Semi-Cryogenic Pre-Burner Ignition at Mahendragiri',
    'Indian Space Research Organisation (ISRO) successfully completed the semi-cryogenic engine pre-burner ignition test at the IPRC test facility.',
    source='ISRO Press Office'
)
print(f"Prediction: {res['prediction']} | Fake Prob: {res['fake_probability']*100:.1f}% | Risk: {res['risk_band']}")
print(f"XAI: {res['xai']['primary_verdict_factors']}")
