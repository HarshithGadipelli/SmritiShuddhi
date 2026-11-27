import json
import math
import re
import ssl
import time
import logging
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import config
from app.retrieval.encoder import regional_encoder

logger = logging.getLogger("ExternalVerifiers")

IST = timezone(timedelta(hours=5, minutes=30))


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
    "WHO", "UNICEF", "UNESCO", "NASA", "BBC", "REUTERS", "PTI", "ANI", "NSE", "BSE",
    "Sensex", "Nifty", "Reserve Bank of India", "Election Commission of India", "Supreme Court",
    "High Court", "Ministry of Finance", "Ministry of Home Affairs", "Ministry of Health",
    "Ministry of Railways", "NITI Aayog", "DRDO", "BCCI", "TRAI", "IRCTC", "SBI",
    "Dodla Dairy", "Heritage Foods", "HDFC Bank", "ICICI Bank", "TCS", "Infosys", "Reliance",
}

GPE_LEXICON = {
    "India", "New Delhi", "Delhi", "Mumbai", "Hyderabad", "Bengaluru", "Bangalore",
    "Chennai", "Kolkata", "Pune", "Ahmedabad", "Jaipur", "Lucknow", "Patna",
    "Telangana", "Andhra Pradesh", "Maharashtra", "Karnataka", "Tamil Nadu",
    "Uttar Pradesh", "Gujarat", "Rajasthan", "Kashmir", "Ladakh", "Kochi",
    "Nadergul", "Rangareddy", "Secunderabad", "Shamshabad", "Warangal", "Vijayawada",
    "Visakhapatnam", "Guntur", "Tirupati", "Nagpur", "Indore", "Bhopal", "Surat",
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

        # Dynamic Indian corporate / company / institutional phrases
        for comp in re.findall(
            r"\b([A-Za-z][A-Za-z]{2,}(?:\s+[A-Za-z][A-Za-z]{2,}){0,2}\s+(?:Dairy|Foods|Bank|Industries|Motors|Pharma|Energy|Steel|Limited|Ltd|Corp|Corporation))\b",
            combined,
            re.IGNORECASE,
        ):
            if comp.strip() not in entities["ORG"]:
                entities["ORG"].append(comp.strip().title())

        for loc in GPE_LEXICON:
            if re.search(r"\b" + re.escape(loc) + r"\b", combined, re.IGNORECASE):
                entities["GPE"].append(loc)

        # Place name heuristic after spatial prepositions ("rainfall at Nadergul", "in Shamshabad")
        for prep_loc in re.findall(r"\b(?:at|in|near|across)\s+([A-Z][a-z]{3,})\b", combined):
            if prep_loc.lower() not in {"india", "november", "december", "january", "february", "march", "april", "may", "june", "july", "august", "september", "october"}:
                if prep_loc not in entities["GPE"]:
                    entities["GPE"].append(prep_loc)

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
            r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|(?:\d{1,2}\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{0,2},?\s*\d{4}|20[1-3]\d|today|tonight|tomorrow)\b",
            combined,
            re.IGNORECASE,
        )
        entities["DATE_TIME"] = sorted(list(set(d.strip() for d in dates if d.strip())))[:8]

        quants = re.findall(
            r"(?:₹|Rs\.?\s*|INR\s*|\$)\s*\d[\d,]*(?:\.\d+)?(?:\s*(?:crore|lakh|billion|million))?|\b\d+(?:\.\d+)?\s*(?:%|°C|C|degrees|mm|cm|crore|lakh)\b",
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
            r"\b(announced|banned|banning|withdrew|withdrawing|launched|confirmed|claimed|ordered|reduced|increased|hiked|rose|rises|surged|fell|dropped|recorded|received|cancelled|arrested|landed|issued|mandated|denies|debunks)\b",
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
            k in low for k in ("press release", "notification", "circular", "spokesperson", "according to ", "exchange filing", "imd")
        )
        unverified_quote_flag = (len(quote_texts) > 0 and not has_named_attribution) or len(unverified_markers) > 0

        lineage_status = "ATTRIBUTED_LINEAGE"
        src_low = (source or "").strip().lower()
        if unverified_quote_flag:
            lineage_status = "UNVERIFIED_OR_PHANTOM_QUOTE"
        elif src_low in ("unknown", "social", "whatsapp", "viral", "social media forward", "whatsapp group broadcast"):
            lineage_status = "UNKNOWN_PUBLISHER_LINEAGE"
        elif not src_low or any(k in src_low for k in ("independent", "citizen", "reporter", "stream_ingest")):
            lineage_status = "STANDARD_CITIZEN_LINEAGE"

        return {
            "quote_count": len(quote_texts),
            "sample_quotes": quote_texts[:2],
            "unverified_quote_flag": unverified_quote_flag,
            "phantom_attribution_cues": unverified_markers,
            "source_lineage_status": lineage_status,
        }

    def query_wikidata_entities(self, entities: Dict[str, List[str]]) -> List[Dict[str, str]]:
        """Lightweight live Wikidata entity check for primary subjects/organizations."""
        candidates = (entities.get("ORG", []) + entities.get("PERSON", []) + entities.get("GPE", []))[:2]
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
# 4. OPEN-METEO REAL-TIME WEATHER & LOCAL GEOCODING VERIFIER
# =============================================================================

