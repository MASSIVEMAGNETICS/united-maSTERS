"""
conftest.py — Shared pytest fixtures for united-masters test suite.
"""

from __future__ import annotations

import struct
import wave
from pathlib import Path
from typing import Optional

import numpy as np
import pytest

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.ingest import AudioFile


# ---------------------------------------------------------------------------
# Audio file factory helpers
# ---------------------------------------------------------------------------

def _write_wav(path: Path, num_samples: int = 44100, sample_rate: int = 44100,
               amplitude: float = 0.5, channels: int = 2) -> None:
    """Write a minimal valid WAV file filled with a sine tone at 440 Hz."""
    t = np.linspace(0, num_samples / sample_rate, num_samples, endpoint=False)
    mono = (amplitude * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    pcm = (mono * 32767).clip(-32768, 32767).astype(np.int16)

    with wave.open(str(path), "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        if channels == 2:
            stereo = np.column_stack([pcm, pcm])
            wf.writeframes(stereo.tobytes())
        else:
            wf.writeframes(pcm.tobytes())


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    """Return path to a valid 1-second stereo 44.1 kHz WAV file."""
    p = tmp_path / "test_track.wav"
    _write_wav(p, num_samples=44100, sample_rate=44100)
    return p


@pytest.fixture
def silent_wav_file(tmp_path: Path) -> Path:
    """Return path to a completely silent WAV file."""
    p = tmp_path / "silent.wav"
    _write_wav(p, num_samples=44100, sample_rate=44100, amplitude=0.0)
    return p


@pytest.fixture
def clipped_wav_file(tmp_path: Path) -> Path:
    """Return path to a WAV file with clipped samples (amplitude > 1.0 → saturated)."""
    p = tmp_path / "clipped.wav"
    _write_wav(p, num_samples=44100, sample_rate=44100, amplitude=1.01)
    return p


@pytest.fixture
def sample_audio_file(tmp_path: Path) -> AudioFile:
    """Return a minimal AudioFile dataclass pointing to a real temp WAV."""
    wav = tmp_path / "track.wav"
    _write_wav(wav)
    return AudioFile(
        path=str(wav),
        filename="track.wav",
        extension=".wav",
        file_size_mb=round(wav.stat().st_size / (1024 * 1024), 3),
        is_supported=True,
    )


@pytest.fixture
def clean_analysis() -> AudioAnalysis:
    """Return an AudioAnalysis representing a clean, well-mastered track."""
    a = AudioAnalysis()
    a.duration_seconds = 180.0
    a.sample_rate = 44100
    a.bit_depth = 24
    a.channels = 2
    a.integrated_lufs = -12.0
    a.true_peak_dbfs = -1.5
    a.crest_factor_db = 10.0
    a.is_clipped = False
    a.dc_offset = 0.0
    a.silence_at_start_ms = 200.0
    a.silence_at_end_ms = 500.0
    a.estimated_bpm = 95.0
    a.error = None
    return a
