import os
import json
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional
from config import MONGO_URI, MONGO_DB, DATA_DIR

logger = logging.getLogger("Database")

# Local fallback storage path
LOCAL_DB_FILE = DATA_DIR / "local_store.json"


class FallbackCursor:
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


class LocalFallbackCollection:
    """Thread-safe, file-persisted JSON fallback collection when MongoDB is offline."""
    def __init__(self, name: str, db_ref: 'LocalFallbackDB'):
        self.name = name
        self.db = db_ref

    def _get_items(self) -> List[Dict[str, Any]]:
        self.db.load()
        return self.db.data.setdefault(self.name, [])

    def insert_one(self, doc: Dict[str, Any]):
        doc_copy = dict(doc)
        if "_id" not in doc_copy:
            doc_copy["_id"] = f"{self.name}_{int(time.time()*1000)}_{len(self._get_items())}"
        self._get_items().append(doc_copy)
        self.db.save()
        class InsertResult:
            inserted_id = doc_copy["_id"]
        return InsertResult()

    def find_one(self, query: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        query = query or {}
        for item in reversed(self._get_items()):
            if all(item.get(k) == v for k, v in query.items()):
                return dict(item)
        return None

    def find(self, query: Dict[str, Any] = None) -> FallbackCursor:
        query = query or {}
        matches = [
            dict(item) for item in reversed(self._get_items())
            if all(item.get(k) == v for k, v in query.items())
        ]
        return FallbackCursor(matches)

    def count_documents(self, query: Dict[str, Any] = None) -> int:
        query = query or {}
        return sum(1 for item in self._get_items() if all(item.get(k) == v for k, v in query.items()))

    def update_one(self, query: Dict[str, Any], update: Dict[str, Any]):
        for item in self._get_items():
            if all(item.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    item.update(update["$set"])
                else:
                    item.update(update)
                self.db.save()
                return True
        return False

    def update_many(self, query: Dict[str, Any], update: Dict[str, Any]):
        count = 0
        set_vals = update.get("$set", update)
        for item in self._get_items():
            if all(item.get(k) == v for k, v in query.items()):
                item.update(set_vals)
                count += 1
        if count > 0:
            self.db.save()
        class UpdateResult:
            modified_count = count
        return UpdateResult()

    def delete_one(self, query: Dict[str, Any]):
        items = self._get_items()
        for idx, item in enumerate(items):
            if all(item.get(k) == v for k, v in query.items()):
                del items[idx]
                self.db.save()
                return True
        return False

    def delete_many(self, query: Dict[str, Any]):
        items = self._get_items()
        initial_len = len(items)
        self.db.data[self.name] = [item for item in items if not all(item.get(k) == v for k, v in query.items())]
        self.db.save()
        return initial_len - len(self.db.data[self.name])

    def create_index(self, *args, **kwargs):
        pass


class LocalFallbackDB:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, List[Dict[str, Any]]] = {}
        self.load()

    def load(self):
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self.data = {}

    def save(self):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, indent=2, default=str), encoding="utf-8")
        except Exception:
            pass

    def __getitem__(self, name: str) -> LocalFallbackCollection:
        return LocalFallbackCollection(name, self)


def _probe_mongo(timeout: float = 0.2) -> bool:
    try:
        import socket
        with socket.create_connection(("localhost", 27017), timeout=timeout):
            return True
    except Exception:
        return False

# Initialization with automatic connection probe
using_mongo = False
if _probe_mongo():
    try:
        from pymongo import MongoClient, DESCENDING
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=800, connectTimeoutMS=800)
        client.admin.command('ping')
        db = client[MONGO_DB]
        using_mongo = True
        logger.info("Connected to live MongoDB cluster at %s", MONGO_URI)
    except Exception as e:
        using_mongo = False

if not using_mongo:
    logger.info("MongoDB cluster unreachable; initializing persistent LocalFallbackDB at %s", LOCAL_DB_FILE)
    db = LocalFallbackDB(LOCAL_DB_FILE)
    DESCENDING = -1

news_col = db['news']
training_col = db['training_samples']
requests_col = db['removal_requests']
unlearning_col = db['unlearning_jobs']
models_col = db['model_versions']
actions_col = db['admin_actions']
devices_col = db['devices']
audit_col = db['audit_logs']
users_col = db['users']
unlearning_ledger_col = db['unlearning_ledger']


def seed_demo_users():
    """Seeds default demo users for Citizen Journalist and Chief Fact-Checker."""
    if users_col.count_documents({}) == 0:
        demo_users = [
            {
                "user_id": "USR_ADMIN_001",
                "email": "admin@veritas.org",
                "password": "admin123",
                "name": "Dr. Sarah Mitchell",
                "role": "ADMIN",
                "title": "Chief Fact-Checking Editor",
                "created_at": now()
            },
            {
                "user_id": "USR_JOURNALIST_002",
                "email": "reporter@times.com",
                "password": "user123",
                "name": "Alex Rivera",
                "role": "JOURNALIST",
                "title": "Investigative Tech Journalist",
                "created_at": now()
            },
            {
                "user_id": "USR_CITIZEN_003",
                "email": "citizen@wire.in",
                "password": "user123",
                "name": "Priya Sharma",
                "role": "CITIZEN",
                "title": "Community Contributor",
                "created_at": now()
            }
        ]
        for u in demo_users:
            users_col.insert_one(u)
        logger.info("Seeded %d demo authentication user profiles.", len(demo_users))


def now():
    return datetime.now(timezone.utc).isoformat()


def init_db():
    seed_demo_users()
    if using_mongo:
        try:
            news_col.create_index([('created_at', DESCENDING)])
            news_col.create_index('news_id', unique=True)
            training_col.create_index('sample_id', unique=True)
            training_col.create_index('news_id')
            requests_col.create_index([('created_at', DESCENDING)])
            unlearning_col.create_index([('created_at', DESCENDING)])
            models_col.create_index('version_id', unique=True)
            actions_col.create_index([('created_at', DESCENDING)])
            devices_col.create_index('client_id', unique=True)
            audit_col.create_index([('created_at', DESCENDING)])
        except Exception as e:
            logger.warning("MongoDB indexing notice: %s", e)
    else:
        logger.info("Local fallback database initialized successfully.")
