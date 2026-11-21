"""
SMRITI SHUDDHI - SUPABASE POSTGRESQL & PGVECTOR ADAPTER
=========================================================
Transparent collection-compatible adapter for Supabase PostgreSQL.
Supports:
- Standard Mongo-like collection calls: find_one, find, insert_one, update_one, delete_one, count_documents
- Native JSONB serialization for multi-aspect XAI verdicts
- Native vector(384) HNSW cosine similarity search
- Automatic schema creation from supabase_schema.sql on first connect
"""

import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from pgvector.psycopg2 import register_vector

logger = logging.getLogger("SupabaseAdapter")

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class SupabaseCursor:
    def __init__(self, items: List[Dict[str, Any]]):
        self._items = items

    def sort(self, key_or_list, direction=None):
        if isinstance(key_or_list, list) and len(key_or_list) > 0:
            key, direction = key_or_list[0]
        else:
            key = key_or_list
        reverse = (direction == -1 or direction == "descending")
        self._items.sort(key=lambda x: str(x.get(key, '')), reverse=reverse)
        return self

    def limit(self, n: int):
        self._items = self._items[:n]
        return self

    def __iter__(self):
        return iter(self._items)

    def to_list(self, length: Optional[int] = None):
        return self._items[:length] if length is not None else self._items


class SupabaseCollection:
    """PostgreSQL Table wrapper matching Mongo collection interface."""
    def __init__(self, table_name: str, db_ref: 'SupabaseDB'):
        self.table_name = table_name
        self.db = db_ref

    def _execute(self, query: str, params: tuple = None, fetch_one: bool = False, fetch_all: bool = False):
        conn = self.db.get_connection()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params or ())
            if fetch_one:
                row = cur.fetchone()
                return dict(row) if row else None
            if fetch_all:
                return [dict(r) for r in cur.fetchall()]
            return None

    def insert_one(self, doc: Dict[str, Any]):
        doc_copy = dict(doc)
        # Ensure _id or primary key
        if "_id" in doc_copy and "news_id" not in doc_copy and self.table_name == "news":
            doc_copy["news_id"] = str(doc_copy["_id"])
        
        # Serialize dicts/lists to Json for jsonb columns
        processed = {}
        for k, v in doc_copy.items():
            if k == "_id":
                continue
            if isinstance(v, (dict, list)):
                processed[k] = Json(v)
            else:
                processed[k] = v

        keys = list(processed.keys())
        cols = ", ".join(keys)
        placeholders = ", ".join(["%s"] * len(keys))
        vals = tuple(processed[k] for k in keys)

        query = f"""
            INSERT INTO {self.table_name} ({cols}) 
            VALUES ({placeholders})
            ON CONFLICT DO NOTHING;
        """
        try:
            self._execute(query, vals)
        except Exception as e:
            logger.warning("Supabase insert error into %s: %s", self.table_name, e)
            # Rollback connection if aborted
            self.db.conn.rollback()

        class InsertResult:
            inserted_id = doc_copy.get("news_id") or doc_copy.get("sample_id") or doc_copy.get("request_id") or doc_copy.get("_id")
        return InsertResult()

    def find_one(self, query: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        query = query or {}
        where_clauses = []
        vals = []
        for k, v in query.items():
            if k == "_id":
                k = "news_id" if self.table_name == "news" else k
            where_clauses.append(f"{k} = %s")
            vals.append(v)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT * FROM {self.table_name} {where_sql} LIMIT 1;"
        return self._execute(sql, tuple(vals), fetch_one=True)

    def find(self, query: Dict[str, Any] = None) -> SupabaseCursor:
        query = query or {}
        where_clauses = []
        vals = []
        for k, v in query.items():
            if k == "_id":
                k = "news_id" if self.table_name == "news" else k
            where_clauses.append(f"{k} = %s")
            vals.append(v)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT * FROM {self.table_name} {where_sql};"
        try:
            rows = self._execute(sql, tuple(vals), fetch_all=True) or []
        except Exception as e:
            logger.warning("Supabase find error on %s: %s", self.table_name, e)
            self.db.conn.rollback()
            rows = []
        return SupabaseCursor(rows)

    def count_documents(self, query: Dict[str, Any] = None) -> int:
        query = query or {}
        where_clauses = []
        vals = []
        for k, v in query.items():
            if k == "_id":
                k = "news_id" if self.table_name == "news" else k
            where_clauses.append(f"{k} = %s")
            vals.append(v)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT COUNT(*) AS c FROM {self.table_name} {where_sql};"
        try:
            res = self._execute(sql, tuple(vals), fetch_one=True)
            return res["c"] if res else 0
        except Exception as e:
            logger.warning("Supabase count error on %s: %s", self.table_name, e)
            self.db.conn.rollback()
            return 0

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        set_vals = update.get("$set", update)
        set_clauses = []
        vals = []
        for k, v in set_vals.items():
            set_clauses.append(f"{k} = %s")
            vals.append(Json(v) if isinstance(v, (dict, list)) else v)

        where_clauses = []
        for k, v in query.items():
            if k == "_id":
                k = "news_id" if self.table_name == "news" else k
            where_clauses.append(f"{k} = %s")
            vals.append(v)

        sql = f"""
            UPDATE {self.table_name} 
            SET {", ".join(set_clauses)}
            WHERE {" AND ".join(where_clauses)};
        """
        try:
            self._execute(sql, tuple(vals))
            return True
        except Exception as e:
            logger.warning("Supabase update error on %s: %s", self.table_name, e)
            self.db.conn.rollback()
            return False

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        return self.update_one(query, update)

    def delete_one(self, query: Dict[str, Any]):
        where_clauses = []
        vals = []
        for k, v in query.items():
            if k == "_id":
                k = "news_id" if self.table_name == "news" else k
            where_clauses.append(f"{k} = %s")
            vals.append(v)

        sql = f"DELETE FROM {self.table_name} WHERE {' AND '.join(where_clauses)};"
        try:
            self._execute(sql, tuple(vals))
            return True
        except Exception as e:
            logger.warning("Supabase delete error on %s: %s", self.table_name, e)
            self.db.conn.rollback()
            return False

    def delete_many(self, query: Dict[str, Any]):
        return self.delete_one(query)

    def create_index(self, *args, **kwargs):
        pass


class SupabaseDB:
    """Manages PostgreSQL connection, pgvector registration, and schema deployment."""
    def __init__(self, uri: str):
        self.uri = uri
        self.conn = None
        self._connect()
        self._initialize_schema()

    def _connect(self):
        try:
            self.conn = psycopg2.connect(self.uri, connect_timeout=8)
            self.conn.autocommit = True
            register_vector(self.conn)
            logger.info("Successfully connected to Supabase PostgreSQL!")
        except Exception as e:
            logger.error("Failed to connect to Supabase: %s", e)
            raise e

    def get_connection(self):
        if self.conn is None or self.conn.closed:
            self._connect()
        return self.conn

    def _initialize_schema(self):
        schema_file = BASE_DIR / "supabase_schema.sql"
        if schema_file.exists():
            try:
                sql = schema_file.read_text(encoding="utf-8")
                with self.conn.cursor() as cur:
                    cur.execute(sql)
                logger.info("Supabase schema & pgvector verified / applied.")
            except Exception as e:
                logger.warning("Schema initialization notice: %s", e)

    def __getitem__(self, name: str) -> SupabaseCollection:
        return SupabaseCollection(name, self)
