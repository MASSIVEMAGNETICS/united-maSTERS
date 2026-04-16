"""
vos_core — VOS v0.5.0 runtime modules.

Exposes:
    TensorEngine      — hardware-accelerated tensor operations
    ChaosSparkMemory  — chaos-theory-inspired episodic memory store
    VictorianGenome   — lineage-tracked generative genome
    SyntheticCore     — unified runtime that wires the above modules together
"""

from vos_core.tensor_accel import TensorEngine
from vos_core.chaos_spark_memory import ChaosSparkMemory
from vos_core.victorian_genome import VictorianGenome
from vos_core.synthetic_core import SyntheticCore

__all__ = [
    "TensorEngine",
    "ChaosSparkMemory",
    "VictorianGenome",
    "SyntheticCore",
]
