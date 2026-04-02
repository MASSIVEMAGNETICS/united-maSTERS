"""
consistency.py — Album consistency analysis and track-order suggestions.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.ingest import AudioFile


@dataclass
class ConsistencyReport:
    track_lufs_values: List[float] = field(default_factory=list)
    mean_lufs: float = -99.0
    lufs_variance: float = 0.0
    outlier_tracks: List[Dict[str, Any]] = field(default_factory=list)
    loudness_balanced: bool = True
    recommended_target_lufs: float = -10.5
    sequence_suggestion: List[str] = field(default_factory=list)


def analyze_album_consistency(
    audio_files: List[AudioFile], analyses: List[AudioAnalysis]
) -> ConsistencyReport:
    """
    Compare loudness and dynamic characteristics across all tracks to identify
    imbalances and suggest a recommended mastering target LUFS.
    """
    report = ConsistencyReport()

    valid_pairs = [
        (af, an)
        for af, an in zip(audio_files, analyses)
        if not an.error and an.integrated_lufs > -90
    ]

    if not valid_pairs:
        return report

    lufs_values = [an.integrated_lufs for _, an in valid_pairs]
    report.track_lufs_values = lufs_values

    mean = statistics.mean(lufs_values)
    report.mean_lufs = round(mean, 2)

    if len(lufs_values) > 1:
        variance = statistics.stdev(lufs_values)
    else:
        variance = 0.0
    report.lufs_variance = round(variance, 2)

    # Flag outlier tracks (> 3 dB from mean)
    outlier_threshold = 3.0
    for (af, an) in valid_pairs:
        delta = abs(an.integrated_lufs - mean)
        if delta > outlier_threshold:
            report.outlier_tracks.append(
                {
                    "filename": af.filename,
                    "lufs": round(an.integrated_lufs, 2),
                    "delta_from_mean": round(delta, 2),
                }
            )

    report.loudness_balanced = len(report.outlier_tracks) == 0 and variance <= 3.0

    # Recommend a mastering target close to the mean, clamped to a safe range
    recommended = max(-13.0, min(-8.0, round(mean, 1)))
    report.recommended_target_lufs = recommended

    # Sequence suggestion
    report.sequence_suggestion = suggest_track_order(
        [an for _, an in valid_pairs],
        [af.filename for af, _ in valid_pairs],
    )

    return report


def suggest_track_order(
    analyses: List[AudioAnalysis], filenames: List[str]
) -> List[str]:
    """
    Suggest a track order that delivers a good album listening arc.

    Strategy: open strong, build through the middle, close with impact.
    Sort by integrated loudness (proxy for energy) and interleave so the
    sequence goes: medium → high → medium → ... → highest.

    This is a heuristic — the artist always has final say.
    """
    if not analyses:
        return filenames

    paired = list(zip(filenames, analyses))
    # Sort by energy ascending
    paired.sort(key=lambda x: x[1].integrated_lufs if not x[1].error else -99.0)

    # Interleave: put the most energetic track as the opener, then quieter,
    # then build back up.
    n = len(paired)
    if n <= 2:
        return [p[0] for p in paired]

    # Classic album arc: strong open, valleys, strong close
    mid = n // 2
    first_half = paired[mid:]   # louder tracks
    second_half = paired[:mid]  # quieter tracks

    ordered: List[str] = []
    i, j = 0, 0
    while i < len(first_half) or j < len(second_half):
        if i < len(first_half):
            ordered.append(first_half[i][0])
            i += 1
        if j < len(second_half):
            ordered.append(second_half[j][0])
            j += 1

    return ordered
