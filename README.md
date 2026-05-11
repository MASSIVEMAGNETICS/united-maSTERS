# united-maSTERS

A Python toolkit for audio mastering, release management, and the **VOS v0.5.0** AI synthesis pipeline.

UnitedMasters provides a local-first music release workbench with tools for mastering, encoding, quality control, and delivery. It includes a powerful CLI and a web-based UI for processing releases.

## Documentation

- **[User Guide](docs/user_guide.md)**: Comprehensive instructions on setup, configuration, and using the project.
- **[CLI Reference](docs/cli_reference.md)**: Detailed documentation for the `united-masters` CLI commands.
- **[Web UI Guide](docs/web_ui.md)**: Instructions on running and using the Flask Web UI.
- **[VOS v0.5.0 Reference](docs/vos_v0.5.0.md)**: Details on the AI synthesis pipeline.

## Installation

```bash
# Clone the repository
git clone https://github.com/your-username/united-masters.git
cd united-masters

# Create and activate a virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install the package and its dependencies
pip install -e .
```

## Quick Start

### Command Line Interface
Run the release pipeline on a directory containing audio files:
```bash
united-masters process path/to/your/audio_folder
```

### Web UI
Start the local Flask server for the Web UI:
```bash
python united_masters/web/app.py
```
Then navigate to `http://127.0.0.1:5000` in your browser.

## Public Demo Setup
A Dockerized demo setup is available for running the Web UI in a production-like environment using Gunicorn.
```bash
./demo.sh
```

---

## VOS v0.5.0

Three new runtime modules live under `vos_core/`:

| Module | Purpose |
|---|---|
| `tensor_accel.TensorEngine` | NumPy/PyTorch tensor ops with automatic GPU routing |
| `chaos_spark_memory.ChaosSparkMemory` | Chaos-indexed episodic memory with SQLite persistence |
| `victorian_genome.VictorianGenome` | Lineage-tracked generative genome (JSON audit trail) |

`SyntheticCore` wires all three together into a single runtime.

See **[docs/vos_v0.5.0.md](docs/vos_v0.5.0.md)** for full documentation including GPU setup, storage locations, and usage examples.