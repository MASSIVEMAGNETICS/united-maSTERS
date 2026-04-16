"""
victorian_genome.py — VOS v0.5.0 lineage-tracked generative genome.

Maintains a mutable *genome* (an ordered sequence of named genes) with
full ancestry tracking stored in a JSON lineage file.  Each mutation or
crossover event is timestamped and appended to the lineage, enabling
complete reproducibility and audit trails.

The lineage file defaults to ``vos_lineage.json`` in the current working
directory and can be overridden via the ``lineage_path`` constructor
parameter.
"""

from __future__ import annotations

import copy
import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_LINEAGE = "vos_lineage.json"


class VictorianGenome:
    """Generative genome with immutable lineage tracking.

    Parameters
    ----------
    genes:
        Initial gene sequence.  Each element should be a
        JSON-serialisable value (str, float, dict, …).
    genome_id:
        Unique identifier for this genome.  Auto-generated (UUID4) when
        not provided.
    lineage_path:
        Path to the JSON file where the full lineage history is
        persisted.  Defaults to ``"vos_lineage.json"``.
    """

    def __init__(
        self,
        genes: Optional[List[Any]] = None,
        genome_id: Optional[str] = None,
        lineage_path: str = _DEFAULT_LINEAGE,
    ) -> None:
        self.genome_id: str = genome_id or str(uuid.uuid4())
        self.genes: List[Any] = list(genes or [])
        self.lineage_path = Path(lineage_path)
        self._lineage: List[Dict[str, Any]] = []

        self._load_lineage()
        self._record_event("init", {"genes": copy.deepcopy(self.genes)})

        logger.info(
            "VictorianGenome ready — id=%s genes=%d lineage=%s",
            self.genome_id,
            len(self.genes),
            self.lineage_path,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def mutate(
        self,
        index: int,
        value: Any,
        *,
        reason: str = "",
    ) -> "VictorianGenome":
        """Replace the gene at *index* with *value*.

        Parameters
        ----------
        index:
            Position in :attr:`genes` to overwrite.
        value:
            New gene value (must be JSON-serialisable).
        reason:
            Human-readable description of why this mutation occurred.

        Returns
        -------
        VictorianGenome
            *self*, to allow chaining.
        """
        old = self.genes[index]
        self.genes[index] = value
        self._record_event(
            "mutate",
            {"index": index, "old": old, "new": value, "reason": reason},
        )
        logger.debug("VictorianGenome.mutate index=%d %r -> %r", index, old, value)
        return self

    def append_gene(self, value: Any, *, reason: str = "") -> "VictorianGenome":
        """Append a new gene to the end of the sequence."""
        self.genes.append(value)
        self._record_event("append", {"value": value, "reason": reason})
        return self

    def crossover(
        self,
        other: "VictorianGenome",
        point: Optional[int] = None,
    ) -> "VictorianGenome":
        """Single-point crossover with *other*, producing a new child genome.

        Parameters
        ----------
        other:
            Second parent genome.
        point:
            Crossover index.  Defaults to the midpoint of the shorter
            parent.

        Returns
        -------
        VictorianGenome
            A brand-new genome whose genes are composed from both parents.
        """
        if point is None:
            point = min(len(self.genes), len(other.genes)) // 2

        child_genes = self.genes[:point] + other.genes[point:]
        child = VictorianGenome(
            genes=child_genes,
            lineage_path=str(self.lineage_path),
        )
        child._record_event(
            "crossover",
            {
                "parent_a": self.genome_id,
                "parent_b": other.genome_id,
                "point": point,
            },
        )
        logger.info(
            "VictorianGenome.crossover parents=(%s, %s) -> child=%s",
            self.genome_id,
            other.genome_id,
            child.genome_id,
        )
        return child

    def express(self) -> Dict[str, Any]:
        """Return a serialisable snapshot of the current genome state."""
        return {
            "genome_id": self.genome_id,
            "genes": copy.deepcopy(self.genes),
            "gene_count": len(self.genes),
            "lineage_events": len(self._lineage),
        }

    def lineage(self) -> List[Dict[str, Any]]:
        """Return the full lineage event list (read-only copy)."""
        return copy.deepcopy(self._lineage)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_event(self, event_type: str, detail: Dict[str, Any]) -> None:
        entry = {
            "genome_id": self.genome_id,
            "event": event_type,
            "timestamp": time.time(),
            "detail": detail,
        }
        self._lineage.append(entry)
        self._save_lineage()

    def _save_lineage(self) -> None:
        try:
            existing: List[Dict[str, Any]] = []
            if self.lineage_path.exists():
                try:
                    existing = json.loads(self.lineage_path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    existing = []
            # Merge: keep other genomes' records, replace ours
            others = [e for e in existing if e.get("genome_id") != self.genome_id]
            merged = others + self._lineage
            self.lineage_path.write_text(
                json.dumps(merged, indent=2, default=str),
                encoding="utf-8",
            )
        except OSError as exc:
            logger.warning("VictorianGenome: could not save lineage — %s", exc)

    def _load_lineage(self) -> None:
        if self.lineage_path.exists():
            try:
                all_events = json.loads(self.lineage_path.read_text(encoding="utf-8"))
                self._lineage = [
                    e for e in all_events if e.get("genome_id") == self.genome_id
                ]
            except (json.JSONDecodeError, OSError):
                self._lineage = []
