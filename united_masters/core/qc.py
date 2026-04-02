"""
qc.py — Release QC engine.

Checks individual tracks and album-level consistency for common mastering
and delivery issues.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.ingest import AudioFile


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class QCIssue:
    severity: str  # "error" | "warning" | "info"
    code: str
    message: str
    file_path: str = ""


@dataclass
class QCReport:
    file_path: str
    issues: List[QCIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_clipping(analysis: AudioAnalysis, file_path: str = "") -> Optional[QCIssue]:
    if analysis.is_clipped:
        return QCIssue(
            severity="error",
            code="CLIPPING_DETECTED",
            message=(
                "Digital clipping detected — samples at or above 0 dBFS. "
                "This will cause distortion on playback and rejection by some distributors. "
                "De-clip or reduce gain before mastering."
            ),
            file_path=file_path,
        )
    return None


def check_silence_head_tail(
    analysis: AudioAnalysis, file_path: str = ""
) -> List[QCIssue]:
    issues: List[QCIssue] = []

    if analysis.silence_at_start_ms > 3000:
        issues.append(
            QCIssue(
                severity="warning",
                code="EXCESS_SILENCE_HEAD",
                message=(
                    f"More than 3 seconds of silence at the start of the file "
                    f"({analysis.silence_at_start_ms:.0f} ms). "
                    "Trim to ≤ 500 ms unless intentional."
                ),
                file_path=file_path,
            )
        )
    elif analysis.silence_at_start_ms > 500:
        issues.append(
            QCIssue(
                severity="info",
                code="SILENCE_HEAD",
                message=(
                    f"Silence at start: {analysis.silence_at_start_ms:.0f} ms. "
                    "Consider trimming to ≤ 200 ms for streaming."
                ),
                file_path=file_path,
            )
        )

    if analysis.silence_at_end_ms > 5000:
        issues.append(
            QCIssue(
                severity="warning",
                code="EXCESS_SILENCE_TAIL",
                message=(
                    f"More than 5 seconds of silence at the end of the file "
                    f"({analysis.silence_at_end_ms:.0f} ms). Trim appropriately."
                ),
                file_path=file_path,
            )
        )
    return issues


def check_dc_offset(
    analysis: AudioAnalysis, file_path: str = ""
) -> Optional[QCIssue]:
    threshold = 0.01  # 1% DC offset is audible and problematic
    if abs(analysis.dc_offset) > threshold:
        return QCIssue(
            severity="warning",
            code="DC_OFFSET",
            message=(
                f"DC offset detected ({analysis.dc_offset:+.4f}). "
                "This will introduce a click at edit points and waste headroom. "
                "Apply a DC-offset removal pass."
            ),
            file_path=file_path,
        )
    return None


def check_mono_compatibility(
    analysis: AudioAnalysis, file_path: str = ""
) -> Optional[QCIssue]:
    """Warn if the track is mono but is labelled as stereo (single-channel content)."""
    if analysis.channels == 1:
        return QCIssue(
            severity="info",
            code="MONO_FILE",
            message=(
                "File has a single audio channel (mono). "
                "Confirm this is intentional — most streaming delivery requires stereo."
            ),
            file_path=file_path,
        )
    return None


def check_sample_rate(
    analysis: AudioAnalysis, file_path: str = ""
) -> Optional[QCIssue]:
    standard_rates = {44100, 48000, 88200, 96000, 176400, 192000}
    if analysis.sample_rate not in standard_rates:
        return QCIssue(
            severity="warning",
            code="NON_STANDARD_SAMPLE_RATE",
            message=(
                f"Non-standard sample rate: {analysis.sample_rate} Hz. "
                "Most distributors require 44100 or 48000 Hz. "
                "Re-sample before delivery."
            ),
            file_path=file_path,
        )
    if analysis.sample_rate not in {44100, 48000}:
        return QCIssue(
            severity="info",
            code="HIGH_SAMPLE_RATE",
            message=(
                f"High sample rate: {analysis.sample_rate} Hz. "
                "Ensure your delivery format specification requires this — "
                "most platforms transcode to 44.1 or 48 kHz anyway."
            ),
            file_path=file_path,
        )
    return None


def check_lufs(analysis: AudioAnalysis, file_path: str = "") -> Optional[QCIssue]:
    lufs = analysis.integrated_lufs
    if lufs > -6.0:
        return QCIssue(
            severity="warning",
            code="VERY_LOUD_SOURCE",
            message=(
                f"Integrated loudness is extremely high ({lufs:.1f} LUFS). "
                "This source is already heavily limited/clipped. "
                "Streaming normalisation will attenuate it significantly."
            ),
            file_path=file_path,
        )
    if lufs < -30.0:
        return QCIssue(
            severity="info",
            code="VERY_QUIET_SOURCE",
            message=(
                f"Integrated loudness is very low ({lufs:.1f} LUFS). "
                "This may be a dialogue/spoken word file or an unlevel mix. "
                "Verify this is the correct file."
            ),
            file_path=file_path,
        )
    return None


def run_qc(audio_file: AudioFile, analysis: AudioAnalysis) -> QCReport:
    """Run all per-track QC checks and return a QCReport."""
    report = QCReport(file_path=audio_file.path)

    # Only run detailed checks if analysis succeeded
    if analysis.error:
        report.issues.append(
            QCIssue(
                severity="error",
                code="ANALYSIS_FAILED",
                message=f"Could not analyse file: {analysis.error}",
                file_path=audio_file.path,
            )
        )
        return report

    checks = [
        check_clipping(analysis, audio_file.path),
        check_dc_offset(analysis, audio_file.path),
        check_mono_compatibility(analysis, audio_file.path),
        check_sample_rate(analysis, audio_file.path),
        check_lufs(analysis, audio_file.path),
    ]

    for issue in checks:
        if issue is not None:
            report.issues.append(issue)

    report.issues.extend(check_silence_head_tail(analysis, audio_file.path))

    return report


def run_album_qc(
    audio_files: List[AudioFile], analyses: List[AudioAnalysis]
) -> List[QCIssue]:
    """
    Album-level QC checks that look across all tracks.
    Returns a list of album-scope QCIssues (not tied to a single file).
    """
    issues: List[QCIssue] = []

    if not audio_files or not analyses:
        return issues

    # --- Inconsistent sample rates ---
    sample_rates = {a.sample_rate for a in analyses if not a.error}
    if len(sample_rates) > 1:
        issues.append(
            QCIssue(
                severity="error",
                code="INCONSISTENT_SAMPLE_RATES",
                message=(
                    f"Tracks have inconsistent sample rates: "
                    f"{sorted(sample_rates)}. "
                    "All tracks must share the same sample rate for a consistent release."
                ),
            )
        )

    # --- LUFS variance (album whiplash) ---
    lufs_values = [
        a.integrated_lufs for a in analyses if not a.error and a.integrated_lufs > -90
    ]
    if len(lufs_values) >= 2:
        lufs_range = max(lufs_values) - min(lufs_values)
        if lufs_range > 6:
            issues.append(
                QCIssue(
                    severity="warning",
                    code="ALBUM_LUFS_WHIPLASH",
                    message=(
                        f"Large loudness variance across tracks: {lufs_range:.1f} dB "
                        f"(range {min(lufs_values):.1f} to {max(lufs_values):.1f} LUFS). "
                        "Listeners will experience jarring volume jumps between tracks."
                    ),
                )
            )

    # --- Duplicate title detection ---
    titles = [f.stem.strip().lower() for f in audio_files]
    seen: dict = {}
    for i, title in enumerate(titles):
        if title in seen:
            issues.append(
                QCIssue(
                    severity="warning",
                    code="DUPLICATE_TRACK_TITLE",
                    message=(
                        f"Possible duplicate track title: '{audio_files[i].stem}' "
                        f"(matches '{audio_files[seen[title]].stem}'). "
                        "Verify these are not accidental duplicates."
                    ),
                )
            )
        else:
            seen[title] = i

    return issues
