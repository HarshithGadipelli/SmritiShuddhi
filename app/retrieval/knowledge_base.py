"""
Smriti Shuddhi - Quantitative Knowledge Base & Multi-Aspect Fact Engine
========================================================================
Combines:
1. Time-Series Quantitative Knowledge Base & Anomaly Detection (Stocks, Gold, Weather, Currency)
2. Context & Viral Propagation Dynamics (Source Credibility, Forward Velocity, Coercive Sharing)
3. Internal Evidence Archive (Stored Past Fact-Verification Proof Independent of External APIs)
"""

import re
import math
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("KnowledgeBase")

# -----------------------------------------------------------------------------
# 1. TIME-SERIES & QUANTITATIVE GROUND-TRUTH BASELINES
# -----------------------------------------------------------------------------

QUANTITATIVE_BASELINES = {
    "currency_banknotes": {
        "active_legal_tender": [10, 20, 50, 100, 200, 500],
        "demonetized_notes": [1000, 2000],
        "active_demonetization_order": False,
        "star_series_valid": True,
        "rule_summary": "All 500, 200, 100, 50, 20, and 10 rupee currency notes remain 100% legal tender. No midnight withdrawal exists."
    },
    "stock_market": {
        "bse_sensex": {"baseline": 81500, "normal_daily_bound_pct": 3.5, "extreme_crash_pct": 8.0, "unit": "points"},
        "nse_nifty": {"baseline": 24800, "normal_daily_bound_pct": 3.5, "extreme_crash_pct": 8.0, "unit": "points"},
        "rule_summary": "Daily Indian stock indices fluctuate within +/-3.5%. Claims of 10,000+ point daily collapse or 50% overnight crash are fabricated."
    },
    "gold_commodity": {
        "gold_24k_10g_inr": {"baseline": 78500, "min_realistic": 68000, "max_realistic": 92000, "daily_swing_limit_pct": 4.5, "unit": "₹"},
        "rule_summary": "Gold prices remain anchored in the ₹70,000-₹90,000 range per 10 grams. Claims of gold dropping to ₹20,000 or soaring to ₹2,00,000 overnight are mathematically false."
    },
    "forex_currency": {
        "usd_inr": {"baseline": 84.20, "min_realistic": 78.0, "max_realistic": 92.0, "daily_swing_limit_pct": 2.5, "unit": "₹"},
        "rule_summary": "USD/INR exchange rate trades within ₹80-₹88 per USD. Claims of 1 USD = ₹20 or ₹200 are false."
    },
    "weather_extremes": {
        "Delhi": {"min_c": 2.0, "max_c": 48.5},
        "Mumbai": {"min_c": 12.0, "max_c": 39.5},
        "Kolkata": {"min_c": 9.0, "max_c": 42.0},
        "Chennai": {"min_c": 18.0, "max_c": 43.0},
        "Hyderabad": {"min_c": 11.0, "max_c": 44.5},
        "Bengaluru": {"min_c": 13.0, "max_c": 39.2},
        "Srinagar": {"min_c": -14.0, "max_c": 36.0},
        "Rajasthan": {"min_c": 0.0, "max_c": 51.0},
        "general_india": {"min_c": -20.0, "max_c": 51.5},
        "rule_summary": "Realistic maximum temperatures in mainland India cap at 50-51°C in peak Rajasthan summer. Claims of 60°C+ or snow in tropical plains are physical anomalies."
    },
    "rbi_monetary_policy": {
        "repo_rate": 6.50,
        "reverse_repo_rate": 3.35,
        "max_single_meeting_change_bps": 75,
        "rule_summary": "RBI Monetary Policy Committee repo rate changes are bounded by +/-75 basis points."
    }
}

# -----------------------------------------------------------------------------
# 2. INTERNAL GROUND-TRUTH FACT VERIFICATION ARCHIVE
# -----------------------------------------------------------------------------

