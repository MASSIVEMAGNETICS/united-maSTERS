"""
analyze.py — Audio analysis using scipy/numpy (no librosa dependency).

Gracefully degrades when scipy or pydub are not installed.
"""

from __future__ import annotations

import math
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class AudioAnalysis:
    duration_seconds: float = 0.0
    sample_rate: int = 44100
    bit_depth: int = 16
    channels: int = 2
    integrated_lufs: float = -99.0
    true_peak_dbfs: float = -99.0
    crest_factor_db: float = 0.0
    is_clipped: bool = False
    dc_offset: float = 0.0
    silence_at_start_ms: float = 0.0
    silence_at_end_ms: float = 0.0
    estimated_bpm: Optional[float] = None
    # Populated after analysis
    error: Optional[str] = None


def analyze_file(path: str) -> AudioAnalysis:
    """
    Analyse an audio file and return an AudioAnalysis.

    Strategy:
    1. WAV files are read directly with scipy.io.wavfile.
    2. All other formats are converted to a temporary WAV via pydub, then analysed.
    3. If neither library is available the function returns a minimal skeleton with an error note.
    """
    ext = Path(path).suffix.lower()

    try:
        if ext == ".wav":
            return _analyze_wav(path)
        else:
            return _analyze_via_pydub(path)
    except Exception as exc:
        result = AudioAnalysis()
        result.error = f"Analysis failed: {exc}"
        return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _analyze_wav(path: str) -> AudioAnalysis:
    """Read a WAV file with scipy and compute signal statistics."""
    try:
        from scipy.io import wavfile  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
    except ImportError:
        result = AudioAnalysis()
        result.error = "scipy/numpy not installed — cannot analyse WAV."
        return result

    sample_rate, data = wavfile.read(path)
    return _compute_analysis(data, sample_rate)


def _analyze_via_pydub(path: str) -> AudioAnalysis:
    """Convert non-WAV to WAV via pydub then analyse."""
    try:
        from pydub import AudioSegment  # noqa: PLC0415
    except ImportError:
        result = AudioAnalysis()
        result.error = "pydub not installed — cannot analyse non-WAV files."
        return result

    try:
        from scipy.io import wavfile  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415
    except ImportError:
        result = AudioAnalysis()
        result.error = "scipy/numpy not installed — cannot analyse audio."
        return result

    segment = AudioSegment.from_file(path)
    # Export to an in-process temp WAV without touching /tmp by using a BytesIO
    import io
    buf = io.BytesIO()
    segment.export(buf, format="wav")
    buf.seek(0)
    sample_rate, data = wavfile.read(buf)
    return _compute_analysis(data, sample_rate)


def _compute_analysis(data, sample_rate: int) -> AudioAnalysis:  # type: ignore[type-arg]
    import numpy as np  # noqa: PLC0415

    analysis = AudioAnalysis()
    analysis.sample_rate = int(sample_rate)

    # Normalise to float [-1.0, 1.0]
    if data.dtype.kind == "i":
        max_val = float(np.iinfo(data.dtype).max)
        analysis.bit_depth = data.dtype.itemsize * 8
        audio_float = data.astype(np.float64) / max_val
    elif data.dtype.kind == "u":
        max_val = float(np.iinfo(data.dtype).max)
        analysis.bit_depth = data.dtype.itemsize * 8
        audio_float = (data.astype(np.float64) - max_val / 2) / (max_val / 2)
    else:
        audio_float = data.astype(np.float64)
        analysis.bit_depth = 32  # float WAV

    if audio_float.ndim == 1:
        analysis.channels = 1
        mono = audio_float
    else:
        analysis.channels = audio_float.shape[1]
        mono = audio_float.mean(axis=1)

    total_samples = len(mono)
    analysis.duration_seconds = round(total_samples / sample_rate, 3)

    # Peak / true peak (simple sample peak as approximation)
    peak = float(np.max(np.abs(mono))) if total_samples > 0 else 0.0
    analysis.true_peak_dbfs = round(_to_db(peak), 2) if peak > 0 else -99.0

    # RMS and crest factor
    if total_samples > 0:
        rms = float(np.sqrt(np.mean(mono ** 2)))
    else:
        rms = 0.0
    rms_db = _to_db(rms) if rms > 0 else -99.0
    analysis.crest_factor_db = round(analysis.true_peak_dbfs - rms_db, 2)

    # Simplified LUFS approximation (no full K-weighting filter chain)
    # Uses mean square with a constant offset that approximates the K-weighting
    # offset for typical music programme material.
    mean_sq = float(np.mean(mono ** 2)) if total_samples > 0 else 0.0
    if mean_sq > 0:
        analysis.integrated_lufs = round(-0.691 + 10 * math.log10(mean_sq), 2)
    else:
        analysis.integrated_lufs = -99.0

    # Clipping detection — samples within 0.1% of full scale
    clip_threshold = 0.999
    clipped_samples = int(np.sum(np.abs(mono) >= clip_threshold))
    analysis.is_clipped = clipped_samples > 0

    # DC offset
    analysis.dc_offset = round(float(np.mean(mono)), 6) if total_samples > 0 else 0.0

    # Silence detection at head/tail (threshold = -60 dBFS ≈ 0.001)
    silence_threshold = 0.001
    analysis.silence_at_start_ms = _count_silence_ms(mono, sample_rate, silence_threshold, from_start=True)
    analysis.silence_at_end_ms = _count_silence_ms(mono, sample_rate, silence_threshold, from_start=False)

    # BPM estimation — very rough onset-based approach
    analysis.estimated_bpm = _estimate_bpm(mono, sample_rate)

    return analysis


