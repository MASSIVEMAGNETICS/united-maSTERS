"""
test_encode.py — Tests for the encode module.

pydub (and thus ffmpeg) are mocked to avoid requiring a real ffmpeg installation
in CI. We test format validation, EncodeResult creation, warning logic, and
the batch helper.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from united_masters.core.encode import (
    SUPPORTED_OUTPUT_FORMATS,
    EncodeResult,
    _quality_ceiling_warning,
    encode_batch,
    encode_file,
)


# ---------------------------------------------------------------------------
# SUPPORTED_OUTPUT_FORMATS
# ---------------------------------------------------------------------------

class TestSupportedOutputFormats:
    def test_all_expected_keys_present(self):
        expected = {
            "wav_16_44", "wav_24_44", "wav_24_48", "wav_24_96",
            "mp3_128", "mp3_192", "mp3_256", "mp3_320", "mp3_vbr", "flac",
        }
        assert expected.issubset(set(SUPPORTED_OUTPUT_FORMATS.keys()))

    def test_wav_formats_have_bit_depth_and_sample_rate(self):
        for key in ["wav_16_44", "wav_24_44", "wav_24_48", "wav_24_96"]:
            fmt = SUPPORTED_OUTPUT_FORMATS[key]
            assert "bit_depth" in fmt
            assert "sample_rate" in fmt
            assert fmt["format"] == "wav"

    def test_mp3_formats_have_bitrate(self):
        for key in ["mp3_128", "mp3_192", "mp3_256", "mp3_320"]:
            fmt = SUPPORTED_OUTPUT_FORMATS[key]
            assert "bitrate" in fmt
            assert fmt["format"] == "mp3"

    def test_flac_format(self):
        fmt = SUPPORTED_OUTPUT_FORMATS["flac"]
        assert fmt["format"] == "flac"

    def test_mp3_320_is_cbr(self):
        assert SUPPORTED_OUTPUT_FORMATS["mp3_320"]["mode"] == "cbr"

    def test_mp3_vbr_mode(self):
        assert SUPPORTED_OUTPUT_FORMATS["mp3_vbr"]["mode"] == "vbr"

    def test_wav_24_96_highest_res(self):
        fmt = SUPPORTED_OUTPUT_FORMATS["wav_24_96"]
        assert fmt["sample_rate"] == 96000
        assert fmt["bit_depth"] == 24

    def test_all_formats_have_description_or_format(self):
        for key, fmt in SUPPORTED_OUTPUT_FORMATS.items():
            assert "format" in fmt, f"Format '{key}' missing 'format' key"


# ---------------------------------------------------------------------------
# EncodeResult dataclass
# ---------------------------------------------------------------------------

class TestEncodeResult:
    def test_success_result(self):
        r = EncodeResult(output_path="/out/track.wav", format_key="wav_16_44", success=True)
        assert r.success is True
        assert r.error is None
        assert r.warning is None

    def test_failure_result(self):
        r = EncodeResult(
            output_path="/out/track.mp3",
            format_key="mp3_320",
            success=False,
            error="ffmpeg not found",
        )
        assert r.success is False
        assert r.error == "ffmpeg not found"

    def test_warning_field(self):
        r = EncodeResult(
            output_path="/out/track.wav",
            format_key="wav_24_96",
            success=True,
            warning="Source quality ceiling warning",
        )
        assert r.warning is not None


# ---------------------------------------------------------------------------
# _quality_ceiling_warning (internal helper)
# ---------------------------------------------------------------------------

class TestQualityCeilingWarning:
    def test_wav_source_no_warning(self):
        assert _quality_ceiling_warning("/music/master.wav", "wav_24_96") is None

    def test_flac_source_no_warning(self):
        assert _quality_ceiling_warning("/music/master.flac", "mp3_320") is None

    def test_mp3_to_high_res_wav_warns(self):
        warning = _quality_ceiling_warning("/music/track.mp3", "wav_24_96")
        assert warning is not None
        assert "SOURCE QUALITY CEILING" in warning
        assert "MP3" in warning

    def test_mp3_to_flac_warns(self):
        warning = _quality_ceiling_warning("/music/track.mp3", "flac")
        assert warning is not None

    def test_mp3_to_mp3_320_warns(self):
        warning = _quality_ceiling_warning("/music/track.mp3", "mp3_320")
        assert warning is not None

    def test_mp3_to_mp3_128_no_warning(self):
        # 128k is not in _HIGH_RES_FORMATS
        assert _quality_ceiling_warning("/music/track.mp3", "mp3_128") is None

    def test_m4a_to_wav_warns(self):
        warning = _quality_ceiling_warning("/music/track.m4a", "wav_24_48")
        assert warning is not None

    def test_ogg_to_flac_warns(self):
        warning = _quality_ceiling_warning("/music/track.ogg", "flac")
        assert warning is not None


# ---------------------------------------------------------------------------
# encode_file — mocked pydub
# ---------------------------------------------------------------------------

class TestEncodeFile:
    def test_unknown_format_key_returns_failure(self, tmp_path):
        result = encode_file(
            input_path=str(tmp_path / "input.wav"),
            output_dir=str(tmp_path / "out"),
            format_key="nonexistent_format",
        )
        assert result.success is False
        assert "Unknown format key" in result.error

    @patch("united_masters.core.encode.AudioSegment")
    def test_successful_wav_encode(self, mock_audio_segment_cls, tmp_path):
        """Encode a WAV with mocked pydub."""
        input_path = str(tmp_path / "input.wav")
        (tmp_path / "input.wav").write_bytes(b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio.__len__ = lambda s: 180000
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_sample_width.return_value = mock_audio
        mock_audio_segment_cls.from_file.return_value = mock_audio

        result = encode_file(
            input_path=input_path,
            output_dir=str(tmp_path / "out"),
            format_key="wav_16_44",
        )
        assert result.success is True
        assert result.format_key == "wav_16_44"
        assert result.error is None
        mock_audio.export.assert_called_once()

    @patch("united_masters.core.encode.AudioSegment")
    def test_successful_mp3_encode(self, mock_audio_segment_cls, tmp_path):
        input_path = str(tmp_path / "input.wav")
        (tmp_path / "input.wav").write_bytes(b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio_segment_cls.from_file.return_value = mock_audio

        result = encode_file(
            input_path=input_path,
            output_dir=str(tmp_path / "out"),
            format_key="mp3_320",
        )
        assert result.success is True
        mock_audio.export.assert_called_once()
        call_kwargs = mock_audio.export.call_args
        assert call_kwargs[1]["format"] == "mp3" or call_kwargs[0][1] == "mp3"

    @patch("united_masters.core.encode.AudioSegment")
    def test_mp3_source_to_high_res_includes_warning(self, mock_audio_segment_cls, tmp_path):
        input_path = str(tmp_path / "input.mp3")
        (tmp_path / "input.mp3").write_bytes(b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio_segment_cls.from_file.return_value = mock_audio

        result = encode_file(
            input_path=input_path,
            output_dir=str(tmp_path / "out"),
            format_key="wav_24_96",
        )
        assert result.success is True
        assert result.warning is not None
        assert "SOURCE QUALITY CEILING" in result.warning

    def test_pydub_import_error_returns_failure(self, tmp_path):
        """If AudioSegment is None (pydub absent), encode should return success=False."""
        input_path = str(tmp_path / "input.wav")
        (tmp_path / "input.wav").write_bytes(b"\x00")
        import united_masters.core.encode as enc_mod
        original = enc_mod.AudioSegment
        enc_mod.AudioSegment = None  # type: ignore[assignment]
        try:
            result = encode_file(
                input_path=input_path,
                output_dir=str(tmp_path / "out"),
                format_key="mp3_320",
            )
            assert result.success is False
            assert result.error is not None
        finally:
            enc_mod.AudioSegment = original

    @patch("united_masters.core.encode.AudioSegment")
    def test_filename_suffix_applied(self, mock_audio_segment_cls, tmp_path):
        input_path = str(tmp_path / "track.wav")
        (tmp_path / "track.wav").write_bytes(b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_sample_width.return_value = mock_audio
        mock_audio_segment_cls.from_file.return_value = mock_audio

        result = encode_file(
            input_path=input_path,
            output_dir=str(tmp_path / "out"),
            format_key="wav_16_44",
            filename_suffix="_master",
        )
        assert "_master" in result.output_path


# ---------------------------------------------------------------------------
# encode_batch
# ---------------------------------------------------------------------------

class TestEncodeBatch:
    @patch("united_masters.core.encode.AudioSegment")
    def test_batch_returns_one_result_per_format(self, mock_audio_segment_cls, tmp_path):
        input_path = str(tmp_path / "track.wav")
        (tmp_path / "track.wav").write_bytes(b"\x00" * 100)

        mock_audio = MagicMock()
        mock_audio.set_frame_rate.return_value = mock_audio
        mock_audio.set_sample_width.return_value = mock_audio
        mock_audio_segment_cls.from_file.return_value = mock_audio

        formats = ["wav_16_44", "mp3_320", "flac"]
        results = encode_batch(
            input_path=input_path,
            output_dir=str(tmp_path / "out"),
            format_keys=formats,
        )
        assert len(results) == 3
        returned_keys = [r.format_key for r in results]
        assert set(returned_keys) == set(formats)

    def test_empty_format_list(self, tmp_path):
        input_path = str(tmp_path / "track.wav")
        (tmp_path / "track.wav").write_bytes(b"\x00")
        results = encode_batch(input_path=input_path, output_dir=str(tmp_path), format_keys=[])
        assert results == []

    def test_unknown_format_in_batch_returns_failure(self, tmp_path):
        input_path = str(tmp_path / "track.wav")
        (tmp_path / "track.wav").write_bytes(b"\x00")
        results = encode_batch(
            input_path=input_path,
            output_dir=str(tmp_path),
            format_keys=["bad_format"],
        )
        assert len(results) == 1
        assert results[0].success is False
