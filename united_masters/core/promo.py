"""
promo.py — Promo asset generation: teasers, tracklists, captions, launch checklists.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.artwork import ArtworkInfo
from united_masters.core.manifest import ReleaseManifest
from united_masters.core.metadata import TrackMetadata
from united_masters.core.qc import QCReport


@dataclass
class PromoAssets:
    tracklist_text_path: Optional[str] = None
    caption_path: Optional[str] = None
    teaser_paths: List[str] = field(default_factory=list)
    checklist_path: Optional[str] = None


def extract_teaser_snippet(
    audio_path: str,
    output_path: str,
    start_sec: float = 30.0,
    duration_sec: float = 30.0,
) -> bool:
    """
    Extract a *duration_sec* snippet starting at *start_sec* from *audio_path*
    and write it to *output_path* as MP3.

    Returns True on success, False on failure.
    """
    try:
        from pydub import AudioSegment  # noqa: PLC0415

        audio = AudioSegment.from_file(audio_path)
        total_ms = len(audio)
        start_ms = int(start_sec * 1000)
        end_ms = int((start_sec + duration_sec) * 1000)

        # Clamp to file length
        start_ms = min(start_ms, max(0, total_ms - 1000))
        end_ms = min(end_ms, total_ms)

        snippet = audio[start_ms:end_ms]

        # Fade in/out for a polished preview
        fade_ms = min(2000, len(snippet) // 4)
        snippet = snippet.fade_in(fade_ms).fade_out(fade_ms)

        os.makedirs(Path(output_path).parent, exist_ok=True)
        snippet.export(output_path, format="mp3", bitrate="192k")
        return True
    except Exception:
        return False


def generate_tracklist_text(manifest: ReleaseManifest) -> str:
    """Return a plain-text tracklist string suitable for descriptions / bios."""
    lines: List[str] = [
        f"{manifest.release_title}",
        f"by {manifest.artist}",
        "",
        "Tracklist:",
    ]
    for t in manifest.tracks:
        dur = _format_duration(t.duration_seconds)
        title = t.title or t.filename or f"Track {t.track_number}"
        explicit_marker = " [Explicit]" if t.explicit else ""
        lines.append(f"  {t.track_number:02d}. {title}{explicit_marker}  ({dur})")

    total = _format_duration(manifest.total_duration_seconds)
    lines.append(f"\nTotal runtime: {total}")
    return "\n".join(lines)


def generate_release_caption(
    metadata: TrackMetadata,
    analysis: Optional[AudioAnalysis] = None,
) -> str:
    """Generate a short social media caption for a single track or release."""
    title = metadata.title or "New Track"
    artist = metadata.artist or "Artist"
    genre = metadata.genre or ""
    year = metadata.year or ""

    parts = [f'🎵 "{title}" — {artist}']
    if genre:
        parts.append(f"#{genre.replace(' ', '')}")
    if year:
        parts.append(year)
    if analysis and analysis.estimated_bpm:
        parts.append(f"{analysis.estimated_bpm:.0f} BPM")

    parts.append("#NewMusic #Release")

    return "  ".join(parts)


def generate_launch_checklist(
    manifest: ReleaseManifest,
    qc_reports: List[QCReport],
    artwork_info: Optional[ArtworkInfo],
) -> List[Dict[str, Any]]:
    """
    Build a human-readable launch checklist.

    Each item: {"item": str, "status": "done"|"warning"|"todo", "notes": str}
    """
    checklist: List[Dict[str, Any]] = []

    def item(name: str, status: str, notes: str = "") -> Dict[str, Any]:
        return {"item": name, "status": status, "notes": notes}

    # --- Artwork ---
    if artwork_info is None:
        checklist.append(item("Upload release artwork", "todo", "No artwork found."))
    elif artwork_info.warnings:
        checklist.append(item("Review artwork", "warning", "; ".join(artwork_info.warnings)))
    else:
        checklist.append(item("Artwork validated", "done", f"{artwork_info.width}×{artwork_info.height} {artwork_info.format}"))

    # --- QC ---
    errors = sum(r.error_count for r in qc_reports)
    warnings = sum(r.warning_count for r in qc_reports)
    if errors:
        checklist.append(item("Fix QC errors", "warning", f"{errors} error(s) must be resolved before delivery."))
    else:
        checklist.append(item("QC passed — no errors", "done"))
    if warnings:
        checklist.append(item("Review QC warnings", "warning", f"{warnings} warning(s) to review."))

    # --- Metadata ---
    tracks_no_title = [t for t in manifest.tracks if not t.title]
    tracks_no_isrc = [t for t in manifest.tracks if not t.isrc]
    if tracks_no_title:
        checklist.append(item("Add missing track titles", "todo",
                               f"{len(tracks_no_title)} track(s) missing title."))
    else:
        checklist.append(item("All track titles present", "done"))

    if tracks_no_isrc:
        checklist.append(item("Register ISRCs", "todo",
                               f"{len(tracks_no_isrc)} track(s) missing ISRC. Register at your PRO or label."))
    else:
        checklist.append(item("All ISRCs present", "done"))

    # --- UPC ---
    if not manifest.upc:
        checklist.append(item("Obtain UPC/EAN barcode", "todo",
                               "Required by all major distributors for album releases."))
    else:
        checklist.append(item("UPC/EAN present", "done", manifest.upc))

    # --- Explicit content ---
    explicit_tracks = [t for t in manifest.tracks if t.explicit]
    if explicit_tracks:
        checklist.append(item("Mark release as Explicit", "warning",
                               f"{len(explicit_tracks)} track(s) flagged as explicit. Ensure distributor settings are correct."))

    # --- Distribution ---
    checklist.append(item("Choose distributor and upload files", "todo",
                           "DistroKid, TuneCore, CD Baby, etc."))
    checklist.append(item("Set release date (allow 5–7 business days)", "todo"))
    checklist.append(item("Pitch to editorial playlists (at least 7 days before release)", "todo"))
    checklist.append(item("Prepare social media content", "todo"))
    checklist.append(item("Set up pre-save links", "todo"))
    checklist.append(item("Brief team / publicist", "todo"))

    return checklist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_duration(seconds: float) -> str:
    total_s = int(round(seconds))
    m, s = divmod(total_s, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
