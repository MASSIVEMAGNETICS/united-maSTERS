"""
metadata.py — Read, write, validate and clean track metadata using mutagen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Words that should stay lowercase in title case (unless first/last word)
_LOWERCASE_WORDS = {
    "a", "an", "the", "and", "but", "or", "nor", "for", "yet", "so",
    "at", "by", "in", "of", "on", "to", "up", "as", "if", "vs",
}

_EXPLICIT_KEYWORDS = [
    "fuck", "shit", "bitch", "nigga", "nigger", "ass", "dick", "pussy",
    "cock", "cunt", "whore", "slut", "motherfuck", "hoe",
]


@dataclass
class TrackMetadata:
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    track_number: Optional[int] = None
    total_tracks: Optional[int] = None
    year: Optional[str] = None
    genre: Optional[str] = None
    isrc: Optional[str] = None
    label: Optional[str] = None
    copyright: Optional[str] = None
    lyrics: Optional[str] = None
    explicit: bool = False
    has_artwork: bool = False
    raw_tags: Dict[str, Any] = field(default_factory=dict)


def read_metadata(file_path: str) -> TrackMetadata:
    """Read metadata from *file_path* using mutagen."""
    meta = TrackMetadata()

    try:
        import mutagen  # noqa: PLC0415
        from mutagen.id3 import ID3NoHeaderError  # noqa: PLC0415
    except ImportError:
        meta.raw_tags = {"error": "mutagen not installed"}
        return meta

    try:
        tag = mutagen.File(file_path, easy=True)
    except Exception as exc:
        meta.raw_tags = {"error": str(exc)}
        return meta

    if tag is None:
        return meta

    def _get(key: str) -> Optional[str]:
        val = tag.get(key)
        if val and isinstance(val, (list, tuple)):
            return str(val[0]).strip() or None
        return None

    meta.title = _get("title")
    meta.artist = _get("artist")
    meta.album = _get("album")
    meta.year = _get("date") or _get("year")
    meta.genre = _get("genre")
    meta.isrc = _get("isrc")
    meta.label = _get("organization") or _get("label")
    meta.copyright = _get("copyright")
    meta.lyrics = _get("lyrics") or _get("unsyncedlyrics")

    tracknumber = _get("tracknumber")
    if tracknumber:
        parts = str(tracknumber).split("/")
        try:
            meta.track_number = int(parts[0])
        except ValueError:
            pass
        if len(parts) > 1:
            try:
                meta.total_tracks = int(parts[1])
            except ValueError:
                pass

    # Artwork detection (non-easy interface needed)
    try:
        full_tag = mutagen.File(file_path)
        if full_tag is not None:
            meta.has_artwork = _has_artwork(full_tag)
    except Exception:
        pass

    meta.raw_tags = {k: list(v) if hasattr(v, "__iter__") and not isinstance(v, str) else v
                    for k, v in tag.items()}

    meta.explicit = detect_explicit(meta.title or "", meta)

    return meta


def _has_artwork(tag: Any) -> bool:
    """Check for embedded artwork in a mutagen tag object."""
    # ID3 (MP3)
    if hasattr(tag, "tags") and tag.tags:
        for key in tag.tags:
            if "APIC" in str(key):
                return True
    # FLAC / OGG
    if hasattr(tag, "pictures") and tag.pictures:
        return True
    # MP4
    if hasattr(tag, "get"):
        try:
            covr = tag.get("covr")
            if covr:
                return True
        except Exception:
            pass
    return False


def write_metadata(file_path: str, metadata: TrackMetadata) -> bool:
    """Write *metadata* back to *file_path*. Returns True on success."""
    try:
        import mutagen  # noqa: PLC0415

        tag = mutagen.File(file_path, easy=True)
        if tag is None:
            return False

        if metadata.title:
            tag["title"] = [metadata.title]
        if metadata.artist:
            tag["artist"] = [metadata.artist]
        if metadata.album:
            tag["album"] = [metadata.album]
        if metadata.year:
            tag["date"] = [metadata.year]
        if metadata.genre:
            tag["genre"] = [metadata.genre]
        if metadata.isrc:
            tag["isrc"] = [metadata.isrc]

        if metadata.track_number is not None:
            if metadata.total_tracks is not None:
                tag["tracknumber"] = [f"{metadata.track_number}/{metadata.total_tracks}"]
            else:
                tag["tracknumber"] = [str(metadata.track_number)]

        tag.save()
        return True
    except Exception:
        return False


def clean_title(title: str) -> str:
    """
    Normalise a track title:
    - Collapse multiple spaces
    - Apply music title-case rules
    - Strip leading/trailing whitespace
    """
    if not title:
        return title

    # Collapse whitespace
    title = re.sub(r"\s+", " ", title).strip()

    words = title.split(" ")
    result: List[str] = []
    for i, word in enumerate(words):
        # Always capitalise first and last word; leave small words lowercase otherwise
        if i == 0 or i == len(words) - 1:
            result.append(_capitalise_word(word))
        elif word.lower() in _LOWERCASE_WORDS:
            result.append(word.lower())
        else:
            result.append(_capitalise_word(word))

    return " ".join(result)


def _capitalise_word(word: str) -> str:
    """Capitalise first letter, preserve rest (handles ALL-CAPS initialisms)."""
    if not word:
        return word
    # Preserve all-caps words like "DJ", "NYC"
    if word.isupper() and len(word) > 1:
        return word
    return word[0].upper() + word[1:]


def detect_explicit(title: str, metadata: TrackMetadata) -> bool:
    """Return True if the track appears to contain explicit content."""
    text_to_check = " ".join(
        filter(None, [title, metadata.lyrics])
    ).lower()
    return any(kw in text_to_check for kw in _EXPLICIT_KEYWORDS)


def validate_metadata(metadata: TrackMetadata) -> List[str]:
    """Return a list of issue strings for missing or invalid metadata fields."""
    issues: List[str] = []

    if not metadata.title:
        issues.append("Missing track title.")
    if not metadata.artist:
        issues.append("Missing artist name.")
    if not metadata.album:
        issues.append("Missing album title.")
    if not metadata.year:
        issues.append("Missing release year.")
    if not metadata.genre:
        issues.append("Missing genre.")
    if not metadata.track_number:
        issues.append("Missing track number.")
    if not metadata.isrc:
        issues.append("Missing ISRC code (required by most distributors).")
    if not metadata.has_artwork:
        issues.append("No embedded artwork found.")

    if metadata.year:
        if not re.match(r"^\d{4}$", str(metadata.year)):
            issues.append(f"Year '{metadata.year}' does not look like a 4-digit year.")

    if metadata.isrc:
        # Basic ISRC format check: CC-XXX-YY-NNNNN
        clean = metadata.isrc.replace("-", "").replace(" ", "")
        if not re.match(r"^[A-Z]{2}[A-Z0-9]{3}\d{7}$", clean):
            issues.append(f"ISRC '{metadata.isrc}' does not match expected format (CC-XXX-YY-NNNNN).")

    return issues
