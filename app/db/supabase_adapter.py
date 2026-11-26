"""
SMRITI SHUDDHI - SUPABASE POSTGRESQL & PGVECTOR ADAPTER
=========================================================
Pure-Python, enterprise-grade adapter for Supabase PostgreSQL using pg8000.
Fully compatible with Windows Application Control policies (zero C-extensions).
Supports:
- MongoDB-compatible collection operations (find_one, find, insert_one, update_one, delete_one, count_documents)
- Native JSONB serialization for multi-aspect XAI verdicts
- Native 384-dimensional vector HNSW cosine similarity search
- Advanced MongoDB-to-SQL query translation ($or, $in, $regex, $ne)
- Thread-safe connection handling per worker thread
- Fast SQL pushdown for sort and limit operations
- Auto-schema deployment & initial dataset seeding on startup
"""

import os
import ssl
import json
import uuid
import logging
import threading
from datetime import datetime, date, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse, unquote

logger = logging.getLogger("SupabaseAdapter")

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Whitelist known table columns to ignore unexpected MongoDB-only attributes
KNOWN_COLUMNS = {
    "news": {
        "news_id", "sample_id", "title", "text", "category", "source", "region",
        "language", "author", "image_url", "url", "reading_time", "status", "real_probability",
        "fake_probability", "s_style", "s_fact", "s_quant", "s_prop", "s_propagation",
        "temporal_consistency", "xai", "created_at", "updated_at", "is_user_submission",
        "tag", "tag_display", "risk_band", "action_recommended", "unlearned_strategy",
        "unlearned_at", "residual_influence_pct", "retain_accuracy_pct", "parameters_modified_pct",
        "view_count", "share_count", "flag_count", "bookmark_count", "first_seen_at", "last_interacted_at"
    },
    "official_truth_vectors": {
        "id", "evidence_id", "news_id", "title", "text", "source", "source_type",
        "truth_label", "category", "embedding", "created_at"
    },
    "unlearning_ledger": {
        "job_id", "sample_id", "news_id", "title", "strategy", "residual_influence",
        "residual_influence_pct", "retain_accuracy_pct", "results", "execution_time_ms",
        "proof_hash", "status", "timestamp", "created_at"
    },
    "removal_requests": {
        "request_id", "news_id", "sample_id", "title", "reason", "details",
        "requested_by", "requester_name", "requester_email", "status", "created_at",
        "unlearned_at", "unlearned_strategy", "rejected_at"
    },
    "training_samples": {
        "sample_id", "news_id", "shard_id", "slice_id", "title", "text",
        "label", "status", "created_at"
    },
    "users": {
        "user_id", "email", "password", "name", "role", "title", "created_at"
    },
    "audit_logs": {
        "log_id", "action", "details", "client_ip", "sample_id", "news_id", "strategy", "created_at"
    },
    "quantitative_knowledge_base": {
        "metric_id", "category", "metric_name", "symbol", "unit", "baseline_value",
        "min_realistic", "max_realistic", "daily_swing_limit_pct", "extreme_anomaly_pct",
        "rule_summary", "last_updated"
    },
    "app_settings": {
        "setting_key", "setting_value", "updated_by", "updated_at"
    }
}


class SupabaseCursor:
    """Lazy cursor supporting chained sort() and limit() pushed down to PostgreSQL."""
    def __init__(self, collection: 'SupabaseCollection', query: Dict[str, Any] = None):
        self.collection = collection
        self.query = query or {}
        self._sort_col = None
        self._sort_dir = "ASC"
        self._limit = None
        self._cached_results = None

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list) and len(key_or_list) > 0:
            key, direction = key_or_list[0]
        else:
            key = key_or_list
        self._sort_col = "news_id" if (key == "_id" and self.collection.table_name == "news") else key
        self._sort_dir = "DESC" if (direction == -1 or direction == "descending") else "ASC"
        self._cached_results = None
        return self

    def limit(self, n: int):
        self._limit = n
        self._cached_results = None
        return self

    def _fetch(self) -> List[Dict[str, Any]]:
        if self._cached_results is not None:
            return self._cached_results

        params = {}
        where_sql = self.collection._build_where(self.query, params)
        order_sql = f"ORDER BY {self._sort_col} {self._sort_dir}" if self._sort_col else ""
        limit_sql = f"LIMIT {int(self._limit)}" if self._limit is not None else ""

        sql = f"SELECT * FROM {self.collection.table_name} {where_sql} {order_sql} {limit_sql};"
        self._cached_results = self.collection._execute(sql, params, fetch_all=True) or []
        return self._cached_results

    def __iter__(self):
        return iter(self._fetch())

    def __len__(self):
        return len(self._fetch())

    def to_list(self, length: Optional[int] = None):
        res = self._fetch()
        return res[:length] if length is not None else res