INDIA_CITY_COORDS = {
    "delhi": (28.6139, 77.2090, "New Delhi"),
    "new delhi": (28.6139, 77.2090, "New Delhi"),
    "mumbai": (19.0760, 72.8777, "Mumbai"),
    "hyderabad": (17.3850, 78.4867, "Hyderabad"),
    "nadergul": (17.2740, 78.5450, "Nadergul (Rangareddy / Hyderabad)"),
    "rangareddy": (17.3100, 78.4900, "Rangareddy"),
    "secunderabad": (17.4399, 78.4983, "Secunderabad"),
    "shamshabad": (17.2403, 78.4294, "Shamshabad"),
    "gachibowli": (17.4401, 78.3489, "Gachibowli (Hyderabad)"),
    "warangal": (17.9689, 79.5941, "Warangal"),
    "vijayawada": (16.5062, 80.6480, "Vijayawada"),
    "visakhapatnam": (17.6868, 83.2185, "Visakhapatnam"),
    "guntur": (16.3067, 80.4365, "Guntur"),
    "tirupati": (13.6288, 79.4192, "Tirupati"),
    "bengaluru": (12.9716, 77.5946, "Bengaluru"),
    "bangalore": (12.9716, 77.5946, "Bengaluru"),
    "chennai": (13.0827, 80.2707, "Chennai"),
    "kolkata": (22.5726, 88.3639, "Kolkata"),
    "jaipur": (26.9124, 75.7873, "Jaipur"),
    "ahmedabad": (23.0225, 72.5714, "Ahmedabad"),
    "pune": (18.5204, 73.8567, "Pune"),
    "lucknow": (26.8467, 80.9462, "Lucknow"),
    "patna": (25.5941, 85.1376, "Patna"),
    "bhopal": (23.2599, 77.4126, "Bhopal"),
    "indore": (22.7196, 75.8577, "Indore"),
    "kochi": (9.9312, 76.2673, "Kochi"),
    "nagpur": (21.1458, 79.0882, "Nagpur"),
    "surat": (21.1702, 72.8311, "Surat"),
    "guwahati": (26.1445, 91.7362, "Guwahati"),
    "bhubaneswar": (20.2961, 85.8245, "Bhubaneswar"),
}


