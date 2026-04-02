"""
test_qc.py — Tests for the QC engine.
"""

import pytest

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.ingest import AudioFile
from united_masters.core.qc import (
    QCIssue,
    QCReport,
    check_clipping,
    check_dc_offset,
    check_mono_compatibility,
    check_sample_rate,
    check_silence_head_tail,
    run_album_qc,
    run_qc,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_analysis(**kwargs) -> AudioAnalysis:
    """Build an AudioAnalysis with sensible defaults, overriding with kwargs."""
    defaults = dict(
        duration_seconds=180.0,
        sample_rate=44100,
        bit_depth=24,
        channels=2,
        integrated_lufs=-12.0,
        true_peak_dbfs=-1.5,
        crest_factor_db=10.0,
        is_clipped=False,
        dc_offset=0.0,
        silence_at_start_ms=200.0,
        silence_at_end_ms=500.0,
        estimated_bpm=95.0,
        error=None,
    )
    defaults.update(kwargs)
    a = AudioAnalysis()
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


def _make_audio_file(filename: str = "track.wav") -> AudioFile:
    return AudioFile(
        path=f"/music/{filename}",
        filename=filename,
        extension=".wav",
        file_size_mb=25.0,
        is_supported=True,
    )


# ---------------------------------------------------------------------------
# QCIssue dataclass
# ---------------------------------------------------------------------------

class TestQCIssue:
    def test_creation(self):
        issue = QCIssue(severity="error", code="TEST", message="Test message", file_path="/f.wav")
        assert issue.severity == "error"
        assert issue.code == "TEST"
        assert issue.message == "Test message"

    def test_default_file_path(self):
        issue = QCIssue(severity="info", code="X", message="y")
        assert issue.file_path == ""


# ---------------------------------------------------------------------------
# QCReport
# ---------------------------------------------------------------------------

class TestQCReport:
    def test_passed_when_no_errors(self):
        report = QCReport(file_path="/f.wav")
        report.issues.append(QCIssue(severity="warning", code="W", message="w"))
        assert report.passed is True

    def test_failed_when_error_present(self):
        report = QCReport(file_path="/f.wav")
        report.issues.append(QCIssue(severity="error", code="E", message="e"))
        assert report.passed is False

    def test_error_count(self):
        report = QCReport(file_path="/f.wav")
        report.issues += [
            QCIssue(severity="error", code="E1", message="e"),
            QCIssue(severity="error", code="E2", message="e"),
            QCIssue(severity="warning", code="W1", message="w"),
        ]
        assert report.error_count == 2
        assert report.warning_count == 1


# ---------------------------------------------------------------------------
# check_clipping
# ---------------------------------------------------------------------------

class TestCheckClipping:
    def test_no_clipping(self):
        analysis = _make_analysis(is_clipped=False)
        assert check_clipping(analysis) is None

    def test_clipping_detected(self):
        analysis = _make_analysis(is_clipped=True)
        issue = check_clipping(analysis)
        assert issue is not None
        assert issue.severity == "error"
        assert issue.code == "CLIPPING_DETECTED"

    def test_file_path_propagated(self):
        analysis = _make_analysis(is_clipped=True)
        issue = check_clipping(analysis, file_path="/music/track.wav")
        assert issue.file_path == "/music/track.wav"


# ---------------------------------------------------------------------------
# check_silence_head_tail
# ---------------------------------------------------------------------------

class TestCheckSilenceHeadTail:
    def test_acceptable_silence(self):
        analysis = _make_analysis(silence_at_start_ms=200, silence_at_end_ms=300)
        issues = check_silence_head_tail(analysis)
        assert issues == []

    def test_excess_head_silence_error(self):
        analysis = _make_analysis(silence_at_start_ms=4000)
        issues = check_silence_head_tail(analysis)
        codes = [i.code for i in issues]
        assert "EXCESS_SILENCE_HEAD" in codes

    def test_moderate_head_silence_info(self):
        analysis = _make_analysis(silence_at_start_ms=600)
        issues = check_silence_head_tail(analysis)
        assert any(i.code == "SILENCE_HEAD" for i in issues)

    def test_excess_tail_silence_warning(self):
        analysis = _make_analysis(silence_at_end_ms=6000)
        issues = check_silence_head_tail(analysis)
        codes = [i.code for i in issues]
        assert "EXCESS_SILENCE_TAIL" in codes

    def test_both_head_and_tail(self):
        analysis = _make_analysis(silence_at_start_ms=4000, silence_at_end_ms=7000)
        issues = check_silence_head_tail(analysis)
        assert len(issues) == 2


# ---------------------------------------------------------------------------
# check_dc_offset
# ---------------------------------------------------------------------------

class TestCheckDcOffset:
    def test_no_dc_offset(self):
        analysis = _make_analysis(dc_offset=0.0)
        assert check_dc_offset(analysis) is None

    def test_small_dc_offset_ignored(self):
        analysis = _make_analysis(dc_offset=0.005)
        assert check_dc_offset(analysis) is None

    def test_large_dc_offset_warns(self):
        analysis = _make_analysis(dc_offset=0.05)
        issue = check_dc_offset(analysis)
        assert issue is not None
        assert issue.severity == "warning"
        assert issue.code == "DC_OFFSET"

    def test_negative_dc_offset_warns(self):
        analysis = _make_analysis(dc_offset=-0.02)
        issue = check_dc_offset(analysis)
        assert issue is not None


# ---------------------------------------------------------------------------
# check_mono_compatibility
# ---------------------------------------------------------------------------

class TestCheckMonoCompatibility:
    def test_stereo_no_issue(self):
        analysis = _make_analysis(channels=2)
        assert check_mono_compatibility(analysis) is None

    def test_mono_flags_info(self):
        analysis = _make_analysis(channels=1)
        issue = check_mono_compatibility(analysis)
        assert issue is not None
        assert issue.severity == "info"
        assert issue.code == "MONO_FILE"


# ---------------------------------------------------------------------------
# check_sample_rate
# ---------------------------------------------------------------------------

class TestCheckSampleRate:
    def test_standard_44100(self):
        analysis = _make_analysis(sample_rate=44100)
        assert check_sample_rate(analysis) is None

    def test_standard_48000(self):
        analysis = _make_analysis(sample_rate=48000)
        assert check_sample_rate(analysis) is None

    def test_non_standard_warns(self):
        analysis = _make_analysis(sample_rate=22050)
        issue = check_sample_rate(analysis)
        assert issue is not None
        assert issue.code == "NON_STANDARD_SAMPLE_RATE"

    def test_high_sample_rate_info(self):
        analysis = _make_analysis(sample_rate=96000)
        issue = check_sample_rate(analysis)
        assert issue is not None
        assert issue.code == "HIGH_SAMPLE_RATE"


# ---------------------------------------------------------------------------
# run_qc
# ---------------------------------------------------------------------------

class TestRunQC:
    def test_clean_file_passes(self):
        af = _make_audio_file()
        analysis = _make_analysis()
        report = run_qc(af, analysis)
        assert report.passed is True
        assert report.error_count == 0

    def test_clipped_file_fails(self):
        af = _make_audio_file()
        analysis = _make_analysis(is_clipped=True)
        report = run_qc(af, analysis)
        assert report.passed is False
        assert any(i.code == "CLIPPING_DETECTED" for i in report.issues)

    def test_analysis_error_creates_error_issue(self):
        af = _make_audio_file()
        analysis = AudioAnalysis()
        analysis.error = "File not found"
        report = run_qc(af, analysis)
        assert report.passed is False
        assert any(i.code == "ANALYSIS_FAILED" for i in report.issues)

    def test_multiple_issues_collected(self):
        af = _make_audio_file()
        analysis = _make_analysis(
            is_clipped=True,
            dc_offset=0.05,
            silence_at_start_ms=4000,
        )
        report = run_qc(af, analysis)
        assert len(report.issues) >= 3


# ---------------------------------------------------------------------------
# run_album_qc
# ---------------------------------------------------------------------------

class TestRunAlbumQC:
    def _make_pair(self, filename: str, sample_rate: int = 44100, lufs: float = -12.0):
        af = _make_audio_file(filename)
        an = _make_analysis(sample_rate=sample_rate, integrated_lufs=lufs)
        return af, an

    def test_empty_input_returns_empty(self):
        assert run_album_qc([], []) == []

    def test_consistent_album_no_issues(self):
        pairs = [self._make_pair(f"t{i}.wav") for i in range(3)]
        files, analyses = zip(*pairs)
        issues = run_album_qc(list(files), list(analyses))
        # Expect no INCONSISTENT_SAMPLE_RATES or ALBUM_LUFS_WHIPLASH
        codes = [i.code for i in issues]
        assert "INCONSISTENT_SAMPLE_RATES" not in codes
        assert "ALBUM_LUFS_WHIPLASH" not in codes

    def test_mixed_sample_rates_error(self):
        af1, an1 = self._make_pair("t1.wav", sample_rate=44100)
        af2, an2 = self._make_pair("t2.wav", sample_rate=48000)
        issues = run_album_qc([af1, af2], [an1, an2])
        codes = [i.code for i in issues]
        assert "INCONSISTENT_SAMPLE_RATES" in codes

    def test_large_lufs_variance_warns(self):
        af1, an1 = self._make_pair("t1.wav", lufs=-7.0)
        af2, an2 = self._make_pair("t2.wav", lufs=-18.0)
        issues = run_album_qc([af1, af2], [an1, an2])
        codes = [i.code for i in issues]
        assert "ALBUM_LUFS_WHIPLASH" in codes

    def test_duplicate_titles_warn(self):
        af1 = _make_audio_file("same song.wav")
        af2 = _make_audio_file("same song.mp3")
        an = _make_analysis()
        issues = run_album_qc([af1, af2], [an, an])
        codes = [i.code for i in issues]
        assert "DUPLICATE_TRACK_TITLE" in codes
