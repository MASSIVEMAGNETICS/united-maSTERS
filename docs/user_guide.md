# UnitedMasters Release Workbench User Guide

Welcome to the UnitedMasters Release Workbench! This guide will help you understand the core concepts, get set up, and start mastering and releasing your audio files.

## Overview

UnitedMasters provides an end-to-end local-first pipeline for audio mastering, encoding, quality control (QC), and metadata generation. It leverages advanced signal processing and analysis to ensure your music is ready for release across multiple streaming platforms.

The system is comprised of two main interfaces:
1. **Command Line Interface (CLI)**: A powerful, scriptable tool for batch processing and detailed analysis.
2. **Web UI**: A user-friendly web interface for initiating pipeline jobs and viewing results interactively.

Additionally, UnitedMasters integrates **VOS v0.5.0**, an AI synthesis pipeline. Refer to the [VOS v0.5.0 Documentation](vos_v0.5.0.md) for details on that system.

## Setup and Installation

### Prerequisites
- Python 3.8 or higher.
- (Optional but recommended) A virtual environment.

### Installation

Clone the repository and install the package in editable mode:

```bash
git clone https://github.com/your-username/united-masters.git
cd united-masters
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

This will make the `united-masters` CLI command globally available within your virtual environment.

## Key Concepts

### The Pipeline
The core of UnitedMasters is its release pipeline (`united_masters/pipeline.py`), which orchestrates several steps on a directory of audio files:
1. **Ingest**: Scans the input folder, detecting duplicates and unsupported formats.
2. **Analysis**: Evaluates LUFS, true peak, frequency response, and crest factor.
3. **Mastering & Recommendations**: Analyzes audio and suggests appropriate mastering presets.
4. **Encoding**: Encodes source audio to multiple target formats (e.g., MP3, WAV, FLAC).
5. **Quality Control (QC)**: Runs strict checks against clipping, DC offset, extreme frequencies, and metadata anomalies.
6. **Manifest Generation**: Generates release metadata (`manifest.json` and `manifest.csv`).

### Mastering Presets
Presets dictate the target loudness (LUFS) and true peak constraints during processing. Some common presets include:
- `streaming_safe`: Optimized for platforms like Spotify and Apple Music (-14 LUFS, -1 dBTP).
- `loud_modern_rap`: Pushed for higher perceived loudness (-9 LUFS).
- `warm_hip_hop`: Focus on low-end warmth and punch.
- `clean_dynamic`: Preserves wide dynamic range for acoustic or classical tracks.

You can view all available presets via the CLI:
```bash
united-masters presets
```

## Using the Software

### CLI Workflow
The CLI is ideal for developers and automated workflows. Here is a typical workflow:

1. **Analyze a folder:** Check the characteristics of your raw mixes.
   ```bash
   united-masters analyze path/to/mixes/
   ```
2. **Run QC:** Verify if the mixes pass basic quality checks.
   ```bash
   united-masters qc path/to/mixes/
   ```
3. **Process Release:** Run the full pipeline (analysis, mastering recommendations, encoding, QC, manifest creation).
   ```bash
   united-masters process path/to/mixes/ --preset streaming_safe --formats wav_16_44,mp3_320,flac
   ```

For detailed CLI usage, see the [CLI Reference](cli_reference.md).

### Web UI Workflow
The Web UI provides a visual dashboard for the pipeline.

1. Start the application:
   ```bash
   python united_masters/web/app.py
   ```
2. Open your browser to `http://127.0.0.1:5000`.
3. Enter the absolute path to your input directory containing audio files.
4. Select your desired mastering preset and output formats.
5. Click **Run Pipeline** and watch the job progress on the results page.

For details on the Web UI, see the [Web UI Guide](web_ui.md).

## Support
If you encounter any issues, verify that your directory paths are correct and that you have the required permissions. System directories (e.g., `/etc`, `/bin`) are blocked by the Web UI for security reasons.