class SupabaseCollection:
    """PostgreSQL Table wrapper matching Mongo collection interface."""
    def __init__(self, table_name: str, db_ref: 'SupabaseDB'):
        self.table_name = table_name
        self.db = db_ref
        self.valid_cols = KNOWN_COLUMNS.get(table_name)

    def _parse_condition(self, col_name: str, val: Any, params: dict, counter: list) -> str:
        col = "news_id" if (col_name == "_id" and self.table_name == "news") else col_name
        if self.valid_cols and col not in self.valid_cols:
            return "FALSE"

        if isinstance(val, dict):
            conds = []
            if "$in" in val:
                in_params = []
                for item in val["$in"]:
                    p_name = f"{col}_{counter[0]}"
                    counter[0] += 1
                    params[p_name] = item
                    in_params.append(f":{p_name}")
                if in_params:
                    conds.append(f"{col} IN ({', '.join(in_params)})")
                else:
                    conds.append("FALSE")
            if "$regex" in val:
                p_name = f"{col}_{counter[0]}"
                counter[0] += 1
                pattern = val["$regex"]
                params[p_name] = pattern
                conds.append(f"{col} ~* :{p_name}")
            if "$ne" in val:
                p_name = f"{col}_{counter[0]}"
                counter[0] += 1
                params[p_name] = val["$ne"]
                conds.append(f"{col} != :{p_name}")
            return " AND ".join(conds) if conds else "TRUE"
        else:
            p_name = f"{col}_{counter[0]}"
            counter[0] += 1
            params[p_name] = val
            return f"{col} = :{p_name}"

    def _build_where(self, query: Dict[str, Any], params: dict) -> str:
        if not query:
            return ""
        counter = [len(params)]
        clauses = []
        if "$or" in query:
            or_conds = []
            for subq in query["$or"]:
                sub_clauses = []
                for sk, sv in subq.items():
                    c = self._parse_condition(sk, sv, params, counter)
                    if c != "FALSE":
                        sub_clauses.append(c)
                if sub_clauses:
                    or_conds.append("(" + " AND ".join(sub_clauses) + ")")
            if or_conds:
                clauses.append("(" + " OR ".join(or_conds) + ")")

        for k, v in query.items():
            if k == "$or":
                continue
            c = self._parse_condition(k, v, params, counter)
            if c != "FALSE":
                clauses.append(c)

        return ("WHERE " + " AND ".join(clauses)) if clauses else ""

    def _execute(self, sql: str, params: dict = None, fetch_one: bool = False, fetch_all: bool = False):
        params = params or {}
        for attempt in range(2):
            try:
                conn = self.db.get_connection()
                raw_rows = conn.run(sql, **params)
                if not raw_rows:
                    return None if fetch_one else []
                col_names = [col["name"] for col in conn.columns] if conn.columns else []
                rows = []
                for row in raw_rows:
                    d = dict(zip(col_names, row))
                    for k, v in d.items():
                        if isinstance(v, (datetime, date)):
                            d[k] = v.isoformat()
                    if "xai" in d and isinstance(d["xai"], str):
                        try:
                            d["xai"] = json.loads(d["xai"])
                        except Exception:
                            pass
                    rows.append(d)
                if fetch_one:
                    return rows[0] if rows else None
                return rows
            except Exception as e:
                logger.warning("Supabase SQL notice on %s (attempt %d): %s", self.table_name, attempt + 1, e)
                self.db.invalidate_current_connection()
                if attempt == 1:
                    return None if fetch_one else []

    def insert_one(self, doc: Dict[str, Any]):
        doc_copy = dict(doc)
        if "_id" in doc_copy and "news_id" not in doc_copy and self.table_name == "news":
            doc_copy["news_id"] = str(doc_copy["_id"])

        # Auto-generate missing primary keys
        if self.table_name == "news" and "news_id" not in doc_copy:
            doc_copy["news_id"] = f"NEWS_{uuid.uuid4().hex[:8].upper()}"
        elif self.table_name == "unlearning_ledger" and "job_id" not in doc_copy:
            doc_copy["job_id"] = f"JOB_{uuid.uuid4().hex[:8].upper()}"
        elif self.table_name == "users" and "user_id" not in doc_copy:
            doc_copy["user_id"] = f"USR_{uuid.uuid4().hex[:8].upper()}"
        elif self.table_name == "removal_requests" and "request_id" not in doc_copy:
            doc_copy["request_id"] = f"REQ_REM_{uuid.uuid4().hex[:8].upper()}"

        # If table uses serial/auto-increment integer primary key, omit string ids
        if self.table_name in ("audit_logs", "official_truth_vectors"):
            for serial_pk in ("log_id", "id"):
                if serial_pk in doc_copy and not isinstance(doc_copy[serial_pk], int):
                    doc_copy.pop(serial_pk, None)

        processed = {}
        for k, v in doc_copy.items():
            if k == "_id":
                continue
            if self.valid_cols and k not in self.valid_cols:
                continue
            if isinstance(v, (dict, list)):
                processed[k] = json.dumps(v)
            elif isinstance(v, (datetime, date)):
                processed[k] = v.isoformat()
            else:
                processed[k] = v

        if not processed:
            class EmptyResult:
                inserted_id = None
            return EmptyResult()

        keys = list(processed.keys())
        cols = ", ".join(keys)
        placeholders = ", ".join([f":{k}" for k in keys])

        sql = f"""
            INSERT INTO {self.table_name} ({cols}) 
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING;
        """
        self._execute(sql, processed)

        class InsertResult:
            inserted_id = doc_copy.get("news_id") or doc_copy.get("sample_id") or doc_copy.get("request_id") or doc_copy.get("job_id") or doc_copy.get("user_id") or doc_copy.get("_id")
        return InsertResult()

    def find_one(self, query: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        query = query or {}
        params = {}
        where_sql = self._build_where(query, params)
        sql = f"SELECT * FROM {self.table_name} {where_sql} LIMIT 1;"
        return self._execute(sql, params, fetch_one=True)

    def find(self, query: Dict[str, Any] = None) -> SupabaseCursor:
        return SupabaseCursor(self, query)

    def count_documents(self, query: Dict[str, Any] = None) -> int:
        query = query or {}
        params = {}
        where_sql = self._build_where(query, params)
        sql = f"SELECT COUNT(*) AS c FROM {self.table_name} {where_sql};"
        res = self._execute(sql, params, fetch_one=True)
        return int(res["c"]) if res and "c" in res else 0

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any], upsert: bool = True, *args, **kwargs):
        existing = self.find_one(query)
        set_vals = update.get("$set", update)

        if not existing and upsert:
            merged = dict(query)
            merged.update(set_vals)
            return self.insert_one(merged)

        set_clauses = []
        params = {}
        for idx, (k, v) in enumerate(set_vals.items()):
            if self.valid_cols and k not in self.valid_cols:
                continue
            param_name = f"s_{idx}"
            set_clauses.append(f"{k} = :{param_name}")
            if isinstance(v, (dict, list)):
                params[param_name] = json.dumps(v)
            elif isinstance(v, (datetime, date)):
                params[param_name] = v.isoformat()
            else:
                params[param_name] = v

        where_sql = self._build_where(query, params)
        if not set_clauses or not where_sql:
            return True

        sql = f"""
            UPDATE {self.table_name} 
            SET {", ".join(set_clauses)}
            {where_sql};
        """
        self._execute(sql, params)
        return True

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any], *args, **kwargs):
        return self.update_one(query, update, *args, **kwargs)

    def delete_one(self, query: Dict[str, Any]):
        params = {}
        where_sql = self._build_where(query, params)
        if not where_sql:
            return False

        sql = f"DELETE FROM {self.table_name} {where_sql};"
        self._execute(sql, params)
        return True

    def delete_many(self, query: Dict[str, Any]):
        return self.delete_one(query)

    def create_index(self, *args, **kwargs):
        pass


