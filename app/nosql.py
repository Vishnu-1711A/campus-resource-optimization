"""
Campus Resource Optimization System - NoSQL Document Store (MongoDB)
Holds the semi-structured, high-volume data that does not belong in the 3NF schema:

  * sessions       - sign-in session tokens (key-value lookups, auto-expiring via a TTL index)
  * activity_logs  - schema-less event log of every action performed on the UI
                     (each event type carries a different set of fields)

Dual-mode like database.py: connects to MongoDB if reachable; otherwise falls back to a
small JSON-file document store exposing the same subset of the PyMongo collection API.
"""

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from . import database  # noqa: F401  (loads .env before MONGO_* are read)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB", "campus_resource_nosql")
NOSQL_BACKEND = os.getenv("NOSQL_BACKEND", "auto").lower()  # 'auto', 'mongodb' or 'file'
FILE_STORE_PATH = os.path.join(os.path.dirname(__file__), "nosql_store.json")

SESSION_TTL_HOURS = 12

ACTIVE_NOSQL_BACKEND = "file"  # 'mongodb' or 'file'


# ============================================================================
# FALLBACK: JSON-FILE DOCUMENT STORE (subset of the PyMongo Collection API)
# ============================================================================
class _FileCursor:
    def __init__(self, docs: List[Dict[str, Any]]):
        self._docs = docs

    def sort(self, key: str, direction: int = 1):
        self._docs.sort(key=lambda d: d.get(key) or "", reverse=direction < 0)
        return self

    def limit(self, n: int):
        self._docs = self._docs[:n] if n else self._docs
        return self

    def __iter__(self):
        return iter(self._docs)


class _FileCollection:
    _lock = threading.Lock()

    def __init__(self, name: str):
        self.name = name

    @staticmethod
    def _load() -> Dict[str, List[Dict[str, Any]]]:
        if not os.path.exists(FILE_STORE_PATH):
            return {}
        with open(FILE_STORE_PATH) as f:
            data = json.load(f)
        for docs in data.values():
            for d in docs:
                for k, v in d.items():
                    if isinstance(v, str) and k.endswith(("_at", "timestamp")):
                        try:
                            d[k] = datetime.fromisoformat(v)
                        except ValueError:
                            pass
        return data

    @staticmethod
    def _save(data: Dict[str, List[Dict[str, Any]]]):
        with open(FILE_STORE_PATH, "w") as f:
            json.dump(data, f, default=lambda o: o.isoformat() if isinstance(o, datetime) else str(o), indent=1)

    @staticmethod
    def _matches(doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        return all(doc.get(k) == v for k, v in query.items())

    def insert_one(self, doc: Dict[str, Any]):
        with self._lock:
            data = self._load()
            doc.setdefault("_id", uuid.uuid4().hex)
            data.setdefault(self.name, []).append(doc)
            self._save(data)

    def find_one(self, query: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return next((d for d in self._load().get(self.name, []) if self._matches(d, query)), None)

    def find(self, query: Optional[Dict[str, Any]] = None) -> _FileCursor:
        return _FileCursor([d for d in self._load().get(self.name, []) if self._matches(d, query or {})])

    def delete_one(self, query: Dict[str, Any]):
        with self._lock:
            data = self._load()
            docs = data.get(self.name, [])
            for i, d in enumerate(docs):
                if self._matches(d, query):
                    del docs[i]
                    break
            self._save(data)

    def count_documents(self, query: Dict[str, Any]) -> int:
        return len(self.find(query)._docs)


# ============================================================================
# CONNECTION
# ============================================================================
sessions = None
activity_logs = None


def connect():
    global sessions, activity_logs, ACTIVE_NOSQL_BACKEND
    if NOSQL_BACKEND in ("auto", "mongodb"):
        try:
            from pymongo import ASCENDING, DESCENDING, MongoClient

            client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
            client.admin.command("ping")
            db = client[MONGO_DB_NAME]
            sessions = db["sessions"]
            activity_logs = db["activity_logs"]
            # TTL index: MongoDB deletes the session document automatically once expires_at passes
            sessions.create_index("expires_at", expireAfterSeconds=0)
            activity_logs.create_index([("timestamp", DESCENDING)])
            activity_logs.create_index([("user.user_id", ASCENDING), ("timestamp", DESCENDING)])
            ACTIVE_NOSQL_BACKEND = "mongodb"
            print(f">>> NoSQL backend: MongoDB {MONGO_URI}/{MONGO_DB_NAME}")
            return
        except Exception as e:
            print(f">>> MongoDB unavailable ({e}); using JSON document store at {FILE_STORE_PATH}")
    sessions = _FileCollection("sessions")
    activity_logs = _FileCollection("activity_logs")
    ACTIVE_NOSQL_BACKEND = "file"


connect()


# ============================================================================
# SESSIONS
# ============================================================================
def _utcnow() -> datetime:
    # MongoDB TTL indexes compare against UTC, so session times are stored as naive UTC
    return datetime.now(timezone.utc).replace(tzinfo=None)


def create_session(user: Dict[str, Any]) -> str:
    token = uuid.uuid4().hex + uuid.uuid4().hex
    now = _utcnow()
    sessions.insert_one({
        "_id": token,
        "user_id": user["user_id"],
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "created_at": now,
        "expires_at": now + timedelta(hours=SESSION_TTL_HOURS),
    })
    return token


def get_session(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    doc = sessions.find_one({"_id": token})
    if not doc:
        return None
    if doc["expires_at"] < _utcnow():
        sessions.delete_one({"_id": token})
        return None
    return doc


def delete_session(token: Optional[str]):
    if token:
        sessions.delete_one({"_id": token})


# ============================================================================
# ACTIVITY LOG
# ============================================================================
def log_activity(action: str, user: Optional[Dict[str, Any]] = None, entity: Optional[str] = None,
                 entity_id: Any = None, details: Optional[Dict[str, Any]] = None):
    """Stores one event document. 'details' is free-form - every action records what is relevant to it."""
    try:
        activity_logs.insert_one({
            "timestamp": datetime.now(),
            "action": action,
            "user": {k: user[k] for k in ("user_id", "name", "role")} if user else {"name": "SYSTEM"},
            "entity": entity,
            "entity_id": entity_id,
            "details": details or {},
        })
    except Exception as e:
        print(f">>> Failed to write activity log: {e}")


def get_recent_activity(limit: int = 100) -> List[Dict[str, Any]]:
    docs = activity_logs.find({}).sort("timestamp", -1).limit(limit)
    return [{**d, "_id": str(d["_id"]), "timestamp": d["timestamp"].strftime("%Y-%m-%d %H:%M:%S")} for d in docs]
