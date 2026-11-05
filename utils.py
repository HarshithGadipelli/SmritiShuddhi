import hashlib
import re
from datetime import datetime, timezone

def utcnow():
    return datetime.now(timezone.utc)

def normalize_text(text: str) -> str:
    text = str(text or '')
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def stable_id(text: str, prefix: str = 'ID') -> str:
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:14]
    return f'{prefix}_{digest}'

def risk_band(fake_probability: float, low: float, high: float) -> str:
    if fake_probability >= high:
        return 'HIGH_RISK_FAKE'
    if fake_probability <= low:
        return 'LOW_RISK'
    return 'BORDERLINE'

def serialize_doc(doc):
    if not doc:
        return None
    out = dict(doc)
    if '_id' in out:
        out['_id'] = str(out['_id'])
    for k, v in list(out.items()):
        if hasattr(v, 'isoformat'):
            out[k] = v.isoformat()
    return out