def _to_db(linear: float) -> float:
    if linear <= 0:
        return -99.0
    return 20 * math.log10(linear)


def _count_silence_ms(mono, sample_rate: int, threshold: float, *, from_start: bool) -> float:
    import numpy as np  # noqa: PLC0415

    data = mono if from_start else mono[::-1]
    count = 0
    for sample in data:
        if abs(sample) < threshold:
            count += 1
        else:
            break
    return round(count / sample_rate * 1000, 1)


def _estimate_bpm(mono, sample_rate: int) -> Optional[float]:
    """
    Rough BPM estimate via onset-energy autocorrelation.
    Returns None if estimation is not reliable.
    """
    try:
        import numpy as np  # noqa: PLC0415

        # Downsample for speed
        hop = max(1, sample_rate // 100)  # 10 ms frames
        frames = [
            float(np.max(np.abs(mono[i : i + hop])))
            for i in range(0, len(mono) - hop, hop)
        ]
        if len(frames) < 60:
            return None

        env = np.array(frames)
        # Autocorrelation
        env -= env.mean()
        corr = np.correlate(env, env, mode="full")
        corr = corr[len(corr) // 2 :]

        # BPM range 60–200 in terms of frame lag
        fps = sample_rate / hop
        lag_min = int(fps * 60 / 200)
        lag_max = int(fps * 60 / 60)

        if lag_max >= len(corr):
            return None

        peak_lag = int(np.argmax(corr[lag_min:lag_max])) + lag_min
        if peak_lag == 0:
            return None

        bpm = round(fps * 60.0 / peak_lag, 1)
        if 60.0 <= bpm <= 200.0:
            return bpm
        return None
    except Exception:
        return None


def recommend_preset(analysis: AudioAnalysis) -> str:
    """
    Return a preset name based on simple signal heuristics.
    The caller should always show the full recommendation explanation to the user.
    """
    lufs = analysis.integrated_lufs
    crest = analysis.crest_factor_db
    bpm = analysis.estimated_bpm or 120.0

    # Very dynamic / quiet source → clean_dynamic
    if lufs < -18 or crest > 18:
        return "clean_dynamic"

    # Loud, low-crest (already heavily limited) → streaming_safe normalisation only
    if lufs > -8 and crest < 6:
        return "streaming_safe"

    # Fast tempo + loud → trap-style
    if bpm >= 130 and lufs > -14:
        return "trap_808_heavy"

    # Moderate tempo, moderate loudness → warm hip-hop
    if 85 <= bpm <= 130 and -16 <= lufs <= -10:
        return "warm_hip_hop"

    # High crest + moderate loudness → vocal_forward
    if crest > 12 and -18 <= lufs <= -10:
        return "vocal_forward"

    return "streaming_safe"
