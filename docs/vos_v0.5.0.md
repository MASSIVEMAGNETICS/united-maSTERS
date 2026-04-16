# VOS v0.5.0 — Module Reference

VOS v0.5.0 adds three new runtime modules under `vos_core/` and a unified
`SyntheticCore` that wires them together.

---

## Module overview

### `vos_core.tensor_accel.TensorEngine`

Hardware-accelerated tensor operations.

| Feature | Detail |
|---|---|
| Default backend | NumPy (CPU) |
| GPU backend | PyTorch (CUDA or Windows DirectML) when `torch` is importable |
| Key methods | `to_tensor`, `from_tensor`, `dot`, `batch_compress`, `stats` |

`batch_compress` performs random-projection dimensionality reduction on a
list of vectors, using the GPU backend when available.

### `vos_core.chaos_spark_memory.ChaosSparkMemory`

Chaos-theory-inspired episodic memory store.

| Feature | Detail |
|---|---|
| Chaotic index | Logistic map (r = 3.9) |
| Hot cache | In-memory `deque` capped at `capacity` entries |
| Persistence | SQLite — see **Storage locations** below |
| Key methods | `ingest`, `recall`, `status`, `compress_hot_cache`, `close` |

### `vos_core.victorian_genome.VictorianGenome`

Lineage-tracked generative genome.

| Feature | Detail |
|---|---|
| Gene sequence | Ordered list of JSON-serialisable values |
| Mutation | `mutate(index, value)` — replaces a single gene |
| Crossover | `crossover(other)` — single-point crossover, returns a child genome |
| Lineage | Every event is timestamped and appended to a JSON file |
| Key methods | `mutate`, `append_gene`, `crossover`, `express`, `lineage` |

---

## Storage locations

| Artefact | Default path | Override parameter |
|---|---|---|
| SQLite memory DB | `vos_memory.db` (cwd) | `ChaosSparkMemory(db_path=…)` |
| Lineage JSON | `vos_lineage.json` (cwd) | `VictorianGenome(lineage_path=…)` |

To store both files in a dedicated directory:

```python
from vos_core import SyntheticCore

core = SyntheticCore(
    db_path="data/vos_memory.db",
    lineage_path="data/vos_lineage.json",
)
```

---

## Enabling GPU routing

### NVIDIA (CUDA)

```bash
pip install torch>=2.1.0          # CUDA build from https://pytorch.org
```

`TensorEngine` detects `torch.cuda.is_available()` automatically.

### Windows DirectML (AMD / Intel GPU via DirectX 12)

```bash
pip install torch torch-directml
```

`TensorEngine` falls back to DirectML when CUDA is not present:

```python
import torch_directml
from vos_core import TensorEngine

engine = TensorEngine(device=torch_directml.device())
```

### CPU-only (no GPU)

No additional packages are required.  Install just:

```bash
pip install numpy>=1.26.4
```

VOS automatically uses the NumPy backend whenever `torch` is not importable.

---

## Basic usage example

```python
from vos_core import SyntheticCore

# Instantiate the unified runtime (all defaults → CPU / NumPy backend)
core = SyntheticCore(
    memory_capacity=256,
    compression_ratio=0.5,
    compress_every=10,   # compress hot cache every 10 calls
)

# Process a sample payload
result = core.process({"audio_features": [0.1, 0.4, 0.9, 0.2]})

print(result["memory_key"])     # SHA-256 hash key assigned by ChaosSparkMemory
print(result["memory_status"])  # "stored" or "compressed:ok"
print(result["genome"])         # current VictorianGenome expression dict

# Inspect memory state
print(core.memory.status())

# Clean up (closes SQLite connection)
core.close()
```

### Using sub-modules directly

```python
from vos_core.tensor_accel import TensorEngine
from vos_core.chaos_spark_memory import ChaosSparkMemory
from vos_core.victorian_genome import VictorianGenome

engine = TensorEngine()
memory = ChaosSparkMemory(capacity=128, compression_ratio=0.5)
genome = VictorianGenome(genes=["A", "B", "C"])

key = memory.ingest([0.5, 0.3, 0.8])
memory.compress_hot_cache(tensor_engine=engine)

genome.mutate(1, "B2", reason="first mutation")
print(genome.express())

memory.close()
```

---

## Windows 10 compatibility notes

* No hard dependency on GPU hardware — all modules run on plain CPU.
* SQLite ships with Python's standard library; no extra install needed.
* The `torch` import is always guarded; missing `torch` never raises
  `ImportError` at module load time.
* Paths use `pathlib.Path` throughout for cross-platform correctness.
