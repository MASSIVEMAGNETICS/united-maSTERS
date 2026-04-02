"""
manifest.py — Release manifest generation and submission kit builder.
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.artwork import ArtworkInfo
from united_masters.core.metadata import TrackMetadata
from united_masters.core.qc import QCReport


@dataclass
class TrackInfo:
    filename: str
    title: Optional[str]
    artist: Optional[str]
    track_number: Optional[int]
    duration_seconds: float
    isrc: Optional[str]
    explicit: bool
    lufs: float
    issues_count: int


@dataclass
class ReleaseManifest:
    release_title: str
    artist: str
    tracks: List[TrackInfo] = field(default_factory=list)
    total_duration_seconds: float = 0.0
    release_date: str = ""
    upc: str = ""
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.release_date:
            self.release_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def generate_manifest(
    metadata_list: List[TrackMetadata],
    analyses: List[AudioAnalysis],
    qc_reports: Optional[List[QCReport]] = None,
    filenames: Optional[List[str]] = None,
) -> ReleaseManifest:
    """Build a ReleaseManifest from per-track metadata and analysis objects."""
    if not metadata_list:
        return ReleaseManifest(release_title="Unknown Release", artist="Unknown Artist")

    # Derive release-level fields from the most common values
    album_titles = [m.album for m in metadata_list if m.album]
    artists = [m.artist for m in metadata_list if m.artist]

    release_title = _most_common(album_titles) or "Unknown Release"
    artist = _most_common(artists) or "Unknown Artist"

    years = [m.year for m in metadata_list if m.year]
    release_date = _most_common(years) or datetime.now(timezone.utc).strftime("%Y")

    tracks: List[TrackInfo] = []
    total_dur = 0.0

    for i, (meta, analysis) in enumerate(zip(metadata_list, analyses)):
        fname = (filenames or [])[i] if filenames and i < len(filenames) else ""
        issues = len(qc_reports[i].issues) if qc_reports and i < len(qc_reports) else 0

        track = TrackInfo(
            filename=fname,
            title=meta.title,
            artist=meta.artist,
            track_number=meta.track_number or (i + 1),
            duration_seconds=round(analysis.duration_seconds, 2),
            isrc=meta.isrc,
            explicit=meta.explicit,
            lufs=round(analysis.integrated_lufs, 2),
            issues_count=issues,
        )
        tracks.append(track)
        total_dur += analysis.duration_seconds

    tracks.sort(key=lambda t: t.track_number or 999)

    return ReleaseManifest(
        release_title=release_title,
        artist=artist,
        tracks=tracks,
        total_duration_seconds=round(total_dur, 2),
        release_date=release_date,
    )


def write_manifest_csv(manifest: ReleaseManifest, output_path: str) -> None:
    """Write the manifest as a CSV file suitable for distributor import."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "track_number", "title", "artist", "duration_seconds",
                "isrc", "explicit", "lufs", "filename", "issues_count",
            ],
        )
        writer.writeheader()
        for t in manifest.tracks:
            writer.writerow(
                {
                    "track_number": t.track_number,
                    "title": t.title or "",
                    "artist": t.artist or "",
                    "duration_seconds": t.duration_seconds,
                    "isrc": t.isrc or "",
                    "explicit": "yes" if t.explicit else "no",
                    "lufs": t.lufs,
                    "filename": t.filename,
                    "issues_count": t.issues_count,
                }
            )


