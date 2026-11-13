# UnitedMasters CLI Reference

The `united-masters` command-line interface (CLI) provides a set of tools to analyze, quality-check, and process audio releases. It is built using the Click framework.

## Global Options

- `--version`: Show the version and exit.
- `--help`: Show the help message.

---

## Commands

### `process`
Runs the full release pipeline on a specified input directory. This includes ingest, analysis, quality control (QC), mastering preset recommendation, encoding, and manifest generation.

**Usage:**
```bash
united-masters process [OPTIONS] INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: The path to the directory containing the source audio files. Must exist.

**Options:**
- `-o, --output TEXT`: Output directory. (Default: `<INPUT_DIR>/_output`)
- `-p, --preset [streaming_safe|loud_modern_rap|warm_hip_hop|vocal_forward|trap_808_heavy|clean_dynamic]`: Mastering preset family to apply. (Default: `streaming_safe`)
- `-f, --formats TEXT`: Comma-separated list of export format keys (e.g., `wav_16_44,mp3_320,flac`). (Default: `wav_16_44,mp3_320,flac`)
- `--no-qc`: Skip the quality control (QC) checks.
- `--no-manifest`: Skip manifest (`manifest.json`/`manifest.csv`) generation.
- `--no-promo`: Skip promo asset generation.

**Example:**
```bash
united-masters process ./my_album --preset warm_hip_hop --formats wav_24_48,mp3_320
```

---

### `analyze`
Analyzes audio files in the specified directory and prints a detailed technical report for each file (duration, sample rate, bit depth, LUFS, true peak, crest factor, clipping, DC offset, etc.).

**Usage:**
```bash
united-masters analyze INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: The directory containing the audio files to analyze.

**Example:**
```bash
united-masters analyze ./my_mixes
```

---

### `qc`
Runs strict Quality Control (QC) checks on audio files in the specified directory. This checks for issues like clipping, extreme DC offset, loudness non-compliance, and album-level consistency.

**Usage:**
```bash
united-masters qc INPUT_DIR
```

**Arguments:**
- `INPUT_DIR`: The directory containing the audio files to verify.

**Example:**
```bash
united-masters qc ./my_masters
```

---

### `presets`
Lists all available mastering presets configured in the system along with their descriptions, targets, and signal chain stages.

**Usage:**
```bash
united-masters presets
```

**Example:**
```bash
united-masters presets
```