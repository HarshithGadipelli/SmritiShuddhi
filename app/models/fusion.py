import logging
import numpy as np
from typing import Dict, Any, List, Optional
from config import FAKE_THRESHOLD_HIGH, FAKE_THRESHOLD_LOW

logger = logging.getLogger(__name__)


class EnsembleFusionLayer:
    """Multi-Aspect Decoupled Ensemble Fusion Layer:
    Combines:
    1. Content-Based / Stylistic Intention Parsing (DeBERTa-v3 + LoRA adapters: S_style)
    2. Dynamic Fact Retrieval (Qdrant HNSW vector space + Stored Internal Proof Archive: S_fact)
    3. Chronological Consistency (Neo4j Temporal Linearity: S_graph)
    4. Quantitative Time-Series Knowledge Base (Stocks, Gold, Weather, Currency Anomaly: S_quant)
    5. Context & Viral Propagation Dynamics (Source Credibility + Coercive Sharing: S_propagation)
    """
    def __init__(self, threshold_low: float = FAKE_THRESHOLD_LOW, threshold_high: float = FAKE_THRESHOLD_HIGH):
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high

    def fuse(
        self,
        style_result: Dict[str, Any],
        retrieval_result: Dict[str, Any],
        graph_result: Dict[str, Any],
        regional_info: Dict[str, Any],
        quant_result: Optional[Dict[str, Any]] = None,
        propagation_result: Optional[Dict[str, Any]] = None,
        internal_evidence_result: Optional[Dict[str, Any]] = None,
        specificity_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """5-Pillar Multi-Aspect Decoupled Ensemble Fusion:
        1. Content-Based: Stylometric Intention, Sensationalism & DeBERTa LoRA (s_content)
        2. Context-Based: Chronological Linearity & Knowledge Graph Consistency (s_context)
        3. Knowledge-Based / Fact-Check: Vector debunks + Internal archive + Time-series anomaly (s_knowledge)
        4. Propagation-Based: Virality pressure & coercive forwarding triggers (s_propagation)
        5. Source-Based: Publisher credibility & institutional wire verification (s_source)
        """
        spec_res = specificity_result or {
            "specificity_tier": "STANDARD_EDITORIAL_SPECIFICITY",
            "vagueness_penalty": 0.0,
            "xai_specificity_note": ""
        }
        # Pillar 1: Content-Based Stylometric Score
        s_content = float(style_result["s_style"])

        # Pillar 2: Context-Based Temporal & Chronological Linearity
        timeline_score = float(graph_result.get("temporal_consistency_score", 0.90))
        contradictions = graph_result.get("contradictions", [])
        timeline_anomalies = graph_result.get("anomalies", [])
        if contradictions:
            s_context = 0.92
        elif timeline_anomalies or timeline_score < 0.50:
            s_context = 0.70
        else:
            s_context = max(0.05, round(1.0 - timeline_score, 4))

        # Pillar 3: Knowledge-Based / Fact-Check Retrieval & Quantitative Baselines
        raw_s_fact = float(retrieval_result.get("s_fact", 0.50))
        evidence_status = retrieval_result.get("verdict_status", "NO_EVIDENCE")
        quant_res = quant_result or {"has_anomaly": False, "s_quant_anomaly": 0.0, "anomalies": []}
        int_evid = internal_evidence_result or {"has_match": False, "s_internal_fact": 0.50}

        s_quant = float(quant_res.get("s_quant_anomaly", 0.0))
        s_internal = float(int_evid.get("s_internal_fact", 0.50))

        # Reconcile Knowledge Base Evidence
        xai_factors = []
        if int_evid.get("has_match") and int_evid.get("top_match"):
            top_m = int_evid["top_match"]
            if top_m["truth_status"] == "VERIFIED_OFFICIAL":
                s_fact_base = min(raw_s_fact, s_internal)
            else:
                s_fact_base = max(raw_s_fact, s_internal)
            xai_factors.append(f"Internal Fact-Check archive matched ({top_m['official_source']}): {top_m['summary'][:110]}...")
        else:
            s_fact_base = raw_s_fact

        # Quantitative anomaly escalation
        if quant_res.get("has_anomaly") and quant_res.get("anomalies"):
            top_anomaly = quant_res["anomalies"][0]
            xai_factors.append(f"Quantitative Anomaly [{top_anomaly['dimension']}]: {top_anomaly['discrepancy']}")
            s_quant = max(s_quant, 0.88)

        s_knowledge = round(max(s_fact_base, s_quant), 4)

        # Pillar 4: Propagation-Based Virality Pressure & Coercive Hooks
        prop_res = propagation_result or {
            "s_propagation": 0.10, "s_source": 0.40,
            "source_verdict": "STANDARD_BROADCAST",
            "propagation_band": "ORGANIC_EDITORIAL_FRAMING",
            "detected_propagation_cues": []
        }
        s_propagation = float(prop_res.get("s_propagation", prop_res.get("virality_pressure_score", 0.10)))

        # Pillar 5: Source-Based Publisher Credibility
        s_source = float(prop_res.get("s_source", prop_res.get("source_risk", 0.40)))
        source_verdict = prop_res.get("source_verdict", "INDEPENDENT_CITIZEN_SUBMISSION")

        if prop_res.get("propagation_band") == "HIGH_COERCIVE_VIRALITY":
            xai_factors.append("High viral propagation pressure detected (coercive forwarding patterns).")
        if source_verdict == "VERIFIED_INSTITUTIONAL_WIRE":
            xai_factors.append("Source verified as institutional wire (Reuters / Times of India / PIB / ISRO).")
        elif source_verdict == "UNVERIFIED_VIRAL_CHANNEL":
            xai_factors.append("Source flagged as unverified viral channel / social messaging forward.")

        if contradictions:
            xai_factors.append(f"Chronological knowledge graph detected contradiction: {contradictions[0]}")
        elif s_context >= 0.60:
            xai_factors.append("Chronological anomaly detected against verified timeline anchors.")

        if evidence_status == "EVIDENCE_MATCHED":
            xai_factors.append("Official verification evidence matched in vector space.")

        # Entity Specificity & Attribution Factor
        if spec_res.get("xai_specificity_note"):
            xai_factors.append(spec_res["xai_specificity_note"])

        # Supplemental contextual proof factors if minimal hits
        if not int_evid.get("has_match") and not quant_res.get("has_anomaly") and evidence_status != "EVIDENCE_MATCHED":
            xai_factors.append("Knowledge Base Baseline: No factual contradictions against official registries; evaluated via zero-shot predictive synthesis.")

        if s_content >= 0.60:
            xai_factors.append(f"Stylistic Analysis: High emotional manipulation / urgency markers ({style_result['xai_style_attribution']['sensational_cue_count']} cues).")
        elif s_content <= 0.35:
            xai_factors.append("Stylistic Analysis: Objective and neutral journalistic tone without sensationalism.")

        # ---------------------------------------------------------------------
        # DYNAMIC 5-PILLAR WEIGHT DISTRIBUTION
        # ---------------------------------------------------------------------
        if evidence_status == "EVIDENCE_MATCHED" or int_evid.get("has_match"):
            # Evidence-Anchored Verification
            w_knowledge = 0.35
            w_content = 0.20
            w_source = 0.20
            w_context = 0.15
            w_propagation = 0.10
        else:
            # Predictive Zero-Shot Synthesis
            w_content = 0.30
            w_knowledge = 0.25
            w_source = 0.20
            w_propagation = 0.15
            w_context = 0.10

        # Multi-Aspect 5-Pillar Weighted Linear Combination
        raw_fake_prob = float(
            w_content * s_content +
            w_context * s_context +
            w_knowledge * s_knowledge +
            w_propagation * s_propagation +
            w_source * s_source +
            spec_res.get("vagueness_penalty", 0.0)
        )

        # Critical Safety Overrides & Escalations
        # If any single pillar exhibits extreme critical violation:
        if quant_res.get("has_anomaly") or (int_evid.get("has_match") and int_evid.get("top_match", {}).get("truth_status") == "VERIFIED_DEBUNK"):
            raw_fake_prob = max(raw_fake_prob, 0.88)
        elif contradictions:
            raw_fake_prob = max(raw_fake_prob, 0.85)
        elif source_verdict == "VERIFIED_INSTITUTIONAL_WIRE" and s_content < 0.30 and not quant_res.get("has_anomaly") and not contradictions:
            # Verified institutional news without sensationalism or contradictions is anchored authentic
            raw_fake_prob = min(raw_fake_prob, 0.08)

        fake_prob = round(float(np.clip(raw_fake_prob, 0.01, 0.99)), 4)
        real_prob = round(1.0 - fake_prob, 4)

        # 3-Tier Risk Band Determination
        if fake_prob >= self.threshold_high:
            risk_band = "HIGH_RISK_FAKE"
            prediction = "FAKE"
            action_recommended = "FLAG_FOR_ADMIN_REVIEW_OR_REVOCATION"
        elif fake_prob <= self.threshold_low:
            risk_band = "LOW_RISK_FACTUAL"
            prediction = "REAL"
            action_recommended = "ALLOW_AUTOMATIC_BROADCAST"
        else:
            risk_band = "MODERATE_RISK"
            prediction = "UNCERTAIN"
            action_recommended = "MONITOR_USER_FEEDBACK"

        # Construct comprehensive Explainable AI (XAI) report across all 5 aspects
        xai_report = {
            "primary_verdict_factors": xai_factors,
            "stylistic_analysis": {
                "s_style": s_content,
                "s_content": s_content,
                "framing_risk": style_result["xai_style_attribution"]["stylistic_framing_risk"],
                "sensational_cue_count": style_result["xai_style_attribution"]["sensational_cue_count"],
                "exclamation_density": style_result["xai_style_attribution"]["exclamation_density"],
                "all_caps_word_ratio": style_result["xai_style_attribution"]["all_caps_word_ratio"],
                "highlighted_html": style_result["xai_style_attribution"].get("highlighted_html", ""),
                "emotional_arousal_score": style_result["xai_style_attribution"].get("emotional_arousal_score", 0.5),
                "detected_cues": style_result["xai_style_attribution"].get("detected_cues", [])
            },
            "factual_retrieval_analysis": {
                "s_fact": s_knowledge,
                "evidence_status": evidence_status,
                "official_matches": retrieval_result.get("matches", [])
            },
            "quantitative_knowledge_base": {
                "s_quant": s_quant,
                "has_anomaly": quant_res.get("has_anomaly", False),
                "anomaly_severity": quant_res.get("anomaly_severity", "NONE"),
                "detected_anomalies": quant_res.get("anomalies", [])
            },
            "context_and_propagation": {
                "s_propagation": s_propagation,
                "s_source": s_source,
                "source_verdict": source_verdict,
                "propagation_band": prop_res.get("propagation_band", "ORGANIC_EDITORIAL_FRAMING"),
                "detected_cues": prop_res.get("detected_propagation_cues", [])
            },
            "chronological_graph_analysis": {
                "temporal_score": timeline_score,
                "s_context": s_context,
                "timeline_verdict": graph_result.get("timeline_verdict"),
                "detected_contradictions": contradictions,
                "graph_backend": graph_result.get("graph_backend")
            },
            "regional_linguistics": {
                "detected_language": regional_info.get("primary_language"),
                "hinglish_markers": regional_info.get("hinglish_cues_found", [])
            }
        }

        # Five-Pillar Explicit Breakdown for Explainability and UI
        five_pillar_breakdown = {
            "content_based": {
                "pillar_name": "Content-Based (Stylometry & Emotional Framing)",
                "risk_score": s_content,
                "weight": w_content,
                "status": "ELEVATED" if s_content >= 0.50 else "NORMAL",
                "cues_found": style_result["xai_style_attribution"]["sensational_cue_count"]
            },
            "context_based": {
                "pillar_name": "Context-Based (Chronological Linearity & Entities)",
                "risk_score": s_context,
                "weight": w_context,
                "status": "CONTRADICTION" if contradictions else ("ANOMALY" if s_context >= 0.50 else "CONSISTENT"),
                "temporal_score": timeline_score
            },
            "knowledge_based": {
                "pillar_name": "Knowledge & Fact-Check (Vector Debunks & Time-Series)",
                "risk_score": s_knowledge,
                "weight": w_knowledge,
                "status": "ANOMALY_OR_DEBUNK" if s_knowledge >= 0.70 else "VERIFIED_ACCURATE",
                "has_quant_anomaly": quant_res.get("has_anomaly", False)
            },
            "propagation_based": {
                "pillar_name": "Propagation-Based (Virality Pressure & Coercive Forwarding)",
                "risk_score": s_propagation,
                "weight": w_propagation,
                "status": prop_res.get("propagation_band", "ORGANIC_EDITORIAL_FRAMING"),
                "cues_found": len(prop_res.get("detected_propagation_cues", []))
            },
            "source_based": {
                "pillar_name": "Source-Based (Publisher Credibility & Verification)",
                "risk_score": s_source,
                "weight": w_source,
                "verdict": source_verdict,
                "status": "TRUSTED" if s_source <= 0.15 else ("UNVERIFIED" if s_source >= 0.70 else "STANDARD")
            }
        }

        return {
            "prediction": prediction,
            "fake_probability": fake_prob,
            "real_probability": real_prob,
            "risk_band": risk_band,
            "action_recommended": action_recommended,
            # 5-Pillar Dedicated Scores
            "s_content": s_content,
            "s_context": s_context,
            "s_knowledge": s_knowledge,
            "s_propagation": s_propagation,
            "s_source": s_source,
            # Backward-compatible aliases
            "s_style": s_content,
            "s_fact": s_knowledge,
            "s_quant": s_quant,
            "temporal_consistency": timeline_score,
            "five_pillar_breakdown": five_pillar_breakdown,
            "xai": xai_report
        }


# Global fusion layer singleton
fusion_layer = EnsembleFusionLayer()
