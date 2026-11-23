import sys
sys.path.insert(0, ".")
from app.main import execute_hybrid_inference

print("Testing Multimodal & Epistemic Calibration...")
r = execute_hybrid_inference(
    title="ISRO Launches Advanced Meteorological Satellite from Sriharikota",
    text="Indian Space Research Organisation successfully injected the meteorological satellite into geostationary transfer orbit.",
    source="Times of India",
    author="Staff Correspondent",
    category="Science & Space",
    image_url="https://images.isro.gov.in/launch_satellite_space.jpg"
)

print("Prediction:", r["prediction"], "| Risk:", r["risk_band"], "| P(Fake):", r["fake_probability"])
print("Epistemic Calibration:", r.get("epistemic_calibration"))
print("Multimodal Forensics:", r.get("multimodal_forensics"))
