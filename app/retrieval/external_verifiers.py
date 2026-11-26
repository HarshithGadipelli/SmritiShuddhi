import json
import math
import re
import ssl
import time
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import config
from app.retrieval.encoder import regional_encoder

logger = logging.getLogger("ExternalVerifiers")


def _get_ssl_context() -> ssl.SSLContext:
    """Returns verified SSL context using certifi CA bundle when available."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()

# Simple in-memory TTL cache to avoid repeated network round-trips for identical claims
_TTL_CACHE: Dict[str, Tuple[float, Any]] = {}


def _cache_get(key: str, max_age_sec: int = 300) -> Optional[Any]:
    item = _TTL_CACHE.get(key)
    if not item:
        return None
    ts, val = item
    if (time.time() - ts) <= max_age_sec:
        return val
    _TTL_CACHE.pop(key, None)
    return None


def _cache_set(key: str, val: Any):
    if len(_TTL_CACHE) > 256:
        oldest_key = next(iter(_TTL_CACHE))
        _TTL_CACHE.pop(oldest_key, None)
    _TTL_CACHE[key] = (time.time(), val)


# =============================================================================
# 1. ADVERSARIAL ML DEFENSE & HOMOGLYPH / OBFUSCATION SANITIZER
# =============================================================================

HOMOGLYPH_MAP = str.maketrans({
    "\u0430": "a", "\u0410": "A",  # Cyrillic а, А
    "\u0435": "e", "\u0415": "E",  # Cyrillic е, Е
    "\u043e": "o", "\u041e": "O",  # Cyrillic о, О
    "\u0440": "p", "\u0420": "P",  # Cyrillic р, Р
    "\u0441": "c", "\u0421": "C",  # Cyrillic с, С
    "\u0443": "y", "\u0423": "Y",  # Cyrillic у, У
    "\u0445": "x", "\u0425": "X",  # Cyrillic х, Х
    "\u0456": "i", "\u0406": "I",  # Cyrillic і, І
    "\u03bf": "o", "\u03b1": "a", "\u03b5": "e",  # Greek
})

ZERO_WIDTH_RE = re.compile(r"[\u200b\u200c\u200d\u200e\u200f\u202a-\u202e\u2060\ufeff]")
LEET_WORD_RE = re.compile(r"\b[a-zA-Z]*[01345@$!]+[a-zA-Z]+\b|\b[a-zA-Z]+[01345@$!]+[a-zA-Z]*\b")
PROMPT_INJECT_RE = re.compile(
    r"(ignore previous|system verdict\s*:\s*true|override fact check|mark as verified|bypass classifier)",
    re.IGNORECASE,
)


class AdversarialDefenseAnalyzer:
    """Detects and sanitizes adversarial text perturbations meant to evade NLP classifiers:
    - Zero-width / BiDi invisible characters
    - Mixed-script Cyrillic/Greek homoglyphs embedded in Latin words
    - Alphanumeric leetspeak evasion (e.g., fr33, b@n, sh0cking)
    - Prompt-injection verdict spoofing phrases
    """

    def analyze_and_sanitize(self, title: str, text: str) -> Dict[str, Any]:
        raw = f"{title or ''} {text or ''}"
        zero_width_hits = len(ZERO_WIDTH_RE.findall(raw))
        cleaned_title = ZERO_WIDTH_RE.sub("", title or "")
        cleaned_text = ZERO_WIDTH_RE.sub("", text or "")

        homoglyph_hits = 0
        for ch in cleaned_title + cleaned_text:
            if ch in HOMOGLYPH_MAP:
                homoglyph_hits += 1

        norm_title = cleaned_title.translate(HOMOGLYPH_MAP)
        norm_text = cleaned_text.translate(HOMOGLYPH_MAP)

        leet_matches = LEET_WORD_RE.findall(f"{norm_title} {norm_text}")
        # Filter out legitimate model numbers / common units like 5G, COVID19, G20, Rs500
        sus_leet = [
            w for w in leet_matches
            if not re.match(r"^(5g|4g|6g|g20|g7|pm25|covid19|nh\d+|sh\d+|rs\d+)$", w, re.IGNORECASE)
        ]

        inject_matches = PROMPT_INJECT_RE.findall(f"{norm_title} {norm_text}")

        risk = 0.0
        vectors = []
        if zero_width_hits > 0:
            risk += min(0.45, zero_width_hits * 0.08)
            vectors.append(f"Zero-width / BiDi invisible character obfuscation ({zero_width_hits} chars)")
        if homoglyph_hits > 0:
            risk += min(0.55, homoglyph_hits * 0.12)
            vectors.append(f"Mixed-script homoglyph substitution ({homoglyph_hits} spoofed glyphs)")
        if sus_leet:
            risk += min(0.35, len(sus_leet) * 0.12)
            vectors.append(f"Leetspeak token obfuscation ({', '.join(sus_leet[:3])})")
        if inject_matches:
            risk += 0.65
            vectors.append("Adversarial verdict-override / prompt injection attempt")

        risk = round(min(1.0, risk), 4)
        return {
            "sanitized_title": norm_title.strip(),
            "sanitized_text": norm_text.strip(),
            "adversarial_risk_score": risk,
            "is_adversarial_attack": risk >= 0.30,
            "attack_vectors_detected": vectors,
            "zero_width_chars_stripped": zero_width_hits,
            "homoglyphs_neutralized": homoglyph_hits,
            "leetspeak_tokens": sus_leet[:5],
            "defense_status": "PERTURBATION_NEUTRALIZED" if vectors else "CLEAN_INPUT",
        }


# =============================================================================
# 2. STRUCTURED NER, SPO CLAIM TRIPLES, QUOTE LINEAGE & WIKIDATA GROUNDING
# =============================================================================

ORG_LEXICON = {
    "RBI", "ISRO", "PIB", "SEBI", "NPCI", "UIDAI", "ECI", "IMD", "AIIMS", "ICMR",
    "WHO", "UNICEF", "UNESCO", "NASA", "BBC", "REUTERS", "PTI", "ANI",
    "Reserve Bank of India", "Election Commission of India", "Supreme Court",
    "High Court", "Ministry of Finance", "Ministry of Home Affairs", "Ministry of Health",
    "Ministry of Railways", "NITI Aayog", "DRDO", "BCCI", "TRAI", "IRCTC", "SBI",
}

GPE_LEXICON = {
    "India", "New Delhi", "Delhi", "Mumbai", "Hyderabad", "Bengaluru", "Bangalore",
    "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Patna",
    "Telangana", "Andhra Pradesh", "Maharashtra", "Karnataka", "Tamil Nadu",
    "Uttar Pradesh", "Gujarat", "Rajasthan", "Kashmir", "Ladakh", "Kochi",
    "Assam", "Bihar", "Odisha", "London", "Washington", "Beijing", "USA", "China",
}

UNVERIFIED_QUOTE_MARKERS = [
    "senior insider", "secret source", "unnamed official", "sources close to",
    "leaked memo", "whatsapp message", "forwarded message", "viral post",
    "anonymous insider", "reliable secret", "hospital insider",
]


class StructuredNERAndSPOEngine:
    """Extracts typed Named Entities (PERSON, ORG, GPE, DATE, QUANTITY),
    Subject-Predicate-Object claim triples, Quote Lineage, and live Wikidata IDs.
    """

    def extract_entities(self, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title}. {text}".strip()
        entities: Dict[str, List[str]] = {
            "ORG": [],
            "GPE": [],
            "PERSON": [],
            "DATE_TIME": [],
            "QUANTITY": [],
        }

        for org in ORG_LEXICON:
            if re.search(r"\b" + re.escape(org) + r"\b", combined, re.IGNORECASE):
                entities["ORG"].append(org)

        for loc in GPE_LEXICON:
            if re.search(r"\b" + re.escape(loc) + r"\b", combined, re.IGNORECASE):
                entities["GPE"].append(loc)

        # Person pattern: Title + Proper Name or Two-word Capitalized Names not in GPE/ORG
        person_pats = re.findall(
            r"\b(?:PM|President|CM|Justice|Dr\.|Mr\.|Ms\.|Minister|Governor|Chief)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            combined,
        )
        known_lower = {x.lower() for x in (entities["ORG"] + entities["GPE"])}
        for p in person_pats:
            if p.lower() not in known_lower:
                entities["PERSON"].append(p)

        # Two-word capitalized Proper Nouns as candidate PERSON/ORG
        for cand in re.findall(r"\b([A-Z][a-z]{2,}\s+[A-Z][a-z]{2,})\b", combined):
            if cand.lower() not in known_lower and not cand.startswith(("The ", "This ", "In ", "On ", "Fact ")):
                if cand not in entities["PERSON"] and cand not in entities["ORG"]:
                    entities["PERSON"].append(cand)

        dates = re.findall(
            r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|20[1-3]\d|today|tonight|tomorrow)\b",
            combined,
            re.IGNORECASE,
        )
        entities["DATE_TIME"] = sorted(list(set(dates)))[:8]

        quants = re.findall(
            r"(?:₹|Rs\.?\s*|INR\s*|\$)\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:crore|lakh|billion|million))?|\b\d+(?:\.\d+)?\s*(?:%|°C|C|degrees|crore|lakh)\b",
            combined,
            re.IGNORECASE,
        )
        entities["QUANTITY"] = sorted(list(set(q.strip() for q in quants)))[:8]

        for k in entities:
            entities[k] = list(dict.fromkeys(entities[k]))[:8]

        return entities

    def extract_spo_triples(self, title: str, text: str, entities: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """Extracts concise Subject-Predicate-Object claim triples from title & lead sentence."""
        lead = title.strip() or (text.split(".")[0] if text else "")
        triples: List[Dict[str, str]] = []
        subj_candidates = entities.get("ORG", []) + entities.get("PERSON", []) + entities.get("GPE", [])
        pred_pat = re.search(
            r"\b(announced|banned|banning|withdrew|withdrawing|launched|confirmed|claimed|ordered|reduced|increased|hiked|cancelled|arrested|landed|issued|mandated|denies|debunks)\b",
            lead,
            re.IGNORECASE,
        )
        if pred_pat:
            verb = pred_pat.group(1)
            parts = re.split(r"\b" + re.escape(verb) + r"\b", lead, maxsplit=1, flags=re.IGNORECASE)
            subj = parts[0].strip(" ,:-") or (subj_candidates[0] if subj_candidates else "Unattributed Actor")
            obj = parts[1].strip(" .,:-") if len(parts) > 1 else ""
            triples.append({
                "subject": subj[:80],
                "predicate": verb.lower(),
                "object": obj[:120],
            })
        elif subj_candidates:
            triples.append({
                "subject": subj_candidates[0],
                "predicate": "asserted_claim",
                "object": lead[:120],
            })
        return triples

    def audit_quotes_and_lineage(self, text: str, source: str, entities: Dict[str, List[str]]) -> Dict[str, Any]:
        quotes = re.findall(r'"([^"]{12,180})"|\u201c([^\u201d]{12,180})\u201d', text or "")
        quote_texts = [q[0] or q[1] for q in quotes]
        low = (text or "").lower()
        unverified_markers = [m for m in UNVERIFIED_QUOTE_MARKERS if m in low]

        has_named_attribution = bool(entities.get("ORG") or entities.get("PERSON")) or any(
            k in low for k in ("press release", "notification", "circular", "spokesperson", "according to ")
        )
        unverified_quote_flag = (len(quote_texts) > 0 and not has_named_attribution) or len(unverified_markers) > 0

        lineage_status = "ATTRIBUTED_LINEAGE"
        if unverified_quote_flag:
            lineage_status = "UNVERIFIED_OR_PHANTOM_QUOTE"
        elif not source or source.lower() in ("user submission", "unknown", "social", "whatsapp", "viral"):
            lineage_status = "UNKNOWN_PUBLISHER_LINEAGE"

        return {
            "quote_count": len(quote_texts),
            "sample_quotes": quote_texts[:2],
            "unverified_quote_flag": unverified_quote_flag,
            "phantom_attribution_cues": unverified_markers,
            "source_lineage_status": lineage_status,
        }

    def query_wikidata_entities(self, entities: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """Lightweight live Wikidata entity check for primary subjects/organizations."""
        candidates = (entities.get("ORG", []) + entities.get("PERSON", []))[:2]
        if not candidates:
            return []
        verified = []
        for term in candidates:
            cache_k = f"wd:{term.lower()}"
            cached = _cache_get(cache_k, max_age_sec=3600)
            if cached is not None:
                if cached:
                    verified.append(cached)
                continue
            try:
                q = urllib.parse.quote(term)
                url = f"https://www.wikidata.org/w/api.php?action=wbsearchentities&search={q}&language=en&format=json&limit=1"
                req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-NER/2.0"})
                with urllib.request.urlopen(req, timeout=4.0, context=_get_ssl_context()) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                hits = data.get("search") or []
                if hits:
                    rec = {
                        "query": term,
                        "wikidata_id": hits[0].get("id", ""),
                        "label": hits[0].get("label", term),
                        "description": hits[0].get("description", "")[:100],
                    }
                    _cache_set(cache_k, rec)
                    verified.append(rec)
                else:
                    _cache_set(cache_k, {})
            except Exception:
                break
        return verified


# =============================================================================
# 3. TWO-LAYER LIVE FACT-CHECK CLIENT (GOOGLE API + FREE RSS FALLBACK)
# =============================================================================

class LiveFactCheckClient:
    """Queries Google Fact Check Tools API using a distilled claim query, with
    free Google News Fact-Check RSS fallback for Indian/global claims.
    """

    def check_claim(self, title: str, text: str, spo_triples: List[Dict[str, str]]) -> Dict[str, Any]:
        query = (title or "").strip()
        if not query and spo_triples:
            t0 = spo_triples[0]
            query = f"{t0['subject']} {t0['predicate']} {t0['object']}".strip()
        if not query:
            query = (text or "")[:120]
        stop_noise = {
            "viral", "alert", "breaking", "tonight", "midnight", "urgent", "shocking",
            "secret", "exposed", "share", "before", "deleted", "immediately", "fake", "fact", "check",
        }
        raw_words = re.findall(r"[A-Za-z0-9\u0900-\u097F\u0C00-\u0C7F]+", query)
        query_words = [w for w in raw_words if w.lower() not in stop_noise][:6] or raw_words[:6]
        search_q = " ".join(query_words)
        if len(search_q) < 6:
            return {"status": "SKIPPED_SHORT_QUERY", "matches": [], "factcheck_risk": None}

        cache_k = f"fc:{search_q.lower()}"
        cached = _cache_get(cache_k, max_age_sec=600)
        if cached is not None:
            return cached

        matches = []
        api_used = False
        api_key = getattr(config, "GOOGLE_FACTCHECK_API_KEY", "") or ""
        if api_key:
            try:
                url = (
                    "https://factchecktools.googleapis.com/v1alpha1/claims:search"
                    f"?query={urllib.parse.quote(search_q)}&languageCode=en&pageSize=4&key={urllib.parse.quote(api_key)}"
                )
                req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-FactCheck/2.0"})
                with urllib.request.urlopen(req, timeout=6.0, context=_get_ssl_context()) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                api_used = True
                for claim in data.get("claims", [])[:4]:
                    ctext = claim.get("text", "")
                    for rev in claim.get("claimReview", [])[:1]:
                        rating = rev.get("textualRating", "Unrated")
                        pub = (rev.get("publisher") or {}).get("name", "IFCN Reviewer")
                        matches.append({
                            "claim_text": ctext[:180],
                            "rating": rating,
                            "publisher": pub,
                            "url": rev.get("url", ""),
                            "layer": "Google Fact Check Tools API",
                        })
            except Exception as e:
                logger.warning("Google Fact Check API notice: %s", e)

        # Layer B: $0 Google News Fact-Check / PIB fallback if API returned zero items
        if not matches:
            try:
                rss_q = urllib.parse.quote_plus(f"{search_q} (\"fact check\" OR \"PIB Fact Check\" OR \"Alt News\")")
                url = f"https://news.google.com/rss/search?q={rss_q}&hl=en-IN&gl=IN&ceid=IN:en"
                req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-FactCheck/2.0"})
                with urllib.request.urlopen(req, timeout=5.0, context=_get_ssl_context()) as resp:
                    root = ET.fromstring(resp.read())
                for item in root.findall("./channel/item")[:3]:
                    it_title = (item.findtext("title") or "").strip()
                    it_link = (item.findtext("link") or "").strip()
                    src_el = item.find("source")
                    pub = src_el.text if src_el is not None and src_el.text else "News Fact Check RSS"
                    low_t = it_title.lower()
                    # Check word overlap so unrelated fact checks don't pollute
                    overlap = sum(1 for w in query_words[:5] if len(w) > 3 and w.lower() in low_t)
                    if overlap >= 2:
                        rating = "Debunked / False" if any(k in low_t for k in ("fake", "false", "fact check", "debunk", "hoax", "no,")) else "Reported Check"
                        matches.append({
                            "claim_text": it_title[:180],
                            "rating": rating,
                            "publisher": pub,
                            "url": it_link,
                            "layer": "Google News Fact-Check RSS ($0 Fallback)",
                        })
            except Exception as e:
                logger.warning("Fact-check RSS fallback notice: %s", e)

        factcheck_risk = None
        if matches:
            ratings_low = " ".join(m["rating"].lower() + " " + m["claim_text"].lower() for m in matches)
            if any(k in ratings_low for k in ("false", "fake", "pants on fire", "altered", "misleading", "hoax", "fabricated", "debunk")):
                factcheck_risk = 0.88
            elif any(k in ratings_low for k in ("partly", "half true", "missing context")):
                factcheck_risk = 0.56
            elif any(k in ratings_low for k in ("true", "accurate", "verified")):
                factcheck_risk = 0.12

        res = {
            "status": "MATCHED" if matches else ("NO_API_MATCH" if api_used else "OFFLINE_OR_NO_MATCH"),
            "google_api_queried": api_used,
            "query_used": search_q,
            "matches": matches,
            "factcheck_risk": factcheck_risk,
        }
        _cache_set(cache_k, res)
        return res


# =============================================================================
# 4. OPEN-METEO REAL-TIME WEATHER VERIFIER
# =============================================================================

INDIA_CITY_COORDS = {
    "delhi": (28.6139, 77.2090, "New Delhi"),
    "new delhi": (28.6139, 77.2090, "New Delhi"),
    "mumbai": (19.0760, 72.8777, "Mumbai"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru"),
    "bangalore": (12.9716, 77.5946, "Bengaluru"),
    "chennai": (13.0827, 80.2707, "Chennai"),
    "kolkata": (22.5726, 88.3639, "Kolkata"),
    "jaipur": (26.9124, 75.7873, "Jaipur"),
    "ahmedabad": (23.0225, 72.5714, "Ahmedabad"),
}


class LiveOpenMeteoVerifier:
    """Fetches real-time Open-Meteo temperatures & precipitation for Indian cities."""

    def fetch_city_weather(self, city_key: str = "new delhi") -> Optional[Dict[str, Any]]:
        lat, lon, display = INDIA_CITY_COORDS.get(city_key.lower(), INDIA_CITY_COORDS["new delhi"])
        cache_k = f"wx:{display}"
        cached = _cache_get(cache_k, max_age_sec=600)
        if cached is not None:
            return cached
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation,wind_speed_10m,weather_code&timezone=Asia/Kolkata"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-Weather/2.0"})
            with urllib.request.urlopen(req, timeout=5.0, context=_get_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cur = data.get("current") or {}
            res = {
                "city": display,
                "temperature_c": cur.get("temperature_2m"),
                "precipitation_mm": cur.get("precipitation", 0.0),
                "wind_kmh": cur.get("wind_speed_10m"),
                "time": cur.get("time", ""),
                "source": "Open-Meteo Live API",
            }
            _cache_set(cache_k, res)
            return res
        except Exception as e:
            logger.warning("Open-Meteo weather fetch notice for %s: %s", display, e)
            return None

    def verify_weather_claim(self, combined_text: str) -> Dict[str, Any]:
        low = combined_text.lower()
        if not any(k in low for k in ("temperature", "heatwave", "rainfall", "monsoon", "snow", "°c", "celsius", "cyclone", "weather")):
            return {"triggered": False}

        matched_city = "new delhi"
        for k in INDIA_CITY_COORDS:
            if k in low:
                matched_city = k
                break

        live = self.fetch_city_weather(matched_city)
        anomaly_notes = []
        risk = None

        # Impossible atmospheric policy claims
        if re.search(r"\b(bans?|prohibits?)\s+(rainfall|rain|monsoon)\b", low):
            anomaly_notes.append("Physical Impossibility: Government cannot legally or physically prohibit meteorological rainfall.")
            risk = 0.96

        temp_claim = re.search(r"(-?\d+(?:\.\d+)?)\s*(?:°\s*c|degrees?\s*celsius|c\b)", low)
        if temp_claim and live and live.get("temperature_c") is not None:
            claimed_t = float(temp_claim.group(1))
            live_t = float(live["temperature_c"])
            diff = abs(claimed_t - live_t)
            if claimed_t > 56.0 or claimed_t < -15.0:
                anomaly_notes.append(f"Extreme meteorological outlier ({claimed_t}°C) far outside Indian climate bounds vs live {live['city']} reading ({live_t}°C).")
                risk = 0.92
            elif diff >= 18.0:
                anomaly_notes.append(f"Claimed {claimed_t}°C deviates by {diff:.1f}°C from live Open-Meteo telemetry in {live['city']} ({live_t}°C).")
                risk = 0.80
            else:
                anomaly_notes.append(f"Claimed {claimed_t}°C aligns within physical tolerance of live {live['city']} telemetry ({live_t}°C).")
                risk = 0.15

        return {
            "triggered": True,
            "live_weather": live,
            "weather_anomalies": anomaly_notes,
            "weather_risk": risk,
        }


# =============================================================================
# 5. PARAGRAPH STANCE CONSISTENCY (HEADLINE VS BODY)
# =============================================================================

class HeadlineStanceAnalyzer:
    """Computes cosine semantic consistency between headline and individual body paragraphs."""

    def analyze(self, title: str, text: str) -> Dict[str, Any]:
        clean_title = (title or "").strip()
        clean_text = (text or "").strip()
        if len(clean_title) < 8 or len(clean_text) < 40:
            return {"consistency_score": 0.85, "stance_status": "SHORT_TEXT_SKIPPED", "divergence_risk": 0.15}

        # Split body into sentence/paragraph chunks
        raw_paras = [p.strip() for p in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z0-9])", clean_text) if len(p.strip()) > 25]
        chunks = raw_paras[:5] if raw_paras else [clean_text[:600]]

        vecs = regional_encoder.encode([clean_title] + chunks, is_query=False)
        t_vec = vecs[0]
        sims = []
        flagged = []
        for idx, b_vec in enumerate(vecs[1:]):
            sim = float(np.dot(t_vec, b_vec))
            sims.append(sim)
            if sim < 0.25:
                flagged.append({"paragraph_index": idx + 1, "cosine_alignment": round(sim, 3), "excerpt": chunks[idx][:120]})

        mean_sim = float(np.mean(sims)) if sims else 0.75
        min_sim = float(np.min(sims)) if sims else 0.75
        # Low cosine similarity (<0.30 with neural encoder or <0.15 fallback) indicates headline baiting
        divergence_risk = max(0.05, min(0.90, 1.0 - max(0.0, mean_sim * 1.15)))
        status = "ALIGNED"
        if mean_sim < 0.28:
            status = "HEADLINE_BODY_DIVERGENCE_CLICKBAIT"
        elif min_sim < 0.20 and len(flagged) >= 2:
            status = "PARTIAL_STANCE_DRIFT"

        return {
            "consistency_score": round(max(0.0, min(1.0, mean_sim)), 4),
            "min_paragraph_alignment": round(max(0.0, min(1.0, min_sim)), 4),
            "divergence_risk": round(divergence_risk, 4),
            "stance_status": status,
            "flagged_sections": flagged,
        }


# =============================================================================
# 6. WEBSITE-USER PROPAGATION ANALYZER (dM/dt OVER REAL SITE TELEMETRY)
# =============================================================================

class WebsitePropagationTracker:
    """Computes genuine mathematical diffusion velocity dM/dt from real Smriti Shuddhi
    platform database metrics (duplicate submission burst, citizen flags, views, shares).
    """

    def measure_website_diffusion(self, news_col: Any, title: str, text: str) -> Dict[str, Any]:
        words = [w for w in re.findall(r"[A-Za-z0-9]{4,}", (title or "").lower())][:4]
        duplicate_count = 1
        total_views = 0
        total_shares = 0
        total_flags = 0
        earliest_ts = None

        try:
            if len(words) >= 2:
                regex_q = ".*".join(re.escape(w) for w in words[:2])
                similar = list(news_col.find({"title": {"$regex": regex_q}}))
            else:
                similar = []
            if similar:
                duplicate_count = max(1, len(similar))
                for doc in similar:
                    total_views += int(doc.get("view_count") or 0)
                    total_shares += int(doc.get("share_count") or 0)
                    total_flags += int(doc.get("flag_count") or 0)
                    cts = doc.get("created_at")
                    if cts:
                        try:
                            dt = datetime.fromisoformat(str(cts).replace("Z", "+00:00"))
                            if earliest_ts is None or dt < earliest_ts:
                                earliest_ts = dt
                        except Exception:
                            pass
        except Exception:
            pass

        elapsed_mins = 10.0
        if earliest_ts is not None:
            now_dt = datetime.now(timezone.utc)
            if earliest_ts.tzinfo is None:
                earliest_ts = earliest_ts.replace(tzinfo=timezone.utc)
            elapsed_mins = max(1.0, (now_dt - earliest_ts).total_seconds() / 60.0)

        interaction_mass = duplicate_count + total_shares * 1.5 + total_flags * 2.0 + (total_views * 0.05)
        velocity_dm_dt = interaction_mass / elapsed_mins
        flag_ratio = round(total_flags / max(1, total_views + duplicate_count), 4)

        viral_alert = duplicate_count >= 3 or velocity_dm_dt >= 0.45 or total_flags >= 2
        risk_boost = min(0.35, (duplicate_count - 1) * 0.08 + flag_ratio * 0.30)

        return {
            "similar_site_submissions": duplicate_count,
            "aggregate_views": total_views,
            "aggregate_shares": total_shares,
            "citizen_removal_flags": total_flags,
            "velocity_dm_dt_per_min": round(velocity_dm_dt, 4),
            "citizen_flag_ratio": flag_ratio,
            "viral_burst_alert": viral_alert,
            "website_propagation_risk_delta": round(risk_boost, 4),
            "graph_scope": "SmritiShuddhi Platform Interaction Diffusion (Zero Synthetic Cascades)",
        }


# =============================================================================
# 7. GEMINI BORDERLINE EXPLANATION SYNTHESIZER (OPTIONAL WHEN UNCERTAIN)
# =============================================================================

class GeminiFactSynthesisClient:
    """Calls Gemini Flash on borderline / half-truth claims with fast timeout fallback."""

    def synthesize(self, title: str, text: str, verdict_hint: str, evidence_snippets: List[str]) -> Optional[str]:
        api_key = getattr(config, "GEMINI_API_KEY", "") or ""
        if not api_key:
            return None
        ev_block = "\n".join(f"- {s[:180]}" for s in evidence_snippets[:3]) or "- No external debunk matched."
        prompt = (
            "You are a concise factual verification analyst for an Indian news portal. "
            "Write 2 plain-English sentences justifying why this claim is marked "
            f"'{verdict_hint}', referencing evidence neutrally.\n"
            f"Headline: {title[:200]}\nBody excerpt: {text[:400]}\nEvidence:\n{ev_block}"
        )
        raw_models = [
            "gemini-3-flash-preview",
            getattr(config, "GEMINI_MODEL", "gemini-3-flash-preview") or "gemini-3-flash-preview",
            "gemini-flash-latest",
            "gemini-flash-lite-latest",
        ]
        models = list(dict.fromkeys(m for m in raw_models if m and m != "gemini-3.8-flash"))
        ssl_ctx = _get_ssl_context()
        for mdl in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{mdl}:generateContent?key={urllib.parse.quote(api_key)}"
                payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=8.0, context=ssl_ctx) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                cands = data.get("candidates") or []
                if cands:
                    parts = (cands[0].get("content") or {}).get("parts") or []
                    if parts and parts[0].get("text"):
                        return parts[0]["text"].strip()
            except Exception as e:
                logger.warning("Gemini model '%s' notice: %s", mdl, e)
                continue
        return None


adversarial_defense = AdversarialDefenseAnalyzer()
structured_ner = StructuredNERAndSPOEngine()
live_factcheck_client = LiveFactCheckClient()
live_weather_verifier = LiveOpenMeteoVerifier()
headline_stance_analyzer = HeadlineStanceAnalyzer()
website_propagation_tracker = WebsitePropagationTracker()
gemini_synthesizer = GeminiFactSynthesisClient()