class LiveOpenMeteoVerifier:
    """Fetches real-time Open-Meteo temperatures & precipitation for Indian cities & towns."""

    def _geocode_indian_place(self, place: str) -> Optional[Tuple[float, float, str]]:
        key = place.strip().lower()
        if not key or len(key) < 3:
            return None
        if key in INDIA_CITY_COORDS:
            return INDIA_CITY_COORDS[key]

        cache_k = f"geo:{key}"
        cached = _cache_get(cache_k, max_age_sec=86400)
        if cached is not None:
            return cached or None

        ssl_ctx = _get_ssl_context()
        try:
            url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(place)}&count=3&countryCode=IN&language=en&format=json"
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-Geo/2.0"})
            with urllib.request.urlopen(req, timeout=4.0, context=ssl_ctx) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            hits = data.get("results") or []
            if hits:
                h = hits[0]
                res = (float(h["latitude"]), float(h["longitude"]), str(h.get("name", place)))
                _cache_set(cache_k, res)
                return res
        except Exception:
            pass

        try:
            url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(place + ', India')}&format=json&limit=1"
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-Geo/2.0"})
            with urllib.request.urlopen(req, timeout=4.0, context=ssl_ctx) as resp:
                hits = json.loads(resp.read().decode("utf-8"))
            if hits:
                h = hits[0]
                res = (float(h["lat"]), float(h["lon"]), str(place).title())
                _cache_set(cache_k, res)
                return res
        except Exception:
            pass

        _cache_set(cache_k, ())
        return None

    def fetch_city_weather(self, city_key: str = "new delhi") -> Optional[Dict[str, Any]]:
        resolved = self._geocode_indian_place(city_key) or INDIA_CITY_COORDS["new delhi"]
        lat, lon, display = resolved
        cache_k = f"wx:{round(lat, 2)}:{round(lon, 2)}"
        cached = _cache_get(cache_k, max_age_sec=600)
        if cached is not None:
            return cached
        try:
            url = (
                "https://api.open-meteo.com/v1/forecast"
                f"?latitude={lat}&longitude={lon}"
                "&current=temperature_2m,precipitation,rain,showers,wind_speed_10m,weather_code,cloud_cover"
                "&daily=precipitation_sum,rain_sum,weather_code&past_days=1&forecast_days=1&timezone=Asia/Kolkata"
            )
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-Weather/2.0"})
            with urllib.request.urlopen(req, timeout=5.0, context=_get_ssl_context()) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            cur = data.get("current") or {}
            daily = data.get("daily") or {}
            p_sums = [float(x or 0.0) for x in (daily.get("precipitation_sum") or [])]
            r_sums = [float(x or 0.0) for x in (daily.get("rain_sum") or [])]
            w_codes = [int(x or 0) for x in (daily.get("weather_code") or [])]
            res = {
                "city": display,
                "temperature_c": cur.get("temperature_2m"),
                "precipitation_mm": float(cur.get("precipitation") or 0.0),
                "rain_mm": float(cur.get("rain") or 0.0),
                "showers_mm": float(cur.get("showers") or 0.0),
                "cloud_cover_pct": cur.get("cloud_cover"),
                "weather_code": int(cur.get("weather_code") or 0),
                "daily_precip_sum_mm": max(p_sums) if p_sums else 0.0,
                "daily_rain_sum_mm": max(r_sums) if r_sums else 0.0,
                "recent_rain_wmo": any(c >= 51 for c in w_codes) or int(cur.get("weather_code") or 0) >= 51,
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
        wx_terms = ("temperature", "heatwave", "rainfall", "rain", "monsoon", "drizzle", "shower", "downpour", "snow", "°c", "celsius", "cyclone", "weather", "flood")
        if not any(k in low for k in wx_terms):
            return {"triggered": False}

        matched_place = None
        for k in INDIA_CITY_COORDS:
            if re.search(r"\b" + re.escape(k) + r"\b", low):
                matched_place = k
                break
        if not matched_place:
            m_loc = re.search(r"\b(?:at|in|near|across)\s+([a-zA-Z]{4,24})\b", combined_text)
            if m_loc:
                cand = m_loc.group(1)
                if cand.lower() not in {"today", "india", "november", "december", "january", "state", "region", "area", "district", "morning", "evening", "night"}:
                    matched_place = cand
        matched_place = matched_place or "new delhi"

        live = self.fetch_city_weather(matched_place)
        anomaly_notes = []
        risk = None
        corroborated = False

        # 1. Impossible atmospheric policy claims
        if re.search(r"\b(bans?|prohibits?)\s+(rainfall|rain|monsoon)\b", low):
            anomaly_notes.append("Physical Impossibility: Government cannot legally or physically prohibit meteorological rainfall.")
            risk = 0.96

        # 2. Temperature check
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
                risk = 0.14
                corroborated = True

        # 3. Rainfall / precipitation verification (current + past 24h)
        if any(k in low for k in ("rainfall", "rain", "drizzle", "shower", "downpour", "monsoon", "wet", "flood")) and live and risk is None:
            precip_24h = max(
                float(live.get("precipitation_mm") or 0.0),
                float(live.get("rain_mm") or 0.0) + float(live.get("showers_mm") or 0.0),
                float(live.get("daily_precip_sum_mm") or 0.0),
                float(live.get("daily_rain_sum_mm") or 0.0),
            )
            has_rain = precip_24h > 0.0 or bool(live.get("recent_rain_wmo"))
            clouds = live.get("cloud_cover_pct")
            if has_rain:
                corroborated = True
                risk = 0.14
                anomaly_notes.append(
                    f"Rain/precipitation corroborated near {live['city']} (current={live['precipitation_mm']}mm, 24h_sum={precip_24h:.1f}mm, temp={live['temperature_c']}°C)."
                )
            elif any(w in low for w in ("slight", "light", "scattered", "mild", "drizzle", "isolated", "overnight")):
                risk = 0.30
                anomaly_notes.append(
                    f"Localized light rainfall near {live['city']} (station readout: cloud_cover={clouds}%, precip={precip_24h:.1f}mm, temp={live['temperature_c']}°C); plausible micro-scale weather variation."
                )

        return {
            "triggered": True,
            "corroborated": corroborated,
            "live_weather": live,
            "weather_anomalies": anomaly_notes,
            "weather_risk": risk,
        }


# =============================================================================
# 5. GENERAL LIVE NEWS WIRE & MARKET TICKER CORROBORATION ENGINE ($0)
# =============================================================================

class LiveNewsAndMarketCorroborationClient:
    """Queries live general news wires (Google News RSS) and financial equity markets
    (Yahoo Finance NSE/BSE search + chart telemetry) to verify developing real-world events
    happening on today's exact date instead of penalizing them as unknown rumors.
    """

    FIN_KEYWORDS = {
        "stock", "stocks", "share", "shares", "nifty", "sensex", "nse", "bse", "rally",
        "surges", "rises", "jumps", "gains", "falls", "drops", "q1", "q2", "q3", "q4",
        "earnings", "profit", "revenue", "dividend", "ipo", "market", "equity",
    }

    NOISE_WORDS = {
        "today", "breaking", "alert", "viral", "news", "report", "reports", "reported",
        "slight", "minor", "major", "yesterday", "recorded", "observed", "rises", "falls",
        "november", "december", "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "2024", "2025", "2026", "date", "same",
    }

    def _query_google_news_rss(self, query_str: str, limit: int = 6) -> List[Dict[str, str]]:
        q_clean = re.sub(r"\s+", " ", (query_str or "").strip())
        if len(q_clean) < 4:
            return []
        cache_k = f"gn:{q_clean.lower()}:{limit}"
        cached = _cache_get(cache_k, max_age_sec=300)
        if cached is not None:
            return cached
        items_out: List[Dict[str, str]] = []
        try:
            url = f"https://news.google.com/rss/search?q={urllib.parse.quote_plus(q_clean)}&hl=en-IN&gl=IN&ceid=IN:en"
            req = urllib.request.Request(url, headers={"User-Agent": "SmritiShuddhi-Wire/3.0"})
            with urllib.request.urlopen(req, timeout=5.0, context=_get_ssl_context()) as resp:
                root = ET.fromstring(resp.read())
            for it in root.findall("./channel/item")[:limit]:
                t = (it.findtext("title") or "").strip()
                src_el = it.find("source")
                pub = (src_el.text or "").strip() if src_el is not None else "Google News Wire"
                pub_date = (it.findtext("pubDate") or "").strip()
                link = (it.findtext("link") or "").strip()
                if t:
                    items_out.append({"title": t, "publisher": pub, "published_at": pub_date, "url": link})
        except Exception as exc:
            logger.debug("Google News RSS corroboration notice (%s): %s", q_clean, exc)
        _cache_set(cache_k, items_out)
        return items_out

    def _query_stock_market(self, title: str, text: str, entities: Dict[str, List[str]]) -> Optional[Dict[str, Any]]:
        combined = f"{title} {text}".strip()
        low = combined.lower()
        tokens = set(re.findall(r"[a-zA-Z]+", low))
        if not tokens.intersection(self.FIN_KEYWORDS):
            return None

        # Candidate search string: prefer ORG entities or leading non-noise words before 'stock'/'share'
        cand_name = ""
        if entities.get("ORG"):
            for org in entities["ORG"]:
                if org.upper() not in {"NSE", "BSE", "SEBI", "RBI", "SENSEX", "NIFTY"}:
                    cand_name = org
                    break
        if not cand_name:
            m = re.search(r"([A-Za-z][A-Za-z\s&]{2,35}?)\s+(?:stock|stocks|share|shares|ltd|limited)\b", title or combined, re.IGNORECASE)
            if m:
                cand_name = m.group(1).strip()
        if not cand_name:
            lead_words = [w for w in re.findall(r"[A-Za-z]{3,}", title or "") if w.lower() not in self.FIN_KEYWORDS and w.lower() not in self.NOISE_WORDS]
            cand_name = " ".join(lead_words[:2])
        if len(cand_name) < 3:
            return None

        cache_k = f"yf:{cand_name.lower()}"
        cached = _cache_get(cache_k, max_age_sec=300)
        if cached is not None:
            return cached or None

        ssl_ctx = _get_ssl_context()
        try:
            s_url = f"https://query1.finance.yahoo.com/v1/finance/search?q={urllib.parse.quote(cand_name)}&quotesCount=5"
            req = urllib.request.Request(s_url, headers={"User-Agent": "Mozilla/5.0 SmritiShuddhi-Finance/3.0"})
            with urllib.request.urlopen(req, timeout=5.0, context=ssl_ctx) as resp:
                sdata = json.loads(resp.read().decode("utf-8"))
            quotes = [q for q in (sdata.get("quotes") or []) if q.get("symbol")]
            # Prioritize NSE (.NS) or BSE (.BO) equities
            quotes.sort(key=lambda q: (0 if str(q.get("symbol", "")).endswith((".NS", ".BO")) else 1))
            if not quotes:
                _cache_set(cache_k, {})
                return None

            q0 = quotes[0]
            sym = str(q0["symbol"])
            shortname = str(q0.get("shortname") or q0.get("longname") or sym)
            c_url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(sym)}?range=5d&interval=1d"
            req_c = urllib.request.Request(c_url, headers={"User-Agent": "Mozilla/5.0 SmritiShuddhi-Finance/3.0"})
            with urllib.request.urlopen(req_c, timeout=5.0, context=ssl_ctx) as resp_c:
                cdata = json.loads(resp_c.read().decode("utf-8"))
            meta = (((cdata.get("chart") or {}).get("result") or [{}])[0]).get("meta") or {}
            price = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose") or meta.get("previousClose")
            pct_chg = round(((float(price) - float(prev)) / float(prev)) * 100.0, 2) if (price and prev) else None

            res = {
                "symbol": sym,
                "company": shortname,
                "exchange": str(q0.get("exchange") or meta.get("exchangeName") or "NSE/BSE"),
                "price": price,
                "previous_close": prev,
                "change_pct": pct_chg,
                "currency": meta.get("currency", "INR"),
            }
            _cache_set(cache_k, res)
            return res
        except Exception as exc:
            logger.debug("Finance lookup notice (%s): %s", cand_name, exc)
            _cache_set(cache_k, {})
            return None

    def corroborate(self, title: str, text: str, entities: Dict[str, List[str]]) -> Dict[str, Any]:
        combined = f"{title} {text}".strip()
        raw_words = [
            w for w in re.findall(r"[A-Za-z0-9\u0900-\u097F\u0C00-\u0C7F]{3,}", title or combined)
            if w.lower() not in self.NOISE_WORDS
        ]
        search_q = " ".join(raw_words[:5])
        news_hits = self._query_google_news_rss(search_q, limit=6) if search_q else []

        # Also query broader regional anchor + topic (e.g. Hyderabad rain if local village/suburb like Nadergul)
        low_c = combined.lower()
        if not news_hits and any(w in low_c for w in ("nadergul", "rangareddy", "shamshabad", "secunderabad", "gachibowli")):
            if any(w in low_c for w in ("rain", "rainfall", "weather", "monsoon", "shower")):
                news_hits = self._query_google_news_rss("Hyderabad rainfall rain weather", limit=5)

        # Keep hits sharing at least one meaningful subject keyword (or Hyderabad weather proxy)
        subject_terms = {w.lower() for w in raw_words[:5] if len(w) >= 3}
        matched_news = []
        for h in news_hits:
            ht_low = h["title"].lower()
            overlap = sum(1 for t in subject_terms if t in ht_low)
            if overlap >= 1 or "hyderabad" in ht_low:
                matched_news.append(h)

        market_info = self._query_stock_market(title, text, entities)
        notes: List[str] = []
        corroborated = False
        risk: Optional[float] = None

        if market_info and market_info.get("price"):
            chg = market_info.get("change_pct")
            sym = market_info["symbol"]
            comp = market_info["company"]
            pct_str = f" ({chg:+.2f}%)" if chg is not None else ""
            # Check if user's text makes an extreme physically absurd percentage claim (>75% single day crash/spike)
            pct_claim = re.search(r"(\d+(?:\.\d+)?)\s*%", combined)
            claimed_p = float(pct_claim.group(1)) if pct_claim else None
            if claimed_p and claimed_p >= 60.0 and chg is not None and abs(chg) < 15.0:
                notes.append(f"Market Discrepancy: Claim asserts {claimed_p:.0f}% swing, while live {sym} telemetry shows {market_info['currency']} {market_info['price']}{pct_str}.")
                risk = 0.82
            else:
                corroborated = True
                risk = 0.16
                notes.append(f"Live Equity Telemetry Verified: {comp} ({sym}) active at {market_info['currency']} {market_info['price']}{pct_str}.")

        if matched_news:
            corroborated = True
            if risk is None:
                risk = 0.16 if len(matched_news) >= 2 else 0.24
            notes.append(f"Live Wire Match: {len(matched_news)} recent dispatch(es) found (e.g. {matched_news[0]['publisher']}: {matched_news[0]['title'][:95]}).")

        return {
            "status": "LIVE_CORROBORATED" if corroborated else "NO_LIVE_MATCH",
            "corroborated": corroborated,
            "corroboration_risk": risk,
            "news_matches": matched_news[:4],
            "market_match": market_info,
            "corroboration_notes": notes,
        }


