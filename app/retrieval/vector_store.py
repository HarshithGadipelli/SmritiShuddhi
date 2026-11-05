import os
import time
import logging
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from config import QDRANT_HOST, QDRANT_PORT, QDRANT_COLLECTION, QDRANT_STORAGE_DIR
from app.retrieval.encoder import regional_encoder

logger = logging.getLogger(__name__)

# Curated benchmark official truth and debunk records (PIB, IMD, RBI, ISRO, ECI)
INITIAL_OFFICIAL_CORPUS = [
    {
        "id": 1,
        "title": "PIB Fact Check: Free 5000 Rs Laptop Scheme Under Prime Minister Scheme is Fake",
        "text": "A viral message claiming the Government is providing free laptops and 5000 rupees to all students under PM Free Laptop Yojana is entirely fake. No such scheme has been launched by the Ministry of Education.",
        "source": "Press Information Bureau (PIB)",
        "source_type": "OFFICIAL_DEBUNK",
        "truth_label": 1,  # 1 = News claiming this is FAKE
        "category": "Government Schemes",
        "published_date": "2024-03-15"
    },
    {
        "id": 2,
        "title": "PIB Fact Check: RBI Withdrawing 500 Rupee Currency Notes is Fake",
        "text": "Rumors circulating on WhatsApp claiming RBI will withdraw 500 rupee banknotes or invalidate notes with Star symbol are false. All currency notes issued by the Reserve Bank remain legal tender.",
        "source": "Reserve Bank of India & PIB Fact Check",
        "source_type": "OFFICIAL_DEBUNK",
        "truth_label": 1,
        "category": "Economy & Banking",
        "published_date": "2024-04-02"
    },
    {
        "id": 3,
        "title": "IMD Weather Alert: Severe Heatwave Warning for Northern and Central India",
        "text": "India Meteorological Department (IMD) issues red alert for severe heatwave conditions over Delhi, Rajasthan, and Haryana with temperatures surpassing 45 degrees Celsius. Advisory issued to stay hydrated.",
        "source": "India Meteorological Department (IMD)",
        "source_type": "OFFICIAL_VERIFIED",
        "truth_label": 0,  # 0 = News reporting this is REAL
        "category": "Weather & Public Safety",
        "published_date": "2024-05-20"
    },
    {
        "id": 4,
        "title": "ISRO Official Press Release: Chandrayaan Data Archive Released on ISSDC",
        "text": "Indian Space Research Organisation (ISRO) releases scientific payload data from Chandrayaan missions on the Indian Space Science Data Centre (ISSDC) portal for global research community.",
        "source": "Indian Space Research Organisation (ISRO)",
        "source_type": "OFFICIAL_VERIFIED",
        "truth_label": 0,
        "category": "Science & Space",
        "published_date": "2024-06-10"
    },
    {
        "id": 5,
        "title": "Election Commission of India: Voting Rights Cannot be Withdrawn via WhatsApp Link",
        "text": "ECI cautions citizens against fraudulent SMS links claiming deletion of names from electoral roll. Any voter deletion requires official Form 7 submission and hearing before ERO.",
        "source": "Election Commission of India (ECI)",
        "source_type": "OFFICIAL_DEBUNK",
        "truth_label": 1,
        "category": "Elections & Governance",
        "published_date": "2024-04-18"
    },
    {
        "id": 6,
        "title": "Ministry of Railways: Tatkal Ticket Booking Rules Clarification",
        "text": "Indian Railways clarifies that IRCTC Tatkal booking rules have not changed. Rumors about mandatory 48-hour advance agent-only booking are baseless. Standard official booking windows remain active.",
        "source": "Ministry of Railways",
        "source_type": "OFFICIAL_VERIFIED",
        "truth_label": 0,
        "category": "Transport & Railways",
        "published_date": "2024-02-12"
    },
    {
        "id": 7,
        "title": "UIDAI Notification: Aadhaar Card Never Expires, Biometric Updates Free for Children",
        "text": "Unique Identification Authority of India clarifies that Aadhaar numbers have lifetime validity. Rumors claiming expiry after 10 years are false. Mandatory biometric updates at ages 5 and 15 remain free.",
        "source": "UIDAI Official",
        "source_type": "OFFICIAL_DEBUNK",
        "truth_label": 1,
        "category": "Identity & Governance",
        "published_date": "2024-01-25"
    }
]


import socket

def _probe_port(host: str, port: int, timeout: float = 0.3) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False

