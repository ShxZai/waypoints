"""A tiny JSON document store on SQLite.

Mirrors the collections the page already uses (checklist, learn, steps,
units, scope, logs), so the page's storage code works unchanged.
"""
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

NAME = re.compile(r"^[A-Za-z0-9_.:@+~-]{1,200}$")


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS docs ("
                " collection TEXT NOT NULL, id TEXT NOT NULL, json TEXT NOT NULL,"
                " updated_at REAL NOT NULL, PRIMARY KEY (collection, id))"
            )
            self._db.commit()

    @staticmethod
    def check(*names: str) -> None:
        for n in names:
            if not NAME.match(n):
                raise ValueError(f"bad name: {n!r}")

    def list(self, collection: str) -> list[dict]:
        self.check(collection)
        with self._lock:
            rows = self._db.execute(
                "SELECT id, json FROM docs WHERE collection = ? ORDER BY id", (collection,)
            ).fetchall()
        return [{"id": i, "data": json.loads(j)} for i, j in rows]

    def get(self, collection: str, doc_id: str):
        self.check(collection, doc_id)
        with self._lock:
            row = self._db.execute(
                "SELECT json FROM docs WHERE collection = ? AND id = ?", (collection, doc_id)
            ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, collection: str, doc_id: str, data: dict) -> None:
        self.check(collection, doc_id)
        text = json.dumps(data, ensure_ascii=False)
        with self._lock:
            self._db.execute(
                "INSERT INTO docs (collection, id, json, updated_at) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(collection, id) DO UPDATE SET json = excluded.json,"
                " updated_at = excluded.updated_at",
                (collection, doc_id, text, time.time()),
            )
            self._db.commit()
