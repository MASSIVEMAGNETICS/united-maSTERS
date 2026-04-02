"""
ingest.py — Scan a folder for audio files and detect basic source quality issues.

IMPORTANT CAVEAT: Converting a low-bitrate MP3 to 320 kbps MP3 or 24-bit WAV does NOT
restore lost detail. The source quality ceiling cannot be exceeded by re-encoding.
Warnings are surfaced here so downstream steps can inform the user.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

SUPPORTED_FORMATS: List[str] = [".wav", ".flac", ".mp3", ".aiff", ".aif", ".m4a", ".ogg"]

# Bitrate thresholds below which lossy sources are considered low-quality
_LOW_QUALITY_BITRATE_KBPS = 192


@dataclass
class AudioFile:
    path: str
    filename: str
    extension: str
    file_size_mb: float
    is_supported: bool
    # Populated by optional deeper inspection (mutagen)
    bitrate_kbps: Optional[int] = None
    detected_format: Optional[str] = None

    def __post_init__(self) -> None:
        self.extension = self.extension.lower()

    @property
    def stem(self) -> str:
        return Path(self.filename).stem


def scan_folder(folder_path: str) -> List[AudioFile]:
    """Recursively scan *folder_path* and return AudioFile objects for every file found."""
    root = Path(folder_path)
    if not root.exists():
        raise FileNotFoundError(f"Input folder not found: {folder_path}")
    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {folder_path}")

    audio_files: List[AudioFile] = []
    for file_path in sorted(root.rglob("*")):
        if not file_path.is_file():
            continue
        ext = file_path.suffix.lower()
        size_mb = file_path.stat().st_size / (1024 * 1024)
        af = AudioFile(
            path=str(file_path),
            filename=file_path.name,
            extension=ext,
            file_size_mb=round(size_mb, 3),
            is_supported=ext in SUPPORTED_FORMATS,
        )
        _try_read_bitrate(af)
        audio_files.append(af)

    return audio_files


def _try_read_bitrate(af: AudioFile) -> None:
    """Attempt to read bitrate via mutagen; fail silently if unavailable."""
    try:
        import mutagen  # noqa: PLC0415

        tag = mutagen.File(af.path)
        if tag is None:
            return
        info = getattr(tag, "info", None)
        if info is None:
            return
        bitrate = getattr(info, "bitrate", None)
        if bitrate:
            af.bitrate_kbps = bitrate // 1000
    except Exception:  # pragma: no cover
        pass


def get_source_quality_warning(audio_file: AudioFile) -> Optional[str]:
    """
    Return a warning string if the source file has a quality ceiling that would make
    up-conversion meaningless — e.g. an MP3 encoded below 192 kbps.

    Re-encoding a degraded lossy file at a higher bitrate or bit-depth only makes the
    file larger; it cannot recover the discarded frequency information.
    """
    lossy_extensions = {".mp3", ".m4a", ".ogg"}
    ext = audio_file.extension

    if ext not in lossy_extensions:
        return None  # Lossless source — no ceiling warning needed

    bitrate = audio_file.bitrate_kbps
    if bitrate is not None and bitrate < _LOW_QUALITY_BITRATE_KBPS:
        return (
            f"⚠  SOURCE QUALITY CEILING: '{audio_file.filename}' is a {ext.upper()} "
            f"encoded at only {bitrate} kbps. Converting to 320 kbps MP3 or 24-bit WAV "
            f"will NOT restore lost detail — the source ceiling is {bitrate} kbps. "
            f"Use a higher-quality master if available."
        )

    if ext in lossy_extensions and bitrate is None:
        return (
            f"⚠  SOURCE QUALITY UNKNOWN: '{audio_file.filename}' is a lossy {ext.upper()} "
            f"file. If its original bitrate was below {_LOW_QUALITY_BITRATE_KBPS} kbps, "
            f"up-converting will not recover lost detail. Verify your source quality."
        )

    return None


def detect_duplicates(files: List[AudioFile]) -> List[List[AudioFile]]:
    """
    Group files whose stems are identical (case-insensitive) — likely duplicates.
    Returns a list of groups; single-file groups are excluded.
    """
    from collections import defaultdict

    groups: dict = defaultdict(list)
    for af in files:
        key = af.stem.strip().lower()
        groups[key].append(af)

    return [group for group in groups.values() if len(group) > 1]
