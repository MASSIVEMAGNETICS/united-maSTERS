"""
test_ingest.py — Tests for the ingest module.
"""

import os
from pathlib import Path

import pytest

from united_masters.core.ingest import (
    SUPPORTED_FORMATS,
    AudioFile,
    detect_duplicates,
    get_source_quality_warning,
    scan_folder,
)


# ---------------------------------------------------------------------------
# AudioFile construction
# ---------------------------------------------------------------------------

class TestAudioFile:
    def test_basic_fields(self):
        af = AudioFile(
            path="/music/track01.wav",
            filename="track01.wav",
            extension=".wav",
            file_size_mb=25.4,
            is_supported=True,
        )
        assert af.path == "/music/track01.wav"
        assert af.filename == "track01.wav"
        assert af.extension == ".wav"
        assert af.file_size_mb == 25.4
        assert af.is_supported is True
        assert af.bitrate_kbps is None

    def test_extension_normalised_to_lowercase(self):
        af = AudioFile(
            path="/music/TRACK.MP3",
            filename="TRACK.MP3",
            extension=".MP3",
            file_size_mb=5.0,
            is_supported=True,
        )
        assert af.extension == ".mp3"

    def test_stem_property(self):
        af = AudioFile(
            path="/music/my song.flac",
            filename="my song.flac",
            extension=".flac",
            file_size_mb=30.0,
            is_supported=True,
        )
        assert af.stem == "my song"

    def test_unsupported_format(self):
        af = AudioFile(
            path="/docs/notes.txt",
            filename="notes.txt",
            extension=".txt",
            file_size_mb=0.01,
            is_supported=False,
        )
        assert af.is_supported is False


# ---------------------------------------------------------------------------
# Supported formats list
# ---------------------------------------------------------------------------

class TestSupportedFormats:
    def test_contains_common_formats(self):
        for fmt in [".wav", ".flac", ".mp3", ".aiff", ".aif", ".m4a", ".ogg"]:
            assert fmt in SUPPORTED_FORMATS

    def test_does_not_contain_video(self):
        assert ".mp4" not in SUPPORTED_FORMATS
        assert ".avi" not in SUPPORTED_FORMATS


# ---------------------------------------------------------------------------
# scan_folder
# ---------------------------------------------------------------------------

class TestScanFolder:
    def test_empty_folder(self, tmp_path):
        files = scan_folder(str(tmp_path))
        assert files == []

    def test_supported_files_detected(self, tmp_path):
        (tmp_path / "track01.wav").write_bytes(b"\x00" * 100)
        (tmp_path / "track02.mp3").write_bytes(b"\x00" * 100)
        (tmp_path / "cover.jpg").write_bytes(b"\xff\xd8\xff")  # not audio

        files = scan_folder(str(tmp_path))
        names = {f.filename for f in files}
        assert "track01.wav" in names
        assert "track02.mp3" in names
        assert "cover.jpg" in names  # included but marked unsupported

    def test_supported_flag(self, tmp_path):
        (tmp_path / "audio.flac").write_bytes(b"\x00" * 50)
        (tmp_path / "readme.txt").write_bytes(b"hello")

        files = scan_folder(str(tmp_path))
        by_name = {f.filename: f for f in files}
        assert by_name["audio.flac"].is_supported is True
        assert by_name["readme.txt"].is_supported is False

    def test_file_size_populated(self, tmp_path):
        content = b"\x00" * 1024 * 10  # 10 KB
        (tmp_path / "small.wav").write_bytes(content)
        files = scan_folder(str(tmp_path))
        assert len(files) == 1
        assert files[0].file_size_mb > 0

    def test_nonexistent_folder_raises(self):
        with pytest.raises(FileNotFoundError):
            scan_folder("/this/path/does/not/exist")

    def test_file_path_raises(self, tmp_path):
        f = tmp_path / "file.wav"
        f.write_bytes(b"\x00")
        with pytest.raises(NotADirectoryError):
            scan_folder(str(f))


# ---------------------------------------------------------------------------
# detect_duplicates
# ---------------------------------------------------------------------------

class TestDetectDuplicates:
    def _make(self, filename: str) -> AudioFile:
        return AudioFile(
            path=f"/music/{filename}",
            filename=filename,
            extension=Path(filename).suffix.lower(),
            file_size_mb=5.0,
            is_supported=True,
        )

    def test_no_duplicates(self):
        files = [self._make("alpha.wav"), self._make("beta.mp3")]
        assert detect_duplicates(files) == []

    def test_exact_duplicate_stems(self):
        files = [self._make("track01.wav"), self._make("track01.mp3")]
        groups = detect_duplicates(files)
        assert len(groups) == 1
        assert len(groups[0]) == 2

    def test_case_insensitive(self):
        files = [self._make("My Song.wav"), self._make("my song.mp3")]
        groups = detect_duplicates(files)
        assert len(groups) == 1

    def test_three_duplicates_in_one_group(self):
        files = [
            self._make("track.wav"),
            self._make("track.flac"),
            self._make("track.mp3"),
        ]
        groups = detect_duplicates(files)
        assert len(groups) == 1
        assert len(groups[0]) == 3

    def test_two_separate_duplicate_pairs(self):
        files = [
            self._make("a.wav"), self._make("a.mp3"),
            self._make("b.wav"), self._make("b.flac"),
        ]
        groups = detect_duplicates(files)
        assert len(groups) == 2


# ---------------------------------------------------------------------------
# get_source_quality_warning
# ---------------------------------------------------------------------------

class TestGetSourceQualityWarning:
    def _make_with_bitrate(self, filename: str, bitrate_kbps: int) -> AudioFile:
        af = AudioFile(
            path=f"/music/{filename}",
            filename=filename,
            extension=Path(filename).suffix.lower(),
            file_size_mb=3.0,
            is_supported=True,
        )
        af.bitrate_kbps = bitrate_kbps
        return af

    def test_wav_no_warning(self):
        af = AudioFile(path="/m/t.wav", filename="t.wav", extension=".wav",
                       file_size_mb=50.0, is_supported=True)
        assert get_source_quality_warning(af) is None

    def test_flac_no_warning(self):
        af = AudioFile(path="/m/t.flac", filename="t.flac", extension=".flac",
                       file_size_mb=50.0, is_supported=True)
        assert get_source_quality_warning(af) is None

    def test_low_bitrate_mp3_warns(self):
        af = self._make_with_bitrate("track.mp3", 128)
        warning = get_source_quality_warning(af)
        assert warning is not None
        assert "128 kbps" in warning
        assert "NOT restore" in warning

    def test_acceptable_mp3_no_warn(self):
        af = self._make_with_bitrate("track.mp3", 320)
        warning = get_source_quality_warning(af)
        assert warning is None

    def test_mp3_unknown_bitrate_warns(self):
        af = AudioFile(path="/m/t.mp3", filename="t.mp3", extension=".mp3",
                       file_size_mb=5.0, is_supported=True)
        af.bitrate_kbps = None
        warning = get_source_quality_warning(af)
        assert warning is not None
        assert "UNKNOWN" in warning

    def test_m4a_low_bitrate_warns(self):
        af = self._make_with_bitrate("track.m4a", 96)
        warning = get_source_quality_warning(af)
        assert warning is not None

    def test_ogg_low_bitrate_warns(self):
        af = self._make_with_bitrate("track.ogg", 128)
        warning = get_source_quality_warning(af)
        assert warning is not None
