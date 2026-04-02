"""
encode.py — Delivery encode matrix using pydub + ffmpeg.

IMPORTANT CAVEAT: Re-encoding a lossy source (e.g. 128 kbps MP3) to a higher
bitrate or greater bit-depth does NOT restore the lost audio information. The
output file will be larger but no better than the source. This module surfaces
that warning so users are clearly informed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from pydub import AudioSegment
except ImportError:  # pragma: no cover
    AudioSegment = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Supported output format matrix
# ---------------------------------------------------------------------------

SUPPORTED_OUTPUT_FORMATS: Dict[str, Dict[str, Any]] = {
    "wav_16_44": {
        "format": "wav",
        "bit_depth": 16,
        "sample_rate": 44100,
        "description": "CD-quality WAV — universal compatibility, standard delivery.",
    },
    "wav_24_44": {
        "format": "wav",
        "bit_depth": 24,
        "sample_rate": 44100,
        "description": "24-bit / 44.1 kHz WAV — high-res delivery at standard sample rate.",
    },
    "wav_24_48": {
        "format": "wav",
        "bit_depth": 24,
        "sample_rate": 48000,
        "description": "24-bit / 48 kHz WAV — standard for sync/video delivery.",
    },
    "wav_24_96": {
        "format": "wav",
        "bit_depth": 24,
        "sample_rate": 96000,
        "description": "24-bit / 96 kHz WAV — audiophile / archival quality.",
    },
    "mp3_128": {
        "format": "mp3",
        "bitrate": "128k",
        "mode": "cbr",
        "description": "128 kbps CBR MP3 — acceptable for preview / streaming fallback.",
    },
    "mp3_192": {
        "format": "mp3",
        "bitrate": "192k",
        "mode": "cbr",
        "description": "192 kbps CBR MP3 — good quality, widely compatible.",
    },
    "mp3_256": {
        "format": "mp3",
        "bitrate": "256k",
        "mode": "cbr",
        "description": "256 kbps CBR MP3 — near-transparent for most listeners.",
    },
    "mp3_320": {
        "format": "mp3",
        "bitrate": "320k",
        "mode": "cbr",
        "description": "320 kbps CBR MP3 — highest standard MP3 quality.",
    },
    "mp3_vbr": {
        "format": "mp3",
        "bitrate": "V0",
        "mode": "vbr",
        "description": "VBR V0 MP3 — variable bitrate, transparent quality, smaller file.",
    },
    "flac": {
        "format": "flac",
        "description": "Lossless FLAC — perfect reconstruction, ~50% of uncompressed WAV size.",
    },
}

# Lossy source extensions that trigger an up-conversion warning
_LOSSY_EXTENSIONS = {".mp3", ".m4a", ".ogg", ".aac"}

# Format keys that represent high-res or high-bitrate outputs
_HIGH_RES_FORMATS = {"wav_24_44", "wav_24_48", "wav_24_96", "mp3_320", "mp3_vbr", "flac"}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class EncodeResult:
    output_path: str
    format_key: str
    success: bool
    warning: Optional[str] = None
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encode_file(
    input_path: str,
    output_dir: str,
    format_key: str,
    filename_suffix: str = "",
) -> EncodeResult:
    """
    Encode *input_path* to the format described by *format_key* and write the
    result into *output_dir*.

    Returns an EncodeResult even on failure (success=False with error message).
    """
    if format_key not in SUPPORTED_OUTPUT_FORMATS:
        return EncodeResult(
            output_path="",
            format_key=format_key,
            success=False,
            error=f"Unknown format key '{format_key}'. Valid keys: {list(SUPPORTED_OUTPUT_FORMATS)}",
        )

    fmt = SUPPORTED_OUTPUT_FORMATS[format_key]
    input_ext = Path(input_path).suffix.lower()
    stem = Path(input_path).stem
    output_ext = "." + fmt["format"]
    out_filename = f"{stem}{filename_suffix}{output_ext}"
    output_path = str(Path(output_dir) / out_filename)

    # Quality ceiling warning
    warning: Optional[str] = _quality_ceiling_warning(input_path, format_key)

    try:
        if AudioSegment is None:
            raise ImportError("pydub is not installed. Install it with: pip install pydub")

        os.makedirs(output_dir, exist_ok=True)
        audio = AudioSegment.from_file(input_path)

        export_kwargs: Dict[str, Any] = {}

        if fmt["format"] == "mp3":
            if fmt.get("mode") == "vbr":
                export_kwargs["parameters"] = ["-q:a", "0"]
            else:
                export_kwargs["bitrate"] = fmt.get("bitrate", "320k")

        elif fmt["format"] == "wav":
            sample_rate = fmt.get("sample_rate", 44100)
            bit_depth = fmt.get("bit_depth", 16)
            audio = audio.set_frame_rate(sample_rate)
            audio = audio.set_sample_width(bit_depth // 8)

        elif fmt["format"] == "flac":
            pass  # pydub exports as-is for flac

        audio.export(output_path, format=fmt["format"], **export_kwargs)

        return EncodeResult(
            output_path=output_path,
            format_key=format_key,
            success=True,
            warning=warning,
        )

    except ImportError:
        return EncodeResult(
            output_path=output_path,
            format_key=format_key,
            success=False,
            warning=warning,
            error="pydub is not installed. Install it with: pip install pydub",
        )
    except Exception as exc:
        return EncodeResult(
            output_path=output_path,
            format_key=format_key,
            success=False,
            warning=warning,
            error=str(exc),
        )


def encode_batch(
    input_path: str,
    output_dir: str,
    format_keys: List[str],
) -> List[EncodeResult]:
    """Encode *input_path* into every format listed in *format_keys*."""
    return [encode_file(input_path, output_dir, fk) for fk in format_keys]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _quality_ceiling_warning(input_path: str, format_key: str) -> Optional[str]:
    """
    Return a warning when a lossy source is being up-converted to a high-res
    output format. The conversion cannot restore discarded frequency content.
    """
    ext = Path(input_path).suffix.lower()
    if ext not in _LOSSY_EXTENSIONS:
        return None
    if format_key not in _HIGH_RES_FORMATS:
        return None

    fmt_desc = SUPPORTED_OUTPUT_FORMATS[format_key].get("description", format_key)
    return (
        f"⚠  SOURCE QUALITY CEILING: Input is a lossy {ext.upper()} file. "
        f"Encoding to '{format_key}' ({fmt_desc}) will NOT recover the frequency "
        f"information discarded during the original lossy compression. "
        f"The output will be larger but not higher fidelity. "
        f"Use a lossless master source if available."
    )