# =============================================================================
# 6. PARAGRAPH STANCE CONSISTENCY (HEADLINE VS BODY)
# =============================================================================

class HeadlineStanceAnalyzer:
    """Computes cosine semantic consistency between headline and individual body paragraphs."""

    def analyze(self, title: str, text: str) -> Dict[str, Any]:
        clean_title = (title or "").strip()
        clean_text = (text or "").strip()
        if len(clean_title) < 8 or len(clean_text) < 40:
            return {"consistency_score": 0.85, "stance_status": "SHORT_TEXT_SKIPPED", "divergence_risk": 0.15}

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
# 7. WEBSITE-USER PROPAGATION ANALYZER (dM/dt OVER REAL SITE TELEMETRY)
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
# 8. GEMINI CURRENT-DATE GROUNDED VERIFICATION SYNTHESIZER
# =============================================================================

class GeminiFactSynthesisClient:
    """Calls Gemini Flash anchored with the exact current IST date and real-time wire/telemetry context."""

    def synthesize(self, title: str, text: str, verdict_hint: str, evidence_snippets: List[str]) -> Optional[str]:
        api_key = getattr(config, "GEMINI_API_KEY", "") or ""
        if not api_key:
            return None
        now_ist = datetime.now(IST)
        today_str = now_ist.strftime("%A, %B %d, %Y (%Y-%m-%d %H:%M IST)")
        ev_block = "\n".join(f"- {s[:220]}" for s in evidence_snippets[:5] if s) or "- Evaluated using live multi-track stylometric, temporal, weather, and market checks."
        prompt = (
            "You are a concise factual verification analyst for an Indian real-time news portal.\n"
            f"IMPORTANT TEMPORAL ANCHOR: Today's verified current date/time is {today_str}. "
            "Do NOT claim today's date or 2026 dates up to today are 'future dates' or beyond your knowledge cutoff.\n"
            "Write 2 clear, factual sentences explaining the verification status of this article strictly from the real-time evidence and telemetry provided.\n"
            f"System Verdict Hint: {verdict_hint}\n"
            f"Headline: {title[:220]}\n"
            f"Body excerpt: {text[:450]}\n"
            f"Real-Time Evidence & Telemetry:\n{ev_block}"
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
live_corroboration_client = LiveNewsAndMarketCorroborationClient()
headline_stance_analyzer = HeadlineStanceAnalyzer()
website_propagation_tracker = WebsitePropagationTracker()
gemini_synthesizer = GeminiFactSynthesisClient()