class QdrantVectorStore:
    """High-Speed Qdrant KNN Vector Database for Real-Time Evidence Retrieval:
    - Indexes verified truth vectors from official Indian organizations (PIB, IMD, RBI, ISRO, ECI)
    - Sub-15ms HNSW vector lookups
    - Supports remote Qdrant container and zero-setup embedded local storage
    """
    def __init__(self, collection_name: str = QDRANT_COLLECTION):
        self.collection_name = collection_name
        self.client = self._init_client()
        self._setup_collection()
        self._seed_official_corpus()

    def _init_client(self) -> QdrantClient:
        # 1. Fast probe connection to remote Qdrant service
        if _probe_port(QDRANT_HOST, QDRANT_PORT, timeout=0.2):
            try:
                client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, timeout=0.8, check_compatibility=False)
                client.get_collections()
                logger.info("Connected to remote Qdrant server at %s:%s", QDRANT_HOST, QDRANT_PORT)
                return client
            except Exception:
                pass

        # 2. Fast, zero-lock local in-memory Qdrant instance
        logger.info("Remote Qdrant not available; initializing local in-memory Qdrant engine.")
        return QdrantClient(":memory:")

    def _setup_collection(self):
        try:
            collections = [c.name for c in self.client.get_collections().collections]
            if self.collection_name not in collections:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=qmodels.VectorParams(
                        size=regional_encoder.vector_dim,
                        distance=qmodels.Distance.COSINE
                    )
                )
                logger.info("Created Qdrant collection: %s", self.collection_name)
        except Exception as e:
            logger.warning("Error configuring Qdrant collection: %s", e)

    def _seed_official_corpus(self):
        try:
            count = self.client.count(collection_name=self.collection_name).count
            if count == 0:
                points = []
                for item in INITIAL_OFFICIAL_CORPUS:
                    content_to_embed = f"{item['title']} {item['text']}"
                    vec = regional_encoder.encode(content_to_embed).tolist()
                    points.append(
                        qmodels.PointStruct(
                            id=item["id"],
                            vector=vec,
                            payload=item
                        )
                    )
                self.client.upsert(collection_name=self.collection_name, points=points)
                logger.info("Successfully seeded %d official Indian truth vectors into Qdrant", len(points))
        except Exception as e:
            logger.warning("Error seeding official corpus into Qdrant: %s", e)

    def search_evidence(self, query_text: str, top_k: int = 3, score_threshold: float = 0.30) -> Dict[str, Any]:
        """Runs sub-15ms KNN vector space search against official Indian evidence.
        Returns:
          - S_fact: Factual fake score [0.0 = Verified True, 1.0 = Verified Fake, 0.5 = Neutral/No Evidence]
          - Evidence list with match score, source, and payload
          - Retrieval latency in ms
        """
        start = time.perf_counter()
        query_vec = regional_encoder.encode(query_text).tolist()

        try:
            # Use query_points or search depending on qdrant-client version
            if hasattr(self.client, 'query_points'):
                results = self.client.query_points(
                    collection_name=self.collection_name,
                    query=query_vec,
                    limit=top_k,
                    score_threshold=score_threshold
                ).points
            else:
                results = self.client.search(
                    collection_name=self.collection_name,
                    query_vector=query_vec,
                    limit=top_k,
                    score_threshold=score_threshold
                )
        except Exception as e:
            logger.warning("Qdrant search error: %s", e)
            results = []

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        evidence_items = []
        fact_scores = []

        for r in results:
            payload = r.payload or {}
            score = float(r.score)
            source_type = payload.get("source_type", "OFFICIAL_VERIFIED")
            truth_label = payload.get("truth_label", 0)

            # If the official corpus is a DEBUNK (e.g. PIB says claim is false),
            # matching this debunk strongly implies the queried text is FAKE (score -> 1.0)
            if source_type == "OFFICIAL_DEBUNK" or truth_label == 1:
                inferred_fake_risk = min(0.95, 0.50 + (score * 0.50))
            else:
                # Official verified reality means the queried text is REAL (score -> 0.05)
                inferred_fake_risk = max(0.05, 0.50 - (score * 0.50))

            fact_scores.append(inferred_fake_risk)
            evidence_items.append({
                "source": payload.get("source"),
                "title": payload.get("title"),
                "snippet": payload.get("text", "")[:180] + "...",
                "source_type": source_type,
                "similarity_score": round(score, 4),
                "category": payload.get("category", "General"),
                "published_date": payload.get("published_date")
            })

        if fact_scores:
            s_fact = sum(fact_scores) / len(fact_scores)
            verdict_status = "EVIDENCE_MATCHED"
        else:
            s_fact = 0.50
            verdict_status = "NO_OFFICIAL_CORPUS_MATCH"

        return {
            "s_fact": round(s_fact, 4),
            "verdict_status": verdict_status,
            "evidence_count": len(evidence_items),
            "matches": evidence_items,
            "retrieval_latency_ms": round(elapsed_ms, 3),
            "sub_15ms_compliant": elapsed_ms < 15.0
        }

    def add_evidence_document(self, doc_id: int, title: str, text: str, source: str, source_type: str, truth_label: int, category: str = "Official"):
        """Dynamically indexes newly verified press releases or debunk bulletins."""
        combined = f"{title} {text}"
        vec = regional_encoder.encode(combined).tolist()
        point = qmodels.PointStruct(
            id=doc_id,
            vector=vec,
            payload={
                "id": doc_id,
                "title": title,
                "text": text,
                "source": source,
                "source_type": source_type,
                "truth_label": truth_label,
                "category": category,
                "published_date": time.strftime("%Y-%m-%d")
            }
        )
        self.client.upsert(collection_name=self.collection_name, points=[point])


# Global vector store singleton
vector_store = QdrantVectorStore()
