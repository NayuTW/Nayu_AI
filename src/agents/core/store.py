import json
import os
import sqlite3
import threading
import time
from typing import Any, Optional

DEFAULT_DB_PATH = ".cache/agent_control_center.sqlite3"
os.makedirs(".cache", exist_ok=True)

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-64000;
PRAGMA temp_store=MEMORY;
PRAGMA mmap_size=268435456;
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  type TEXT NOT NULL,
  payload TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts DESC);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(type);

CREATE TABLE IF NOT EXISTS tool_metrics (
  tool_name TEXT PRIMARY KEY,
  enabled INTEGER NOT NULL,
  calls INTEGER NOT NULL,
  failures INTEGER NOT NULL,
  failure_streak INTEGER NOT NULL,
  last_latency_ms REAL NOT NULL,
  avg_latency_ms REAL NOT NULL,
  last_error TEXT NOT NULL,
  last_update_ts REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fine_tune_examples (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts REAL NOT NULL,
  session_id TEXT NOT NULL,
  user_text TEXT NOT NULL,
  assistant_text TEXT NOT NULL,
  meta TEXT NOT NULL,
  label TEXT NOT NULL DEFAULT 'unlabeled' CHECK(label IN ('good','bad','unlabeled'))
);
CREATE INDEX IF NOT EXISTS idx_examples_ts ON fine_tune_examples(ts DESC);
CREATE INDEX IF NOT EXISTS idx_examples_label ON fine_tune_examples(label);
"""

class SQLiteStore:
    def __init__(self, path: str = DEFAULT_DB_PATH):
        self.path = path
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30.0)
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()
        self._event_buffer: list[tuple] = []
        self._buffer_size = 10

    def append_event(self, type_: str, payload: dict[str, Any], ts: Optional[float] = None) -> Optional[int]:
        """
        Append event to buffer for batch insertion.
        Returns None since actual ID is assigned during flush.
        For immediate insertion with ID, call flush() after append.
        """
        ts = ts or time.time()
        data = json.dumps(payload, ensure_ascii=False)
        with self._lock:
            # Buffer events for batch insert
            self._event_buffer.append((ts, type_, data))
            if len(self._event_buffer) >= self._buffer_size:
                self._flush_events()
            # Return None - actual ID assigned on flush
            return None
    
    def _flush_events(self):
        """Flush buffered events to database."""
        if not self._event_buffer:
            return
        try:
            with self._conn:
                self._conn.executemany(
                    "INSERT INTO events (ts, type, payload) VALUES (?, ?, ?)",
                    self._event_buffer,
                )
            # Only clear buffer after successful insert
            self._event_buffer.clear()
        except Exception:
            # Preserve buffer on error - events will be retried on next flush
            raise
    
    def flush(self):
        """Public method to flush any pending events."""
        with self._lock:
            self._flush_events()

    def get_recent_events(self, limit: int = 200) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, ts, type, payload FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        out = []
        for rid, ts, typ, payload in rows[::-1]:
            try:
                p = json.loads(payload)
            except Exception:
                p = {"raw": payload}
            out.append({"id": rid, "ts": ts, "type": typ, "payload": p})
        return out

    def upsert_tool_stats(self, stats: dict[str, Any]):
        row = (
            stats["tool_name"],
            1 if stats["enabled"] else 0,
            int(stats["calls"]),
            int(stats["failures"]),
            int(stats["failure_streak"]),
            float(stats["last_latency_ms"]),
            float(stats["avg_latency_ms"]),
            stats.get("last_error", ""),
            float(stats["last_update_ts"] or time.time()),
        )
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO tool_metrics(tool_name, enabled, calls, failures, failure_streak, last_latency_ms, avg_latency_ms, last_error, last_update_ts)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(tool_name) DO UPDATE SET
                  enabled=excluded.enabled,
                  calls=excluded.calls,
                  failures=excluded.failures,
                  failure_streak=excluded.failure_streak,
                  last_latency_ms=excluded.last_latency_ms,
                  avg_latency_ms=excluded.avg_latency_ms,
                  last_error=excluded.last_error,
                  last_update_ts=excluded.last_update_ts
                """,
                row,
            )

    def get_all_tool_stats(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT tool_name, enabled, calls, failures, failure_streak, last_latency_ms, avg_latency_ms, last_error, last_update_ts
                FROM tool_metrics
                ORDER BY tool_name ASC
                """
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "tool_name": r[0],
                    "enabled": bool(r[1]),
                    "calls": r[2],
                    "failures": r[3],
                    "failure_streak": r[4],
                    "last_latency_ms": r[5],
                    "avg_latency_ms": r[6],
                    "last_error": r[7],
                    "last_update_ts": r[8],
                }
            )
        return out

    def set_setting(self, key: str, value: str):
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value),
            )

    def get_setting(self, key: str, default: Optional[str] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return default
        return row[0]

    def append_example(self, session_id: str, user_text: str, assistant_text: str, meta: dict[str, Any], ts: Optional[float] = None) -> int:
        ts = ts or time.time()
        meta_json = json.dumps(meta, ensure_ascii=False)
        with self._lock, self._conn:
            cur = self._conn.execute(
                """
                INSERT INTO fine_tune_examples (ts, session_id, user_text, assistant_text, meta)
                VALUES (?, ?, ?, ?, ?)
                """,
                (ts, session_id, user_text, assistant_text, meta_json),
            )
            return cur.lastrowid

    def label_example(self, example_id: int, label: str):
        assert label in ("good", "bad", "unlabeled")
        with self._lock, self._conn:
            self._conn.execute("UPDATE fine_tune_examples SET label=? WHERE id=?", (label, example_id))

    def get_recent_examples(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, ts, session_id, user_text, assistant_text, meta, label
                FROM fine_tune_examples
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        out: list[dict[str, Any]] = []
        for rid, ts, sid, u, a, m, lab in rows:
            try:
                meta = json.loads(m)
            except Exception:
                meta = {"raw": m}
            out.append({"id": rid, "ts": ts, "session_id": sid, "user_text": u, "assistant_text": a, "meta": meta, "label": lab})
        return list(reversed(out))

    def export_examples_jsonl(self, path: str, include_unlabeled: bool = False) -> int:
        with self._lock:
            if include_unlabeled:
                rows = self._conn.execute(
                    "SELECT user_text, assistant_text, meta, label FROM fine_tune_examples ORDER BY id ASC"
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT user_text, assistant_text, meta, label FROM fine_tune_examples WHERE label IN ('good','bad') ORDER BY id ASC"
                ).fetchall()
        n = 0
        with open(path, "w", encoding="utf-8") as f:
            for u, a, m, lab in rows:
                try:
                    meta = json.loads(m)
                except Exception:
                    meta = {}
                obj = {"user": u, "assistant": a, "label": lab, "meta": meta}
                f.write(json.dumps(obj, ensure_ascii=False) + "\n")
                n += 1
        return n
    
    def close(self):
        """Close database connection and flush pending events."""
        with self._lock:
            self._flush_events()
            self._conn.close()