INTERNAL_FACT_EVIDENCE_ARCHIVE = [
    {
        "evidence_id": "EVID_RBI_500_CURRENCY",
        "topic": "500 Rupee Note Demonetization Rumors",
        "keywords": ["500", "currency", "rbi", "demonetize", "demonetization", "ban", "invalid", "midnight", "withdrawing", "star"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Reserve Bank of India (RBI) & PIB Fact Check",
        "summary": "Reserve Bank of India has issued zero notifications invalidating 500 rupee banknotes. All 500 currency notes with or without star symbol are fully legal tender.",
        "fact_score": 0.02
    },
    {
        "evidence_id": "EVID_ISRO_CHANDRAYAAN_DATA",
        "topic": "ISRO Lunar Mission Payload Archive",
        "keywords": ["isro", "chandrayaan", "issdc", "payload", "archive", "lunar", "pragyan", "vikram", "space centre"],
        "truth_status": "VERIFIED_OFFICIAL",
        "official_source": "Indian Space Research Organisation (ISRO)",
        "summary": "ISRO has officially released scientific payload data and spectrometry observations from the Chandrayaan mission on the ISSDC portal for global researchers.",
        "fact_score": 0.05
    },
    {
        "evidence_id": "EVID_GOVT_FREE_LAPTOP_SCHEME",
        "topic": "PM Free Laptop and 5000 Cash Scheme Fraud",
        "keywords": ["laptop", "5000", "pm yojana", "free laptop", "dhamaka", "register now", "scheme approved"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Press Information Bureau (PIB) Fact Check",
        "summary": "Government of India is NOT running any 'PM Free Laptop Yojana' offering free laptops or ₹5000 cash. Circulating links are phishing malware.",
        "fact_score": 0.98
    },
    {
        "evidence_id": "EVID_IMD_HEATWAVE_DELHI",
        "topic": "IMD Severe Heatwave Alerts",
        "keywords": ["imd", "heatwave", "red alert", "temperature", "delhi", "rajasthan", "haryana", "weather"],
        "truth_status": "VERIFIED_OFFICIAL",
        "official_source": "India Meteorological Department (IMD)",
        "summary": "IMD issues heatwave color-coded alerts during pre-monsoon summer across north-western plains. Severe heatwave corresponds to temperatures 44-47°C.",
        "fact_score": 0.08
    },
    {
        "evidence_id": "EVID_AADHAAR_EXPIRY_CLAIM",
        "topic": "Aadhaar Card Expiration Rumors",
        "keywords": ["aadhaar", "uidai", "expiry", "expired", "10 years", "deactivated", "fingerprint update"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Unique Identification Authority of India (UIDAI)",
        "summary": "Aadhaar numbers have lifetime validity. Rumors claiming mandatory invalidation after 10 years are false.",
        "fact_score": 0.96
    },
    {
        "evidence_id": "EVID_IRCTC_TATKAL_RULES",
        "topic": "IRCTC Ticket Booking Rules",
        "keywords": ["irctc", "railway", "tatkal", "ticket", "booking window", "agent only", "train"],
        "truth_status": "VERIFIED_OFFICIAL",
        "official_source": "Ministry of Railways & IRCTC",
        "summary": "IRCTC standard booking timings (10:00 AM for AC, 11:00 AM for Non-AC) remain active. No mandatory agent restriction has been implemented.",
        "fact_score": 0.06
    }
]


class QuantitativeAnomalyEngine:
    """Detects physically, financially, and economically anomalous claims by cross-referencing
    numerical assertions in news articles against stored time-series ground-truth baselines.
    """

    def analyze_quantities(self, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title} {text}".lower()
        anomalies = []
        anomaly_score = 0.0

        # 1. Currency Note Withdrawal & Demonetization Checks
        currency_keywords = ["500", "currency", "note", "rupee", "banknote", "cash", "demonet"]
        if any(k in combined for k in currency_keywords):
            invalidation_cues = ["withdraw", "ban", "invalid", "midnight", "tonight", "demonetiz", "freeze", "illegal tender", "invaliding", "cease"]
            has_invalidation = any(k in combined for k in invalidation_cues)
            mentions_500 = bool(re.search(r'\b500\b', combined))

            if has_invalidation and mentions_500:
                anomalies.append({
                    "dimension": "CURRENCY_DENOMINATION_ANOMALY",
                    "severity": "CRITICAL",
                    "claimed": "Withdrawal / Demonetization of ₹500 Banknotes",
                    "baseline": "₹500 notes are active legal tender under RBI Act 1934 Section 26.",
                    "discrepancy": "Direct contradiction of official RBI banknote registry and legal tender status.",
                    "penalty": 0.75
                })
                anomaly_score = max(anomaly_score, 0.90)

        # 2. Stock Market Extreme Crashes
        sensex_match = re.search(r'(?:sensex|bse)[\s\w]*(?:fell|dropped|crashed|down|lost)[\s\w]*?([0-9,]+)\s*(?:points|pts)?', combined)
        if sensex_match:
            try:
                pts_str = sensex_match.group(1).replace(",", "")
                pts = float(pts_str)
                if pts >= 7000:  # ~8.5% crash claim without circuit breaker
                    anomalies.append({
                        "dimension": "FINANCIAL_TIME_SERIES_ANOMALY",
                        "severity": "HIGH",
                        "claimed": f"Sensex crash of {pts:,.0f} points",
                        "baseline": f"BSE Baseline: ~81,500 pts. Normal daily swing: <3.5% (~2,800 pts). Circuit breakers trigger halt at 10%.",
                        "discrepancy": f"Claimed drop of {pts:,.0f} points represents an extreme non-halted market anomaly.",
                        "penalty": 0.65
                    })
                    anomaly_score = max(anomaly_score, 0.80)
            except ValueError:
                pass

        # 3. Gold Price Drastic Deviations
        gold_match = re.search(r'gold[\s\w]*(?:drop|crash|fall|fell|reach|trade|rate|price)[\s\w]*?(?:rs\.?|inr|₹)?\s*([0-9,]+)', combined)
        if gold_match:
            try:
                price_str = gold_match.group(1).replace(",", "")
                price = float(price_str)
                # If price is framed as per 10 grams and under ₹40,000 or over ₹1,50,000
                if 5000 <= price < 50000:
                    deviation = ((price - 78500) / 78500) * 100
                    anomalies.append({
                        "dimension": "COMMODITY_PRICE_ANOMALY",
                        "severity": "CRITICAL",
                        "claimed": f"Gold price at ₹{price:,.0f} per 10g",
                        "baseline": "Current commodity baseline: ₹75,000 - ₹85,000 per 10g (MCX).",
                        "discrepancy": f"Extreme price deviation ({deviation:.1f}% from benchmark). Mathematically inconsistent with sovereign gold trade.",
                        "penalty": 0.85
                    })
                    anomaly_score = max(anomaly_score, 0.88)
            except ValueError:
                pass

        # 4. Temperature Physical Impossibilities
        temp_match = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(?:degrees?|°|\s*c\b|\s*celsius)', combined)
        if temp_match:
            try:
                temp_val = float(temp_match.group(1))
                # Check for physically impossible summer heat (e.g. 56°C - 70°C in Indian cities)
                if 52.0 <= temp_val <= 90.0:
                    city_found = "India Regional"
                    for city, b in QUANTITATIVE_BASELINES["weather_extremes"].items():
                        if city.lower() in combined:
                            city_found = city
                            break
                    anomalies.append({
                        "dimension": "METEOROLOGICAL_PHYSICAL_ANOMALY",
                        "severity": "CRITICAL",
                        "claimed": f"{temp_val}°C in {city_found}",
                        "baseline": "IMD Historical Extreme Threshold: 50.6°C (Phalodi, Rajasthan).",
                        "discrepancy": f"Claimed temperature {temp_val}°C exceeds all meteorological historical records in India.",
                        "penalty": 0.80
                    })
                    anomaly_score = max(anomaly_score, 0.85)
            except ValueError:
                pass

        has_anomaly = len(anomalies) > 0
        severity = "NONE"
        if has_anomaly:
            severity = "CRITICAL" if any(a["severity"] == "CRITICAL" for a in anomalies) else "HIGH"

        return {
            "has_anomaly": has_anomaly,
            "anomaly_severity": severity,
            "s_quant_anomaly": round(anomaly_score, 4),
            "anomaly_count": len(anomalies),
            "anomalies": anomalies
        }


class ContextPropagationAnalyzer:
    """Analyzes contextual metadata, source attribution credibility, and viral propagation markers
    such as coercive sharing pressure and social media forwarding velocity.
    """

    TRUSTED_SOURCES = [
        "reuters", "reuters india", "times of india", "the times of india", "the hindu",
        "the hindu business line", "pib", "press information bureau", "pib national wire",
        "isro", "isro press office", "rbi", "rbi central bulletin", "imd", "imd weather bureau",
        "ndtv", "indian express", "live law", "eenadu", "sakshi", "bbc news"
    ]

    UNVERIFIED_SOURCE_MARKERS = [
        "whatsapp", "telegram", "forward", "viral post", "social media", "unknown", "anonymous",
        "facebook post", "blog", "group forward"
    ]

    VIRAL_PROPAGATION_PATTERNS = [
        r'\b(forward to all|share before deleted|share before midnight|viral alert|breaking dhamaka)\b',
        r'\b(secret exposed|hidden truth|leak exposed|panic|urgent warning|warning to public)\b',
        r'\b(forwarded as received|must forward|send to 10 friends|share in all groups)\b',
        r'\b(ban tonight|withdrawing tonight|breaking alert|save your money immediately)\b'
    ]

    def analyze_context_and_propagation(self, source: str, author: str, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title} {text}".lower()
        src_lower = (source or "").strip().lower()
        author_lower = (author or "").strip().lower()

        # 1. Source Credibility Scoring
        is_trusted = any(ts in src_lower for ts in self.TRUSTED_SOURCES)
        is_unverified_source = any(us in src_lower or us in author_lower for us in self.UNVERIFIED_SOURCE_MARKERS)

        if is_trusted:
            source_risk = 0.05
            source_verdict = "VERIFIED_INSTITUTIONAL_WIRE"
        elif is_unverified_source:
            source_risk = 0.85
            source_verdict = "UNVERIFIED_VIRAL_CHANNEL"
        else:
            source_risk = 0.40
            source_verdict = "INDEPENDENT_CITIZEN_SUBMISSION"

        # 2. Viral Propagation & Coercive Forwarding Cues
        propagation_cues = []
        for pat in self.VIRAL_PROPAGATION_PATTERNS:
            for match in re.finditer(pat, combined, re.IGNORECASE):
                propagation_cues.append(match.group(0))

        cue_count = len(propagation_cues)
        if cue_count >= 2:
            virality_pressure_score = min(0.95, 0.60 + cue_count * 0.15)
            propagation_band = "HIGH_COERCIVE_VIRALITY"
        elif cue_count == 1:
            virality_pressure_score = 0.65
            propagation_band = "MODERATE_SHARING_PRESSURE"
        else:
            virality_pressure_score = 0.10
            propagation_band = "ORGANIC_EDITORIAL_FRAMING"

        # Composite propagation risk score
        s_propagation = round(0.40 * source_risk + 0.60 * virality_pressure_score, 4)

        return {
            "s_propagation": s_propagation,
            "source_verdict": source_verdict,
            "source_risk": source_risk,
            "propagation_band": propagation_band,
            "virality_pressure_score": round(virality_pressure_score, 4),
            "detected_propagation_cues": propagation_cues[:6]
        }


class InternalEvidenceEngine:
    """Queries stored past verified ground-truth debunks and official bulletins without
    depending on external network connectivity or volatile third-party endpoints.
    """

    def query_evidence(self, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title} {text}".lower()
        matched_evidence = []

        for record in INTERNAL_FACT_EVIDENCE_ARCHIVE:
            keyword_hits = sum(1 for kw in record["keywords"] if kw in combined)
            if keyword_hits >= 2:
                matched_evidence.append({
                    "evidence_id": record["evidence_id"],
                    "topic": record["topic"],
                    "truth_status": record["truth_status"],
                    "official_source": record["official_source"],
                    "summary": record["summary"],
                    "keyword_hits": keyword_hits,
                    "fact_score": record["fact_score"]
                })

        if matched_evidence:
            # Sort by keyword hits
            matched_evidence.sort(key=lambda x: x["keyword_hits"], reverse=True)
            top_match = matched_evidence[0]
            return {
                "has_match": True,
                "evidence_status": "INTERNAL_EVIDENCE_FOUND",
                "top_match": top_match,
                "all_matches": matched_evidence,
                "s_internal_fact": top_match["fact_score"]
            }

        return {
            "has_match": False,
            "evidence_status": "NO_INTERNAL_EVIDENCE",
            "top_match": None,
            "all_matches": [],
            "s_internal_fact": 0.50
        }


# Global Singletons
quantitative_anomaly_engine = QuantitativeAnomalyEngine()
propagation_analyzer = ContextPropagationAnalyzer()
internal_evidence_engine = InternalEvidenceEngine()
