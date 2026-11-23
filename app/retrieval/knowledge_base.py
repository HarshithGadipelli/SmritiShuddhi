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
    "crude_oil_energy": {
        "brent_crude_usd_bbl": {"baseline": 74.50, "min_realistic": 55.0, "max_realistic": 115.0, "daily_swing_limit_pct": 6.0, "unit": "$/bbl"},
        "rule_summary": "Brent crude oil trades within $60-$100/barrel. Claims of crude dropping to $15 or spiking to $250 overnight are false."
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
    },
    {
        "evidence_id": "EVID_FREE_ENERGY_MIRACLE_INVENTION",
        "topic": "Free Fuel / Perpetual Motion / Miracle Energy Invention Fraud",
        "keywords": ["free fuel", "free electricity", "water fuel", "water running car", "perpetual motion", "water to petrol", "miracle invention"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Department of Science and Technology (DST) & PIB Fact Check",
        "summary": "Claims of water-running cars, free perpetual electricity generators, or secret fuel inventions suppressed by oil cartels are scientifically fraudulent and violate thermodynamic laws.",
        "fact_score": 0.98
    },
    {
        "evidence_id": "EVID_HEALTH_MIRACLE_CURE",
        "topic": "Miracle Medical Disease Cure Hoaxes",
        "keywords": ["cure cancer in 24 hours", "miracle cure", "cure all diseases", "who approved miracle", "lemon baking soda cancer"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Ministry of Ayush, ICMR & WHO Fact Desk",
        "summary": "No verified clinical medical evidence exists for overnight miracle cancer cures or instant cures circulating on social messaging channels.",
        "fact_score": 0.96
    },
    {
        "evidence_id": "EVID_RBI_MONEY_DOUBLING_FRAUD",
        "topic": "Government Money Doubling & Direct Cash Phishing",
        "keywords": ["double money", "rbi lottery", "pm mudra free", "7 days double", "claim cash prize"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Reserve Bank of India & PIB Fact Check",
        "summary": "RBI does not run lotteries or offer cash prizes. Any scheme promising doubling money in days or free direct bank transfers is fraudulent phishing.",
        "fact_score": 0.97
    },
    {
        "evidence_id": "EVID_DOT_SIM_DEACTIVATION_FRAUD",
        "topic": "Department of Telecom SIM Card Disconnection Hoaxes",
        "keywords": ["sim block", "deactivate in 24 hours", "dot blocking", "kyc expired sim", "call this number to avoid block"],
        "truth_status": "VERIFIED_DEBUNK",
        "official_source": "Department of Telecommunications (DoT)",
        "summary": "Department of Telecommunications (DoT) does not issue calls or messages threatening immediate 24-hour disconnection for KYC. Such messages are cyber scams.",
        "fact_score": 0.95
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

        # 4. Crude Oil & Energy Price Collapse/Spike Anomaly
        crude_match = re.search(r'(?:crude|brent|petroleum)[\s\w]*(?:drop|crash|fall|fell|reach|trade|rate|price|soar|surge|plunge|plunges|collapse|collapses|slump|slumps|tumble|tumbles)[\s\w]*?(?:\$|usd|rs\.?|₹|\bto\b|\bat\b)?\s*([0-9]+(?:\.[0-9]+)?)', combined)
        if crude_match:
            try:
                price = float(crude_match.group(1))
                if (1.0 <= price <= 25.0) or price >= 200.0:
                    anomalies.append({
                        "dimension": "ENERGY_COMMODITY_ANOMALY",
                        "severity": "CRITICAL",
                        "claimed": f"Crude oil at ${price:,.1f}/barrel",
                        "baseline": "Brent crude baseline: ~$74.50/barrel (Normal trading range: $55-$110/barrel).",
                        "discrepancy": f"Claimed crude price of ${price:,.1f}/barrel is an extreme non-market dislocation anomaly.",
                        "penalty": 0.80
                    })
                    anomaly_score = max(anomaly_score, 0.85)
            except ValueError:
                pass

        # 5. Temperature Physical Impossibilities
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

        # 6. Forex USD/INR Drastic Dislocation Anomaly
        forex_match = re.search(r'(?:usd|dollar|rupee)[\s\w]*(?:drop|crash|fall|fell|reach|trade|rate|equal|equals|plunge|plunges|soar|surge)[\s\w]*?(?:rs\.?|inr|₹|\$)?\s*([0-9]+(?:\.[0-9]+)?)', combined)
        if forex_match:
            try:
                rate = float(forex_match.group(1))
                if (1.0 <= rate <= 45.0) or (rate >= 140.0):
                    anomalies.append({
                        "dimension": "FOREX_EXCHANGE_ANOMALY",
                        "severity": "CRITICAL",
                        "claimed": f"USD/INR exchange rate at ₹{rate:,.1f}",
                        "baseline": "USD/INR baseline: ~₹84.20 (Normal trading band: ₹80 - ₹90).",
                        "discrepancy": f"Claimed rate of ₹{rate:,.1f}/USD is an extreme monetary dislocation anomaly.",
                        "penalty": 0.85
                    })
                    anomaly_score = max(anomaly_score, 0.88)
            except ValueError:
                pass

        # 7. Pseudoscience & Thermodynamic Free Energy Physical Anomaly
        free_energy_cues = ["free fuel", "free electricity", "water fuel", "water running car", "perpetual motion", "water to petrol", "free energy generator"]
        if any(f in combined for f in free_energy_cues):
            anomalies.append({
                "dimension": "PSEUDOSCIENCE_PHYSICAL_ANOMALY",
                "severity": "CRITICAL",
                "claimed": "Free Energy / Perpetual Motion / Miracle Fuel Invention",
                "baseline": "First and Second Laws of Thermodynamics prohibit perpetual energy creation without fuel consumption.",
                "discrepancy": "Claim asserts a physically impossible zero-fuel or perpetual energy generation mechanism.",
                "penalty": 0.85
            })
            anomaly_score = max(anomaly_score, 0.88)

        # 8. Miracle Medical Cure & Unverified Pharmacology Anomaly
        miracle_cures = ["cure cancer in 24 hours", "miracle cure", "cures all diseases", "instant cure", "cure overnight"]
        if any(m in combined for m in miracle_cures):
            anomalies.append({
                "dimension": "MEDICAL_EFFICACY_ANOMALY",
                "severity": "CRITICAL",
                "claimed": "Overnight Miracle Disease Cure",
                "baseline": "Clinical pharmacovigilance requires verified CDSCO/ICMR/WHO randomized clinical trials.",
                "discrepancy": "Unverified medical claims claiming instantaneous cures violate scientific and regulatory standards.",
                "penalty": 0.80
            })
            anomaly_score = max(anomaly_score, 0.85)

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
        "ndtv", "indian express", "hindustan times", "economic times", "business standard",
        "mint", "live law", "eenadu", "sakshi", "bbc news", "ani", "pti", "dd news", "all india radio"
    ]

    UNVERIFIED_SOURCE_MARKERS = [
        "whatsapp", "telegram", "forward", "viral post", "social media", "unknown", "anonymous",
        "facebook post", "blog", "group forward", "tiktok", "instagram reel"
    ]

    VIRAL_PROPAGATION_PATTERNS = [
        r'\b(forward to all|share before deleted|share before midnight|viral alert|breaking dhamaka)\b',
        r'\b(secret exposed|hidden truth|leak exposed|panic|urgent warning|warning to public)\b',
        r'\b(forwarded as received|must forward|send to 10 friends|share in all groups|share maximum|don\'t ignore)\b',
        r'\b(ban tonight|withdrawing tonight|breaking alert|save your money immediately)\b'
    ]

    def analyze_context_and_propagation(self, source: str, author: str, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title} {text}".lower()
        src_lower = (source or "").strip().lower()
        author_lower = (author or "").strip().lower()

        # 1. Source Credibility Scoring (Pillar 5)
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

        # 2. Viral Propagation & Coercive Forwarding Cues (Pillar 4)
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

        # Composite propagation score for backward compatibility
        s_propagation_composite = round(0.40 * source_risk + 0.60 * virality_pressure_score, 4)

        return {
            "s_source": round(source_risk, 4),
            "s_propagation": round(virality_pressure_score, 4),
            "s_propagation_composite": s_propagation_composite,
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
            keyword_hits = 0
            for kw in record["keywords"]:
                # Use strict word boundary matching so "star" does not match "started" and "rbi" does not match "orbital"
                if re.search(r'\b' + re.escape(kw.lower()) + r'\b', combined):
                    keyword_hits += 1
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


class EntitySpecificityAnalyzer:
    """Analyzes the informational density, named entity attribution, and contextual verifiability of news claims.
    Distinguishes abstract generic assertions (e.g. 'an inventor invented an invention yesterday',
    'a person invented an invention') from verifiable claims anchored with named entities, research labs,
    or institutional citations.
    """
    GENERIC_SUBJECT_PATTERNS = [
        r'\b(an inventor|a person|someone|somebody|a scientist|an individual|a man|a woman|a guy)\b',
        r'\b(an invention|a discovery|something|a device|a gadget|a machine)\b'
    ]

    INSTITUTIONAL_ENTITY_MARKERS = [
        r'\b(isro|drdo|iit|iisc|aiims|csir|icmr|dst|barc|tifr|nasa|mit|stanford|oxford|cambridge|who|rbi|sebi|pib|bse|nse)\b',
        r'\b(dr\.|prof\.|professor|minister|ministry|director|spokesperson|chief justice|court|patent)\b'
    ]

    def analyze_specificity(self, title: str, text: str) -> Dict[str, Any]:
        combined = f"{title} {text}".strip()
        combined_lower = combined.lower()

        # 1. Count generic subject placeholders
        generic_hits = 0
        for pat in self.GENERIC_SUBJECT_PATTERNS:
            generic_hits += len(re.findall(pat, combined_lower))

        # 2. Count institutional or accredited named entities
        named_entity_hits = 0
        for pat in self.INSTITUTIONAL_ENTITY_MARKERS:
            named_entity_hits += len(re.findall(pat, combined_lower))

        # 3. Capitalized Proper Nouns (proxy for named entities in English)
        words = combined.split()
        capitalized_names = [
            w for w in words[1:] 
            if w.istitle() and not w.isupper() and w.lower() not in {"an", "the", "in", "on", "at", "to", "for", "of", "and", "a", "yesterday", "today", "tomorrow"}
        ]

        # Classification into specificity tiers
        if named_entity_hits >= 1 or len(capitalized_names) >= 2:
            tier = "HIGH_SPECIFICITY_VERIFIABLE"
            xai_note = "Entity Specificity: High named entity attribution (verifiable institutional anchors or named individuals detected)."
            vagueness_penalty = 0.0
        elif generic_hits >= 2 or (generic_hits >= 1 and len(capitalized_names) == 0):
            tier = "ABSTRACT_GENERIC_ASSERTION"
            xai_note = "Entity Specificity: Abstract uncorroborated claim lacking named entity attribution, research institution, or verifiable patent/journal citation."
            vagueness_penalty = 0.10
        else:
            tier = "STANDARD_EDITORIAL_SPECIFICITY"
            xai_note = "Entity Specificity: Standard narrative content with typical situational framing."
            vagueness_penalty = 0.0

        return {
            "specificity_tier": tier,
            "generic_subject_hits": generic_hits,
            "named_entity_hits": named_entity_hits,
            "capitalized_names_count": len(capitalized_names),
            "vagueness_penalty": vagueness_penalty,
            "xai_specificity_note": xai_note
        }


class AdvancedJustificationMetricsEngine:
    """Computes transparent mathematical metrics to justify fake/real classification:
    1. Headline-Body Stance Discrepancy Index (HSDI): Stance divergence & clickbait exaggeration
    2. Shannon Lexical Entropy (H(X)): Information density in bits vs. repetitive spam
    3. Type-Token Ratio (TTR): Lexical diversity (journalistic prose vs. keyword stuffing)
    4. Emotional Panic & Polarization Index (EPPI): Density of existential panic/fear markers
    5. Claim Criticality Index (CCI): Intrinsic societal/safety impact severity
    6. Entity Attribution Depth (EAD): Proportion of grounded named entities vs. vague placeholders
    """
    CRITICAL_SEVERITY_KEYWORDS = [
        "war", "nuclear", "assassination", "killed", "dead", "casualty", "attack",
        "terror", "lockdown", "curfew", "emergency", "demonetization", "ban",
        "bank run", "collapse", "pandemic", "poison", "leak", "riot", "shootout"
    ]

    PANIC_EMOTIONAL_PATTERNS = [
        r'\b(panic|terrified|danger|horrific|flee|run for your life|catastrophe|devastating)\b',
        r'\b(deadly|poisonous|massive destruction|bloodbath|shocking disaster|doomsday)\b',
        r'\b(save your children|withdraw all money|emergency alert|do not drink|do not eat)\b'
    ]

    CLICKBAIT_STANCE_EXAGGERATIONS = [
        r'\b(banned|cancelled|terminated|shut down|arrested|executed|resigned|declared)\b'
    ]

    STANCE_HEDGE_PATTERNS = [
        r'\b(may|might|could|possible|alleged|rumor|speculated|proposed|considering|unconfirmed)\b'
    ]

    def compute_metrics(self, title: str, text: str) -> Dict[str, Any]:
        title_lower = (title or "").lower()
        text_lower = (text or "").lower()
        combined = f"{title_lower} {text_lower}"

        # 1. Tokenization & Basic Counts
        words = re.findall(r'\b[a-zA-Z\u0900-\u097F\u0C00-\u0C7F0-9_]+\b', combined)
        total_tokens = max(len(words), 1)
        unique_tokens = len(set(words))

        # 2. Type-Token Ratio (TTR) - Lexical Diversity
        ttr = round(unique_tokens / total_tokens, 4)

        # 3. Shannon Lexical Entropy H(X) in bits
        token_counts = {}
        for w in words:
            token_counts[w] = token_counts.get(w, 0) + 1
        entropy = 0.0
        for count in token_counts.values():
            p = count / total_tokens
            if p > 0:
                entropy -= p * math.log2(p)
        entropy = round(entropy, 3)

        # 4. Emotional Panic & Polarization Index (EPPI)
        panic_hits = 0
        for pat in self.PANIC_EMOTIONAL_PATTERNS:
            panic_hits += len(re.findall(pat, combined))
        eppi = min(1.0, round((panic_hits * 3.0) / max(total_tokens // 15, 1), 4))

        # 5. Claim Criticality Index (CCI)
        crit_hits = sum(1 for kw in self.CRITICAL_SEVERITY_KEYWORDS if re.search(r'\b' + re.escape(kw) + r'\b', combined))
        cci = min(1.0, round(crit_hits * 0.25, 3))

        # 6. Headline-Body Stance Discrepancy Index (HSDI)
        headline_exaggeration = any(re.search(pat, title_lower) for pat in self.CLICKBAIT_STANCE_EXAGGERATIONS)
        body_hedges = any(re.search(pat, text_lower) for pat in self.STANCE_HEDGE_PATTERNS)

        title_words = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', title_lower))
        text_words = set(re.findall(r'\b[a-zA-Z0-9]{3,}\b', text_lower))
        if title_words:
            overlap = len(title_words.intersection(text_words)) / len(title_words)
        else:
            overlap = 1.0

        if headline_exaggeration and body_hedges:
            hsdi = 0.85
        elif overlap < 0.25 and len(title_words) >= 4:
            hsdi = 0.70
        elif overlap < 0.45:
            hsdi = 0.40
        else:
            hsdi = round(max(0.05, 1.0 - overlap), 3)

        # 7. Entity Attribution Depth (EAD)
        named_entities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', f"{title} {text}")
        common_stops = {"The", "A", "An", "In", "On", "At", "To", "For", "Of", "And", "Today", "Yesterday"}
        filtered_ne = [e for e in named_entities if e not in common_stops]
        ead = min(1.0, round(len(filtered_ne) / max(total_tokens // 25, 2), 3))

        justification_notes = []
        if hsdi >= 0.70:
            justification_notes.append("Headline-Body Stance Discrepancy: Headline makes categorical assertions hedged or contradicted in body text.")
        if eppi >= 0.50:
            justification_notes.append("High Emotional Panic Index: Elevated frequency of alarmist, existential threat terminology.")
        if ttr < 0.38 and total_tokens > 40:
            justification_notes.append("Low Lexical Diversity: Repetitive linguistic structure characteristic of automated or propagandistic copy.")
        if cci >= 0.60:
            justification_notes.append("High-Criticality Claim: Involves national security, public safety, or systemic financial stability.")

        return {
            "hsdi": hsdi,
            "shannon_entropy_bits": entropy,
            "type_token_ratio": ttr,
            "eppi": eppi,
            "claim_criticality_index": cci,
            "entity_attribution_depth": ead,
            "justification_notes": justification_notes
        }


class BreakingNewsCorroborationEngine:
    """Specialized Zero-Day Protocol for Breaking & Fast-Moving News:
    Cross-references breaking submissions in real time against the active corpus of
    live institutional wire stories (Reuters, PTI, ANI, BBC, PIB, The Hindu).
    Resolves the 'Fact-Check Latency Lag' by computing the Cross-Source Corroboration Index (CSCI).
    """
    BREAKING_CUE_PATTERNS = [
        r'\b(breaking news|just in|flash|developing story|developing|latest update|reports emerging)\b',
        r'\b(urgent update|breaking|live updates|just now|happening now|minutes ago)\b'
    ]

    def corroborate_breaking_story(
        self,
        title: str,
        text: str,
        news_collection: Any = None,
        claim_criticality: float = 0.25,
        max_wire_check: int = 150
    ) -> Dict[str, Any]:
        combined = f"{title} {text}".lower()

        # 1. Detect breaking cues
        breaking_hits = []
        for pat in self.BREAKING_CUE_PATTERNS:
            found = re.findall(pat, combined)
            if found:
                breaking_hits.extend(found)
        is_breaking = len(breaking_hits) > 0 or "breaking" in title.lower()

        # 2. Extract salient search entities / keywords (length >= 4)
        stopwords = {
            "that", "this", "from", "with", "have", "were", "been", "will", "would",
            "could", "should", "their", "there", "about", "which", "after", "before",
            "news", "breaking", "update", "today", "report", "reports", "says", "said"
        }
        tokens = [w for w in re.findall(r'\b[a-zA-Z0-9]{4,}\b', combined) if w not in stopwords]
        salient_keywords = list(dict.fromkeys(tokens))[:8]

        # 3. Cross-reference against active live wire news repository
        corroborating_articles = []
        distinct_publishers = set()

        if news_collection is not None and salient_keywords:
            try:
                cursor = news_collection.find({"status": "PUBLISHED"}).limit(max_wire_check)
                for article in cursor:
                    art_text = f"{article.get('title', '')} {article.get('text', '')}".lower()
                    matches = sum(1 for kw in salient_keywords if kw in art_text)
                    if matches >= 2:
                        corroborating_articles.append({
                            "title": article.get("title", ""),
                            "source": article.get("source", "Accredited Wire"),
                            "keyword_matches": matches
                        })
                        src_name = (article.get("source") or "").strip().lower()
                        if src_name:
                            distinct_publishers.add(src_name)
            except Exception as e:
                logger.debug("Breaking news wire corroboration query notice: %s", e)

        distinct_count = len(distinct_publishers)
        # CSCI: 3 or more independent accredited wires = 1.0 (Full corroboration)
        csci = min(1.0, round(distinct_count / 3.0, 3))
        criticality_gap = max(0.0, round(claim_criticality - csci, 3))

        # 4. Breaking Protocol Decision
        if is_breaking:
            if csci >= 0.65:
                protocol_verdict = "BREAKING_MULTI_SOURCE_CORROBORATED"
                guidance = "Corroborated by multiple independent accredited news wires in real time."
                developing_tag = "BREAKING_VERIFIED"
            elif claim_criticality >= 0.60 and csci == 0.0:
                protocol_verdict = "CRITICAL_BREAKING_UNSUBSTANTIATED"
                guidance = "High-criticality national/public safety assertion with ZERO accredited wire corroboration. High rumor probability."
                developing_tag = "CRITICAL_UNVERIFIED_RUMOR"
            else:
                protocol_verdict = "BREAKING_DEVELOPING_UNCONFIRMED"
                guidance = "Developing story undergoing real-time wire verification. Recommended for human editorial review."
                developing_tag = "DEVELOPING_STORY"
        else:
            protocol_verdict = "STANDARD_ARCHIVAL_ANALYSIS"
            guidance = "Standard news content evaluated against established historical and vector evidence."
            developing_tag = None

        return {
            "is_breaking": is_breaking,
            "breaking_protocol_verdict": protocol_verdict,
            "developing_tag": developing_tag,
            "cross_source_corroboration_index": csci,
            "criticality_gap": criticality_gap,
            "distinct_publishers_count": distinct_count,
            "distinct_publishers": list(distinct_publishers)[:5],
            "corroborating_articles_count": len(corroborating_articles),
            "breaking_cues_found": list(set(breaking_hits)),
            "salient_keywords_queried": salient_keywords[:6],
            "actionable_guidance": guidance,
            "top_corroborations": corroborating_articles[:3]
        }


# Global Singletons
quantitative_anomaly_engine = QuantitativeAnomalyEngine()
propagation_analyzer = ContextPropagationAnalyzer()
internal_evidence_engine = InternalEvidenceEngine()
entity_specificity_analyzer = EntitySpecificityAnalyzer()
justification_metrics_engine = AdvancedJustificationMetricsEngine()
breaking_corroboration_engine = BreakingNewsCorroborationEngine()
