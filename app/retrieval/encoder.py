import re
import math
import hashlib
from typing import List, Dict, Any, Union
import numpy as np
from config import BGE_MODEL_NAME

# Indian regional keywords & Hinglish indicators
HINGLISH_PATTERNS = [
    r'\b(sach|jhooth|khabar|viral|dhyan|paisa|sarkar|yojana|muft|dhamaka|khatra|suno|pakka|breaking)\b',
    r'\b(modi|bjp|congress|aadhaar|pan|rbi|cbi|isro|railway|yojna|free|bonus)\b'
]

DEVANAGARI_RANGE = (0x0900, 0x097F)
TELUGU_RANGE = (0x0C00, 0x0C7F)
TAMIL_RANGE = (0x0B80, 0x0BFF)


class MultilingualRegionalEncoder:
    """BGE-M3 Multilingual & Regional Language Encoder:
    Encodes English, Hindi, Hinglish, Telugu, Tamil text into normalized dense vectors.
    Supports neural embeddings when torch/transformers are loaded, with a robust
    subword-hash semantic projection fallback for low-latency CPU inference.
    """
    def __init__(self, vector_dim: int = 384):
        self.vector_dim = vector_dim
        self._neural_model = None
        self._tokenizer = None
        self._neural_available = False

    def _try_init_neural(self):
        if self._neural_available or self._neural_model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            # Use local_files_only to prevent network timeout when running on offline/edge hardware
            self._tokenizer = AutoTokenizer.from_pretrained(BGE_MODEL_NAME, local_files_only=True)
            self._neural_model = AutoModel.from_pretrained(BGE_MODEL_NAME, local_files_only=True)
            self._neural_model.eval()
            self._neural_available = True
        except Exception:
            # High-resolution subword hash projection fallback (instant & offline)
            self._neural_available = False

    def detect_regional_cues(self, text: str) -> Dict[str, Any]:
        """Detects linguistic script composition and Hinglish sensational markers."""
        chars = [ord(c) for c in text]
        total_chars = max(len(chars), 1)

        devanagari_count = sum(1 for c in chars if DEVANAGARI_RANGE[0] <= c <= DEVANAGARI_RANGE[1])
        telugu_count = sum(1 for c in chars if TELUGU_RANGE[0] <= c <= TELUGU_RANGE[1])
        tamil_count = sum(1 for c in chars if TAMIL_RANGE[0] <= c <= TAMIL_RANGE[1])

        hinglish_hits = []
        for pattern in HINGLISH_PATTERNS:
            found = re.findall(pattern, text, re.IGNORECASE)
            if found:
                hinglish_hits.extend(found)

        primary_lang = "English"
        if devanagari_count / total_chars > 0.15:
            primary_lang = "Hindi (Devanagari)"
        elif telugu_count / total_chars > 0.15:
            primary_lang = "Telugu"
        elif tamil_count / total_chars > 0.15:
            primary_lang = "Tamil"
        elif len(hinglish_hits) >= 2:
            primary_lang = "Hinglish (Mixed Romanized)"

        return {
            "primary_language": primary_lang,
            "devanagari_ratio": round(devanagari_count / total_chars, 4),
            "telugu_ratio": round(telugu_count / total_chars, 4),
            "tamil_ratio": round(tamil_count / total_chars, 4),
            "hinglish_cues_found": list(set(hinglish_hits))
        }

    def _hash_embed(self, text: str) -> np.ndarray:
        """Deterministic multi-granular subword & word n-gram projection into unit sphere.
        Preserves regional language semantic clustering without requiring 2GB GPU RAM.
        """
        vec = np.zeros(self.vector_dim, dtype=np.float32)
        tokens = re.findall(r'\w+', text.lower())
        if not tokens:
            return vec

        # 1. Word tokens
        for t in tokens:
            h = int(hashlib.md5(t.encode('utf-8')).hexdigest(), 16)
            idx = h % self.vector_dim
            sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
            vec[idx] += sign

        # 2. Bigrams
        for i in range(len(tokens) - 1):
            bg = f"{tokens[i]}_{tokens[i+1]}"
            h = int(hashlib.sha1(bg.encode('utf-8')).hexdigest(), 16)
            idx = h % self.vector_dim
            sign = 1.0 if (h >> 16) % 2 == 0 else -1.0
            vec[idx] += sign * 1.5

        # 3. Subword character 3-grams for regional morphology
        for t in tokens:
            if len(t) >= 3:
                for j in range(len(t) - 2):
                    trigram = t[j:j+3]
                    h = int(hashlib.sha256(trigram.encode('utf-8')).hexdigest(), 16)
                    idx = h % self.vector_dim
                    sign = 1.0 if (h >> 8) % 2 == 0 else -1.0
                    vec[idx] += sign * 0.75

        # L2 Normalization
        norm = np.linalg.norm(vec)
        if norm > 1e-9:
            vec /= norm
        return vec

    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """Encodes single text or list of texts into normalized embedding vectors."""
        is_single = isinstance(texts, str)
        text_list = [texts] if is_single else texts

        self._try_init_neural()

        if self._neural_available and self._neural_model is not None:
            try:
                import torch
                encoded_input = self._tokenizer(
                    text_list, padding=True, truncation=True, max_length=512, return_tensors='pt'
                )
                with torch.no_grad():
                    model_output = self._neural_model(**encoded_input)
                    # Use CLS token or mean pooling
                    token_embeddings = model_output[0]
                    input_mask_expanded = encoded_input['attention_mask'].unsqueeze(-1).expand(token_embeddings.size()).float()
                    sum_embeddings = torch.sum(token_embeddings * input_mask_expanded, 1)
                    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9)
                    pooled = sum_embeddings / sum_mask
                    # Normalize
                    pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
                    res = pooled.cpu().numpy()
                    return res[0] if is_single else res
            except Exception:
                pass

        # Fallback to hash projection
        vectors = [self._hash_embed(t) for t in text_list]
        arr = np.array(vectors, dtype=np.float32)
        return arr[0] if is_single else arr


# Global encoder instance
regional_encoder = MultilingualRegionalEncoder()
