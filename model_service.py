from pathlib import Path
import joblib
import numpy as np
from config import SISA_DIR, SISA_SHARDS, FAKE_THRESHOLD_HIGH, FAKE_THRESHOLD_LOW
from utils import normalize_text, risk_band
from unlearning.sisa import load_active_ensemble

class Predictor:
    def __init__(self):
        self.reload()

    def reload(self):
        self.ensemble = None
        try:
            self.ensemble = load_active_ensemble(SISA_DIR)
        except Exception:
            self.ensemble = None

    def predict(self, title: str, text: str):
        combined = f'{normalize_text(title)} {normalize_text(text)}'.strip()
        if not combined:
            raise ValueError('News text is empty.')
        if self.ensemble is None:
            return {
                'fake_probability': 0.5,
                'real_probability': 0.5,
                'risk_band': 'MODEL_NOT_TRAINED',
                'prediction': 'UNKNOWN',
                'model_version': 'none'
            }
        fake_prob = float(self.ensemble.predict_fake_probability([combined])[0])
        real_prob = 1.0 - fake_prob
        band = risk_band(fake_prob, FAKE_THRESHOLD_LOW, FAKE_THRESHOLD_HIGH)
        prediction = 'FAKE' if fake_prob >= 0.5 else 'REAL'
        return {
            'fake_probability': round(fake_prob, 6),
            'real_probability': round(real_prob, 6),
            'risk_band': band,
            'prediction': prediction,
            'model_version': self.ensemble.version_id
        }
