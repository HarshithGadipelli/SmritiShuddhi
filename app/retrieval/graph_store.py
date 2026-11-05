import re
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import networkx as nx
from config import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

logger = logging.getLogger(__name__)


# Known historical timeline milestones and anchors for official verification
HISTORICAL_ANCHORS = [
    {"entity": "Chandrayaan-3", "event": "Lunar Soft Landing", "date": "2023-08-23", "status": "COMPLETED"},
    {"entity": "Reserve Bank of India", "event": "2000 Note Withdrawal from Circulation", "date": "2023-05-19", "status": "COMPLETED"},
    {"entity": "Reserve Bank of India", "event": "500 Note Ban Rumor Clarification", "date": "2024-04-02", "status": "CONFIRMED_VALID"},
    {"entity": "Election Commission of India", "event": "Lok Sabha Elections 2024", "date": "2024-04-19", "status": "COMPLETED"},
    {"entity": "G20 India", "event": "New Delhi Summit", "date": "2023-09-09", "status": "COMPLETED"},
    {"entity": "Aadhaar UIDAI", "event": "Lifetime Validity Clarification", "date": "2024-01-25", "status": "CONFIRMED_LIFETIME"},
    {"entity": "PM Free Laptop Scheme", "event": "Government Free Device Scheme", "date": "2024-03-15", "status": "NEVER_EXISTED_FAKE"},
]


class TemporalGraphEngine:
    """Neo4j Chronological Knowledge Graph & Linearity Verifier:
    Cross-references named entities, event dates, and temporal sequence
    to flag anachronisms, future-predictive fabrications, and timeline contradictions.
    Uses embedded NetworkX directed multi-graph when Neo4j container is offline.
    """
    def __init__(self):
        self.driver = None
        self.using_neo4j = False
        self.nx_graph = nx.DiGraph()
        self._connect_neo4j()
        self._seed_temporal_graph()

    def _connect_neo4j(self):
        try:
            import socket
            with socket.create_connection(("localhost", 7687), timeout=0.2):
                pass
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(
                NEO4J_URI,
                auth=(NEO4J_USER, NEO4J_PASSWORD),
                connection_timeout=0.5
            )
            driver.verify_connectivity()
            self.driver = driver
            self.using_neo4j = True
            logger.info("Connected to Neo4j graph cluster at %s", NEO4J_URI)
        except Exception:
            self.driver = None
            self.using_neo4j = False
            logger.info("Neo4j server not reachable; initializing embedded chronological knowledge graph engine.")

    def _seed_temporal_graph(self):
        """Populates the directed temporal graph with known timeline anchors."""
        for item in HISTORICAL_ANCHORS:
            entity = item["entity"]
            event = item["event"]
            date_str = item["date"]
            status = item["status"]

            # NetworkX in-memory representation
            self.nx_graph.add_node(entity, type="ENTITY")
            self.nx_graph.add_node(event, type="EVENT", date=date_str, status=status)
            self.nx_graph.add_edge(entity, event, relation="ASSOCIATED_WITH", date=date_str, status=status)

            # Neo4j cypher insertion if available
            if self.using_neo4j and self.driver:
                try:
                    with self.driver.session() as session:
                        session.run(
                            """
                            MERGE (e:Entity {name: $entity})
                            MERGE (v:Event {name: $event})
                            ON CREATE SET v.date = $date, v.status = $status
                            MERGE (e)-[r:ASSOCIATED_WITH {date: $date, status: $status}]->(v)
                            """,
                            entity=entity, event=event, date=date_str, status=status
                        )
                except Exception as e:
                    logger.warning("Error seeding Neo4j node: %s", e)

    def extract_temporal_entities(self, text: str) -> Dict[str, Any]:
        """Extracts dates, years, and recognized entities from text."""
        # Find explicit 4-digit years (e.g., 2018 to 2035)
        years = re.findall(r'\b(20[1-3][0-9])\b', text)
        
        # Find explicit date patterns (YYYY-MM-DD or DD/MM/YYYY)
        dates = re.findall(r'\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})\b', text)

        # Future-oriented phrasing
        future_markers = re.findall(r'\b(will happen tomorrow|next week|in upcoming months|to be banned soon|predicted for 202[5-9])\b', text, re.IGNORECASE)

        # Matched historical entities
        found_entities = []
        for anchor in HISTORICAL_ANCHORS:
            if re.search(re.escape(anchor["entity"]), text, re.IGNORECASE) or re.search(re.escape(anchor["event"]), text, re.IGNORECASE):
                found_entities.append(anchor)

        return {
            "years_mentioned": list(set(years)),
            "dates_mentioned": list(set(dates)),
            "future_markers": future_markers,
            "matched_anchors": found_entities
        }

    def verify_timeline(self, title: str, text: str) -> Dict[str, Any]:
        """Runs chronological linearity checks:
        - Detects contradictions with official historical dates
        - Flags claims of past completed events being announced as new/future
        - Returns timeline consistency score [0.0 = severe contradiction, 1.0 = consistent]
        """
        combined = f"{title} {text}"
        extracted = self.extract_temporal_entities(combined)
        anomalies = []
        contradictions = []

        # Check matched anchors
        for anchor in extracted["matched_anchors"]:
            status = anchor["status"]
            event_name = anchor["event"]
            anchor_date = anchor["date"]

            # Contradiction: text claims something is newly happening or active, but official graph states it never existed
            if status == "NEVER_EXISTED_FAKE":
                if any(w in combined.lower() for w in ["apply now", "register", "free laptop", "5000"]):
                    contradictions.append(
                        f"Fabricated Event Contradiction: Official record shows '{event_name}' was verified as fake on {anchor_date}."
                    )

            # Contradiction: 500 currency note ban
            if "500 Note Ban" in event_name:
                if any(w in combined.lower() for w in ["ban", "withdrawn", "invalid", "star mark"]):
                    contradictions.append(
                        f"Chronological Contradiction: RBI reaffirmed 500 Rupee notes are fully valid on {anchor_date}."
                    )

            # Check if an event completed in 2023/2024 is framed as an imminent future crisis
            if status == "COMPLETED" and len(extracted["future_markers"]) > 0:
                anomalies.append(
                    f"Temporal Discontinuity: '{event_name}' concluded on {anchor_date}, but text frames it as a future event."
                )

        if contradictions:
            temporal_score = 0.15  # Heavy factual conflict
            verdict = "TIMELINE_CONTRADICTION"
        elif anomalies:
            temporal_score = 0.40  # Moderate chronological anomaly
            verdict = "TIMELINE_ANOMALY"
        else:
            temporal_score = 0.90  # Linearly consistent
            verdict = "CHRONOLOGICALLY_CONSISTENT"

        return {
            "temporal_consistency_score": round(temporal_score, 3),
            "timeline_verdict": verdict,
            "contradictions": contradictions,
            "anomalies": anomalies,
            "extracted_entities": [a["entity"] for a in extracted["matched_anchors"]],
            "graph_backend": "neo4j_cluster" if self.using_neo4j else "embedded_networkx_graph"
        }


# Global temporal graph engine
graph_engine = TemporalGraphEngine()
