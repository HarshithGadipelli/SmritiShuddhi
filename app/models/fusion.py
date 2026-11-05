import logging
from typing import Dict, Any, List
from config import FAKE_THRESHOLD_HIGH, FAKE_THRESHOLD_LOW

logger = logging.getLogger(__name__)


class EnsembleFusionLayer:
    """Decoupled Ensemble Fusion Layer:
    Combines Track A (Stylistic Intention Parsing: S_style) with
    Track B (Dynamic Fact Cross-Referencing: S_fact + Temporal Graph Linearity)
    to generate final Real/Fake verdict, risk bands, and Explainable AI (XAI) rationale.
    """
    def __init__(self, threshold_low: float = FAKE_THRESHOLD_LOW, threshold_high: float = FAKE_THRESHOLD_HIGH):
        self.threshold_low = threshold_low
        self.threshold_high = threshold_high

    def fuse(
        self,
        style_result: Dict[str, Any],
        retrieval_result: Dict[str, Any],
        graph_result: Dict[str, Any],
        regional_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        s_style = style_result["s_style"]
        s_fact = retrieval_result["s_fact"]
        evidence_status = retrieval_result["verdict_status"]
        timeline_score = graph_result["temporal_consistency_score"]
        contradictions = graph_result.get("contradictions", [])

        # Decoupled dynamic weighting logic
        xai_factors = []
        if evidence_status == "EVIDENCE_MATCHED":
            # Official Indian sources (PIB, IMD, RBI) are prioritized
            w_fact = 0.70
            w_style = 0.30
            xai_factors.append("Official verification evidence matched in Qdrant vector space.")
        else:
            # When no official bulletin matches, stylistic intention is primary
            w_fact = 0.15
            w_style = 0.85
            xai_factors.append("No direct official bulletin found; prediction guided by stylistic intention analysis.")

        # Temporal Graph Adjustment
        if contradictions:
            # Timeline contradiction found by Neo4j graph engine
            s_fact = max(s_fact, 0.90)
            xai_factors.append(f"Temporal graph detected chronological contradiction: {contradictions[0]}")
        elif timeline_score < 0.50:
            s_fact = max(s_fact, 0.70)
            xai_factors.append("Chronological anomaly detected against verified timeline anchors.")

        # Combined fake probability
        fake_prob = float(w_style * s_style + w_fact * s_fact)
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
            "temporal_consistency": timeline_score,
            "xai": xai_report
        }


# Global fusion layer singleton
fusion_layer = EnsembleFusionLayer()
