# united-maSTERS

A Python toolkit for audio mastering, release management, and the **VOS v0.5.0** AI synthesis pipeline.

## VOS v0.5.0

Three new runtime modules live under `vos_core/`:

| Module | Purpose |
|---|---|
| `tensor_accel.TensorEngine` | NumPy/PyTorch tensor ops with automatic GPU routing |
| `chaos_spark_memory.ChaosSparkMemory` | Chaos-indexed episodic memory with SQLite persistence |
| `victorian_genome.VictorianGenome` | Lineage-tracked generative genome (JSON audit trail) |

`SyntheticCore` wires all three together into a single runtime.

See **[docs/vos_v0.5.0.md](docs/vos_v0.5.0.md)** for full documentation including GPU setup, storage locations, and usage examples.