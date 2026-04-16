"""
chaos_spark_memory.py — VOS v0.5.0 chaos-theory-inspired episodic memory.

Stores ingested data records in an SQLite database and maintains a
logistic-map chaotic index so that recall patterns exhibit emergent,
non-linear associations — mimicking aspects of human associative memory.

The SQLite database path defaults to ``vos_memory.db`` in the current
working directory and can be overridden via the ``db_path`` constructor
parameter.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = "vos_memory.db"
_LOGISTIC_R = 3.9          # chaotic regime of the logistic map
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS memory_records (
    key         TEXT PRIMARY KEY,
    payload     TEXT NOT NULL,
    timestamp   REAL NOT NULL,
    chaos_index REAL NOT NULL
);
"""


def _logistic_next(x: float) -> float:
    """One step of the logistic map:  x_{n+1} = r * x_n * (1 - x_n)."""
    return _LOGISTIC_R * x * (1.0 - x)


def _make_key(data: Any) -> str:
    """Deterministic SHA-256 key for *data*."""
    raw = json.dumps(data, sort_keys=True, default=str).encode()
    return hashlib.sha256(raw).hexdigest()[:32]


class ChaosSparkMemory:
    """Episodic memory store with chaotic associative indexing.

    Parameters
    ----------
    capacity:
        Maximum number of records held in the hot (in-memory) cache.
        Older entries are evicted to SQLite when the cache is full.
    compression_ratio:
        Fraction (0 < ratio ≤ 1) of vector dimensions kept when
        :py:meth:`compress_hot_cache` is called.  A value of ``0.5``
        halves the stored vector size.
    db_path:
        Path to the SQLite persistence file.  Defaults to
        ``"vos_memory.db"`` in the current working directory.
    seed:
        Initial chaotic seed (must be strictly between 0 and 1).
    """

    def __init__(
        self,
        capacity: int = 512,
        compression_ratio: float = 0.5,
        db_path: str = _DEFAULT_DB,
        seed: float = 0.37,
    ) -> None:
        if not (0.0 < seed < 1.0):
            raise ValueError(f"seed must be strictly between 0 and 1, got {seed!r}.")
        self.capacity = capacity
        self.compression_ratio = compression_ratio
        self.db_path = db_path
        self._chaos_x: float = seed

        self._hot_cache: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._db: sqlite3.Connection = sqlite3.connect(db_path, check_same_thread=False)
        # WAL mode: allows concurrent readers while a writer is active.
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=NORMAL")
        self._db.execute(_SCHEMA_SQL)
        self._db.commit()

        logger.info(
            "ChaosSparkMemory ready — capacity=%d compression_ratio=%.2f db=%s",
            capacity,
            compression_ratio,
            db_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def ingest(self, data: Any, *, key: Optional[str] = None) -> str:
        """Persist *data* into both the hot cache and SQLite.

        Parameters
        ----------
        data:
            Any JSON-serialisable object.
        key:
            Explicit storage key.  Auto-generated from a hash of *data*
            when not provided.

        Returns
        -------
        str
            The storage key assigned to this record.
        """
        self._chaos_x = _logistic_next(self._chaos_x)
        chaos_idx = self._chaos_x

        record_key = key or _make_key(data)
        record = {
            "key": record_key,
            "payload": data,
            "timestamp": time.time(),
            "chaos_index": chaos_idx,
        }

        self._hot_cache.append(record)
        self._persist(record)

        logger.debug("ChaosSparkMemory.ingest key=%s chaos_index=%.6f", record_key, chaos_idx)
        return record_key

    def recall(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve a record by *key* (hot cache first, then SQLite)."""
        for record in self._hot_cache:
            if record["key"] == key:
                return record

        row = self._db.execute(
            "SELECT key, payload, timestamp, chaos_index FROM memory_records WHERE key = ?",
            (key,),
        ).fetchone()
        if row:
            return {
                "key": row[0],
                "payload": json.loads(row[1]),
                "timestamp": row[2],
                "chaos_index": row[3],
            }
        return None

    def status(self) -> Dict[str, Any]:
        """Return a summary of current memory state."""
        count = self._db.execute("SELECT COUNT(*) FROM memory_records").fetchone()[0]
        return {
            "hot_cache_size": len(self._hot_cache),
            "capacity": self.capacity,
            "db_records": count,
            "chaos_x": round(self._chaos_x, 8),
            "db_path": self.db_path,
        }

    def compress_hot_cache(self, tensor_engine: Any = None) -> str:
        """Compress vector payloads in the hot cache using *tensor_engine*.

        Parameters
        ----------
        tensor_engine:
            A :class:`~vos_core.tensor_accel.TensorEngine` instance.
            When *None* or unavailable, compression is skipped and
            ``"skipped"`` is returned.

        Returns
        -------
        str
            ``"ok"`` on success, ``"skipped"`` when engine is absent.
        """
        if tensor_engine is None:
            logger.debug("compress_hot_cache: no tensor_engine supplied, skipping.")
            return "skipped"

        vectors = []
        indices = []
        for i, record in enumerate(self._hot_cache):
            payload = record.get("payload")
            if isinstance(payload, (list, tuple)):
                vectors.append(payload)
                indices.append(i)

        if not vectors:
            return "skipped"

        compressed = tensor_engine.batch_compress(vectors, ratio=self.compression_ratio)
        cache_list = list(self._hot_cache)
        for idx, comp in zip(indices, compressed):
            cache_list[idx]["payload"] = comp.tolist()
        self._hot_cache = deque(cache_list, maxlen=self.capacity)

        logger.info("compress_hot_cache: compressed %d vectors.", len(vectors))
        return "ok"

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self._db.close()
        logger.info("ChaosSparkMemory closed.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _persist(self, record: Dict[str, Any]) -> None:
        payload_str = json.dumps(record["payload"], default=str)
        self._db.execute(
            """
            INSERT OR REPLACE INTO memory_records (key, payload, timestamp, chaos_index)
            VALUES (?, ?, ?, ?)
            """,
            (record["key"], payload_str, record["timestamp"], record["chaos_index"]),
        )
        self._db.commit()