def write_manifest_json(manifest: ReleaseManifest, output_path: str) -> None:
    """Write the manifest as a JSON file."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data: Dict[str, Any] = {
        "release_title": manifest.release_title,
        "artist": manifest.artist,
        "release_date": manifest.release_date,
        "upc": manifest.upc,
        "total_duration_seconds": manifest.total_duration_seconds,
        "created_at": manifest.created_at,
        "tracks": [
            {
                "track_number": t.track_number,
                "title": t.title,
                "artist": t.artist,
                "duration_seconds": t.duration_seconds,
                "isrc": t.isrc,
                "explicit": t.explicit,
                "lufs": t.lufs,
                "filename": t.filename,
                "issues_count": t.issues_count,
            }
            for t in manifest.tracks
        ],
    }
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def generate_credits_sheet(
    metadata_list: List[TrackMetadata], output_path: str
) -> None:
    """Write a credits CSV with fields for label copy / liner notes."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=[
                "track_number", "title", "artist", "genre", "year",
                "isrc", "label", "copyright", "explicit",
            ],
        )
        writer.writeheader()
        for i, m in enumerate(metadata_list):
            writer.writerow(
                {
                    "track_number": m.track_number or (i + 1),
                    "title": m.title or "",
                    "artist": m.artist or "",
                    "genre": m.genre or "",
                    "year": m.year or "",
                    "isrc": m.isrc or "",
                    "label": m.label or "",
                    "copyright": m.copyright or "",
                    "explicit": "yes" if m.explicit else "no",
                }
            )


def generate_submission_checklist(
    manifest: ReleaseManifest,
    qc_reports: List[QCReport],
    artwork_info: Optional[ArtworkInfo],
) -> Dict[str, Any]:
    """
    Generate a submission readiness checklist and a 0–100 risk score.

    Risk score: higher = more problems. ≤ 20 → green, 21–50 → amber, > 50 → red.
    """
    risk = 0
    items: List[Dict[str, Any]] = []

    # ---- Artwork ----
    if artwork_info is None:
        items.append({"check": "Artwork provided", "status": "fail", "note": "No artwork file found."})
        risk += 20
    else:
        if not artwork_info.is_square:
            items.append({"check": "Artwork is square", "status": "fail", "note": "Not square."})
            risk += 15
        else:
            items.append({"check": "Artwork is square", "status": "pass"})

        if not artwork_info.meets_minimum_size:
            items.append({"check": "Artwork ≥ 3000 px", "status": "fail",
                          "note": f"{artwork_info.width}×{artwork_info.height}"})
            risk += 10
        else:
            items.append({"check": "Artwork ≥ 3000 px", "status": "pass"})

    # ---- Metadata completeness ----
    tracks_missing_title = [t for t in manifest.tracks if not t.title]
    if tracks_missing_title:
        items.append({"check": "All tracks have titles", "status": "fail",
                      "note": f"{len(tracks_missing_title)} track(s) missing title."})
        risk += 15
    else:
        items.append({"check": "All tracks have titles", "status": "pass"})

    tracks_missing_isrc = [t for t in manifest.tracks if not t.isrc]
    if tracks_missing_isrc:
        items.append({"check": "All tracks have ISRC", "status": "warn",
                      "note": f"{len(tracks_missing_isrc)} track(s) missing ISRC."})
        risk += 10
    else:
        items.append({"check": "All tracks have ISRC", "status": "pass"})

    # ---- QC ----
    error_count = sum(r.error_count for r in qc_reports)
    warning_count = sum(r.warning_count for r in qc_reports)
    if error_count > 0:
        items.append({"check": "No QC errors", "status": "fail",
                      "note": f"{error_count} error(s) across all tracks."})
        risk += min(30, error_count * 10)
    else:
        items.append({"check": "No QC errors", "status": "pass"})

    if warning_count > 0:
        items.append({"check": "No QC warnings", "status": "warn",
                      "note": f"{warning_count} warning(s) across all tracks."})
        risk += min(15, warning_count * 3)
    else:
        items.append({"check": "No QC warnings", "status": "pass"})

    # ---- Explicit flagging ----
    explicit_tracks = [t for t in manifest.tracks if t.explicit]
    if explicit_tracks:
        items.append({"check": "Explicit tracks flagged", "status": "warn",
                      "note": f"{len(explicit_tracks)} explicit track(s). Ensure your distribution account allows explicit content."})
        risk += 5

    risk = min(100, risk)

    return {
        "risk_score": risk,
        "risk_level": "green" if risk <= 20 else "amber" if risk <= 50 else "red",
        "items": items,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _most_common(values: List[Any]) -> Optional[Any]:
    if not values:
        return None
    return max(set(values), key=values.count)
