import logging
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
        internal_evidence_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        s_style = style_result["s_style"]
        s_fact = retrieval_result["s_fact"]
        evidence_status = retrieval_result["verdict_status"]
        timeline_score = graph_result["temporal_consistency_score"]
        contradictions = graph_result.get("contradictions", [])

        # Default sub-scores if not passed
        quant_res = quant_result or {"has_anomaly": False, "s_quant_anomaly": 0.0, "anomalies": []}
        prop_res = propagation_result or {"s_propagation": 0.20, "source_verdict": "STANDARD_BROADCAST", "detected_propagation_cues": []}
        int_evid = internal_evidence_result or {"has_match": False, "s_internal_fact": 0.50}

        s_quant = quant_res.get("s_quant_anomaly", 0.0)
        s_prop = prop_res.get("s_propagation", 0.20)

        # Internal Evidence reconciliation
        xai_factors = []
        if int_evid.get("has_match") and int_evid.get("top_match"):
            top_m = int_evid["top_match"]
            s_fact = min(s_fact, top_m["fact_score"]) if top_m["truth_status"] == "VERIFIED_OFFICIAL" else max(s_fact, top_m["fact_score"])
            xai_factors.append(f"Internal Knowledge Base proof matched ({top_m['official_source']}): {top_m['summary'][:110]}...")

        if evidence_status == "EVIDENCE_MATCHED":
            w_fact = 0.50
            w_style = 0.25
            w_quant = 0.15
            w_prop = 0.10
            xai_factors.append("Official verification evidence matched in Qdrant vector space.")
        else:
            w_fact = 0.15
            w_style = 0.45
            w_quant = 0.25
            w_prop = 0.15
            xai_factors.append("Predictive synthesis guided by stylometric intention, quantitative knowledge base, and propagation markers.")

        # Quantitative Anomaly Escalation
        if quant_res.get("has_anomaly") and quant_res.get("anomalies"):
            top_anomaly = quant_res["anomalies"][0]
            xai_factors.append(f"Quantitative Anomaly [{top_anomaly['dimension']}]: {top_anomaly['discrepancy']}")
            s_quant = max(s_quant, 0.85)

        # Viral Propagation Escalation
        if prop_res.get("propagation_band") == "HIGH_COERCIVE_VIRALITY":
            xai_factors.append("High viral propagation pressure detected (coercive forwarding patterns).")
        elif prop_res.get("source_verdict") == "VERIFIED_INSTITUTIONAL_WIRE":
            xai_factors.append("Source verified as institutional wire (Reuters / Times of India / PIB / ISRO).")

        # Temporal Graph Adjustment
        if contradictions:
            s_fact = max(s_fact, 0.90)
            xai_factors.append(f"Temporal graph detected chronological contradiction: {contradictions[0]}")
        elif timeline_score < 0.50:
            s_fact = max(s_fact, 0.70)
            xai_factors.append("Chronological anomaly detected against verified timeline anchors.")

        # Multi-Aspect 5-Pillar Weighted Fusion
        fake_prob = float(w_style * s_style + w_fact * s_fact + w_quant * s_quant + w_prop * s_prop)
        fake_prob = round(min(max(fake_prob, 0.01), 0.99), 4)
        real_prob = round(1.0 - fake_prob, 4)

        # Risk band determination
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

        # Construct comprehensive Explainable AI (XAI) report
        xai_report = {
            "primary_verdict_factors": xai_factors,
            "stylistic_analysis": {
                "s_style": s_style,
                "framing_risk": style_result["xai_style_attribution"]["stylistic_framing_risk"],
                "sensational_cue_count": style_result["xai_style_attribution"]["sensational_cue_count"],
                "exclamation_density": style_result["xai_style_attribution"]["exclamation_density"],
                "all_caps_word_ratio": style_result["xai_style_attribution"]["all_caps_word_ratio"],
                "highlighted_html": style_result["xai_style_attribution"].get("highlighted_html", ""),
                "emotional_arousal_score": style_result["xai_style_attribution"].get("emotional_arousal_score", 0.5),
                "detected_cues": style_result["xai_style_attribution"].get("detected_cues", [])
            },
            "factual_retrieval_analysis": {
                "s_fact": s_fact,
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
                "s_propagation": s_prop,
                "source_verdict": prop_res.get("source_verdict", "STANDARD_BROADCAST"),
                "propagation_band": prop_res.get("propagation_band", "ORGANIC_EDITORIAL_FRAMING"),
                "detected_cues": prop_res.get("detected_propagation_cues", [])
            },
            "chronological_graph_analysis": {
                "temporal_score": timeline_score,
                "timeline_verdict": graph_result.get("timeline_verdict"),
                "detected_contradictions": contradictions,
                "graph_backend": graph_result.get("graph_backend")
            },
            "regional_linguistics": {
                "detected_language": regional_info.get("primary_language"),
                "hinglish_markers": regional_info.get("hinglish_cues_found", [])
            }
        }

        return {
            "prediction": prediction,
            "fake_probability": fake_prob,
            "real_probability": real_prob,
            "risk_band": risk_band,
            "action_recommended": action_recommended,
            "s_style": s_style,
            "s_fact": s_fact,
            "s_quant": s_quant,
            "s_propagation": s_prop,
            "temporal_consistency": timeline_score,
            "xai": xai_report
        }


# Global fusion layer singleton
fusion_layer = EnsembleFusionLayer()