class SupabaseDB:
    """Manages pure-Python PostgreSQL connections (thread-safe) and schema migration."""
    def __init__(self, uri: str):
        self.uri = uri
        self._local = threading.local()
        # Verify initial connectivity and apply schema
        startup_conn = self._create_raw_connection()
        try:
            self._initialize_schema(startup_conn)
            self._seed_initial_data(startup_conn)
        finally:
            try:
                startup_conn.close()
            except Exception:
                pass

    def _create_raw_connection(self):
        import pg8000.native
        cleaned_uri = self.uri
        if ":[" in cleaned_uri and "]@" in cleaned_uri:
            p1 = cleaned_uri.find(":[")
            p2 = cleaned_uri.find("]@", p1)
            cleaned_uri = cleaned_uri[:p1+1] + cleaned_uri[p1+2:p2] + cleaned_uri[p2+1:]

        p = urlparse(cleaned_uri)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        return pg8000.native.Connection(
            user=unquote(p.username or "postgres"),
            password=unquote(p.password or ""),
            host=p.hostname,
            port=p.port or 5432,
            database=p.path.lstrip("/") or "postgres",
            ssl_context=ctx,
            timeout=12
        )

    def get_connection(self):
        """Returns thread-local connection, reconnecting automatically if disconnected."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.run("SELECT 1;")
                return conn
            except Exception:
                self.invalidate_current_connection()

        conn = self._create_raw_connection()
        self._local.conn = conn
        return conn

    def invalidate_current_connection(self):
        """Safely closes and removes the thread-local connection."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
            self._local.conn = None

    def _initialize_schema(self, conn):
        schema_file = BASE_DIR / "supabase_schema.sql"
        if schema_file.exists():
            try:
                sql = schema_file.read_text(encoding="utf-8")
                statements = [s.strip() for s in sql.split(";") if s.strip()]
                for stmt in statements:
                    try:
                        conn.run(stmt + ";")
                    except Exception:
                        pass
                # Ensure additive propagation columns exist on pre-existing Supabase news tables
                alter_stmts = [
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS url TEXT;",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS view_count INT DEFAULT 0;",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS share_count INT DEFAULT 0;",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS flag_count INT DEFAULT 0;",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS bookmark_count INT DEFAULT 0;",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS first_seen_at TIMESTAMPTZ DEFAULT NOW();",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS last_interacted_at TIMESTAMPTZ DEFAULT NOW();",
                    "ALTER TABLE news ADD COLUMN IF NOT EXISTS s_propagation FLOAT DEFAULT 0.10;",
                ]
                for astmt in alter_stmts:
                    try:
                        conn.run(astmt)
                    except Exception:
                        pass
                logger.info("Supabase schema verified and applied.")
            except Exception as e:
                logger.warning("Schema initialization notice: %s", e)

    def upsert_truth_vector(
        self,
        evidence_id: str,
        title: str,
        text: str,
        source: str,
        source_type: str,
        truth_label: int,
        category: str,
        embedding: list,
        news_id: Optional[str] = None,
    ) -> bool:
        """Upserts a 384-dim pgvector ground-truth or debunk record into official_truth_vectors."""
        try:
            conn = self.get_connection()
            vec_literal = "[" + ",".join(f"{float(v):.6f}" for v in embedding[:384]) + "]"
            sql = """
                INSERT INTO official_truth_vectors
                    (evidence_id, news_id, title, text, source, source_type, truth_label, category, embedding)
                VALUES
                    (:evidence_id, :news_id, :title, :text, :source, :source_type, :truth_label, :category, CAST(:vec AS vector))
                ON CONFLICT (evidence_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    text = EXCLUDED.text,
                    source = EXCLUDED.source,
                    source_type = EXCLUDED.source_type,
                    truth_label = EXCLUDED.truth_label,
                    category = EXCLUDED.category,
                    embedding = EXCLUDED.embedding;
            """
            conn.run(
                sql,
                evidence_id=str(evidence_id)[:64],
                news_id=(str(news_id)[:64] if news_id else None),
                title=str(title)[:500],
                text=str(text)[:2500],
                source=str(source)[:120],
                source_type=str(source_type)[:60],
                truth_label=int(truth_label),
                category=str(category)[:60],
                vec=vec_literal,
            )
            return True
        except Exception as e:
            logger.warning("pgvector upsert notice for %s: %s", evidence_id, e)
            self.invalidate_current_connection()
            return False

    def search_truth_vectors(self, query_embedding: list, top_k: int = 5) -> List[Dict[str, Any]]:
        """Executes live pgvector HNSW cosine distance (<=>) query against official_truth_vectors."""
        try:
            conn = self.get_connection()
            vec_literal = "[" + ",".join(f"{float(v):.6f}" for v in query_embedding[:384]) + "]"
            sql = """
                SELECT evidence_id, news_id, title, text, source, source_type, truth_label, category,
                       1.0 - (embedding <=> CAST(:vec AS vector)) AS score
                FROM official_truth_vectors
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :lim;
            """
            rows = conn.run(sql, vec=vec_literal, lim=int(top_k))
            cols = [c["name"] for c in conn.columns] if conn.columns else []
            out = []
            for r in rows:
                d = dict(zip(cols, r))
                d["score"] = round(float(d.get("score") or 0.0), 4)
                out.append(d)
            return out
        except Exception as e:
            logger.warning("pgvector search notice: %s", e)
            self.invalidate_current_connection()
            return []

    def delete_truth_vector(self, identifier: str) -> int:
        """Removes a purged/forgotten item from official_truth_vectors by evidence_id, news_id, or title substring."""
        try:
            conn = self.get_connection()
            sql = """
                DELETE FROM official_truth_vectors
                WHERE evidence_id = :ident OR news_id = :ident OR title = :ident;
            """
            conn.run(sql, ident=str(identifier))
            return 1
        except Exception as e:
            logger.warning("pgvector delete notice: %s", e)
            self.invalidate_current_connection()
            return 0

    def get_truth_vector_count(self) -> int:
        try:
            conn = self.get_connection()
            rows = conn.run("SELECT COUNT(*) FROM official_truth_vectors;")
            return int(rows[0][0]) if rows else 0
        except Exception:
            return 0

    def sync_training_samples_index(self, df_rows: list) -> int:
        """Populates training_samples metadata table in Supabase via single batched JSONB insert."""
        try:
            conn = self.get_connection()
            res = conn.run("SELECT COUNT(*) FROM training_samples;")
            existing = int(res[0][0]) if res else 0
            if existing >= 100 or not df_rows:
                return existing
            batch = []
            for row in df_rows[:300]:
                sid = str(row.get("sample_id") or "").replace("\x00", "")[:64]
                if not sid:
                    continue
                nid = str(row.get("news_id") or "").replace("\x00", "")[:64] or None
                batch.append({
                    "sample_id": sid,
                    "news_id": nid,
                    "shard_id": int(row.get("shard_id", 0)),
                    "slice_id": int(row.get("slice_id", 0)),
                    "title": str(row.get("title") or "").replace("\x00", "")[:400],
                    "text": str(row.get("text") or "").replace("\x00", "")[:1200],
                    "label": int(row.get("label", 0)),
                    "status": str(row.get("status") or "ACTIVE")[:48],
                })
            if not batch:
                return existing
            sql = """
                INSERT INTO training_samples (sample_id, news_id, shard_id, slice_id, title, text, label, status)
                SELECT sample_id, news_id, shard_id, slice_id, title, text, label, status
                FROM jsonb_to_recordset(CAST(:rows_json AS jsonb))
                  AS x(sample_id text, news_id text, shard_id int, slice_id int, title text, text text, label int, status text)
                ON CONFLICT (sample_id) DO NOTHING;
            """
            conn.run(sql, rows_json=json.dumps(batch))
            return len(batch)
        except Exception as e:
            logger.warning("Training samples index sync notice: %s", e)
            return 0

    def mark_training_samples_unlearned(self, sample_ids: list) -> int:
        """Purges target sample_ids from Supabase training_samples in one SQL roundtrip."""
        if not sample_ids:
            return 0
        try:
            conn = self.get_connection()
            clean_ids = [str(s) for s in sample_ids if s]
            if not clean_ids:
                return 0
            conn.run(
                "DELETE FROM training_samples WHERE sample_id = ANY(SELECT jsonb_array_elements_text(CAST(:sids AS jsonb)));",
                sids=json.dumps(clean_ids),
            )
            return len(clean_ids)
        except Exception as e:
            logger.debug("Training sample unlearn update notice: %s", e)
            return 0

    def _seed_initial_data(self, conn):
        """Seeds initial verified news dispatches into Supabase if empty."""
        try:
            res = conn.run("SELECT COUNT(*) FROM news;")
            cnt = int(res[0][0]) if res else 0
            if cnt < 5:
                local_file = BASE_DIR / "data" / "local_store.json"
                if local_file.exists():
                    data = json.loads(local_file.read_text(encoding="utf-8"))
                    news_items = data.get("news", [])
                    news_col = self["news"]
                    for item in news_items[:15]:
                        news_col.insert_one(item)
                    logger.info("Supabase initial core news migration complete!")
        except Exception as e:
            logger.warning("Data seeding notice: %s", e)

    def __getitem__(self, name: str) -> SupabaseCollection:
        return SupabaseCollection(name, self)
