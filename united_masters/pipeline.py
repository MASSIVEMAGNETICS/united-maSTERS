"""
pipeline.py — Main pipeline orchestrator.

Runs all processing steps in order and returns a PipelineResult even when
individual steps fail, so partial results are always available.
"""

from __future__ import annotations

import os
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from united_masters.core.analyze import AudioAnalysis, analyze_file, recommend_preset
from united_masters.core.artwork import ArtworkInfo, check_artwork
from united_masters.core.consistency import ConsistencyReport, analyze_album_consistency
from united_masters.core.encode import EncodeResult, encode_batch
from united_masters.core.ingest import AudioFile, detect_duplicates, get_source_quality_warning, scan_folder
from united_masters.core.manifest import ReleaseManifest, generate_manifest, write_manifest_csv, write_manifest_json
from united_masters.core.mastering import get_recommendation_explanation
from united_masters.core.metadata import TrackMetadata, read_metadata, validate_metadata
from united_masters.core.promo import PromoAssets, extract_teaser_snippet, generate_launch_checklist, generate_tracklist_text
from united_masters.core.qc import QCReport, run_album_qc, run_qc


@dataclass
class PipelineConfig:
    input_dir: str
    output_dir: str
    mastering_preset: str = "streaming_safe"
    export_formats: List[str] = field(default_factory=lambda: ["wav_16_44", "mp3_320", "flac"])
    run_qc: bool = True
    generate_manifest: bool = True
    generate_promo: bool = True


@dataclass
class PipelineResult:
    input_files: List[AudioFile] = field(default_factory=list)
    audio_analyses: Dict[str, AudioAnalysis] = field(default_factory=dict)
    qc_reports: List[QCReport] = field(default_factory=list)
    album_qc_issues: List[Any] = field(default_factory=list)
    consistency_report: Optional[ConsistencyReport] = None
    preset_recommendations: Dict[str, Any] = field(default_factory=dict)
    manifest: Optional[ReleaseManifest] = None
    encoded_files: Dict[str, List[EncodeResult]] = field(default_factory=dict)
    launch_checklist: List[Dict[str, Any]] = field(default_factory=list)
    promo_assets: Optional[PromoAssets] = None
    artwork_info: Optional[ArtworkInfo] = None
    metadata_list: List[TrackMetadata] = field(default_factory=list)
    source_quality_warnings: List[str] = field(default_factory=list)
    risk_score: float = 0.0
    errors: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0


def run_pipeline(config: PipelineConfig) -> PipelineResult:
    """
    Execute the full processing pipeline. Each step is wrapped in a try/except
    so a failure in one step does not abort the rest.
    """
    result = PipelineResult()
    out_dir = config.output_dir
    os.makedirs(out_dir, exist_ok=True)

    # ------------------------------------------------------------------
    # Step 1 — Ingest files
    # ------------------------------------------------------------------
    try:
        all_files = scan_folder(config.input_dir)
        supported = [f for f in all_files if f.is_supported]
        result.input_files = supported

        for af in supported:
            warn = get_source_quality_warning(af)
            if warn:
                result.source_quality_warnings.append(warn)

        duplicates = detect_duplicates(supported)
        if duplicates:
            for group in duplicates:
                names = ", ".join(f.filename for f in group)
                result.errors.append(f"Possible duplicates: {names}")
    except Exception as exc:
        result.errors.append(f"Ingest failed: {exc}\n{traceback.format_exc()}")
        return result  # Nothing to process

    if not result.input_files:
        result.errors.append(f"No supported audio files found in '{config.input_dir}'.")
        return result

    # ------------------------------------------------------------------
    # Step 2 — Analyse each file
    # ------------------------------------------------------------------
    for af in result.input_files:
        try:
            analysis = analyze_file(af.path)
            result.audio_analyses[af.path] = analysis
        except Exception as exc:
            err_analysis = AudioAnalysis()
            err_analysis.error = str(exc)
            result.audio_analyses[af.path] = err_analysis
            result.errors.append(f"Analysis failed for '{af.filename}': {exc}")

    analyses = [result.audio_analyses[af.path] for af in result.input_files]

    # ------------------------------------------------------------------
    # Step 3 — QC each file
    # ------------------------------------------------------------------
    if config.run_qc:
        for af in result.input_files:
            try:
                analysis = result.audio_analyses[af.path]
                report = run_qc(af, analysis)
                result.qc_reports.append(report)
            except Exception as exc:
                result.errors.append(f"QC failed for '{af.filename}': {exc}")

        # ------------------------------------------------------------------
        # Step 4 — Album-level QC
        # ------------------------------------------------------------------
        try:
            result.album_qc_issues = run_album_qc(result.input_files, analyses)
        except Exception as exc:
            result.errors.append(f"Album QC failed: {exc}")

    # ------------------------------------------------------------------
    # Step 5 — Album consistency + preset recommendations
    # ------------------------------------------------------------------
    try:
        result.consistency_report = analyze_album_consistency(result.input_files, analyses)
    except Exception as exc:
        result.errors.append(f"Consistency analysis failed: {exc}")

    for af in result.input_files:
        try:
            analysis = result.audio_analyses[af.path]
            preset_name = recommend_preset(analysis) if not analysis.error else config.mastering_preset
            explanation = get_recommendation_explanation(preset_name, analysis)
            result.preset_recommendations[af.path] = explanation
        except Exception as exc:
            result.errors.append(f"Preset recommendation failed for '{af.filename}': {exc}")

    # ------------------------------------------------------------------
    # Step 6 — Encode delivery formats
    # ------------------------------------------------------------------
    encode_dir = str(Path(out_dir) / "encoded")
    for af in result.input_files:
        try:
            encode_results = encode_batch(af.path, encode_dir, config.export_formats)
            result.encoded_files[af.path] = encode_results
        except Exception as exc:
            result.errors.append(f"Encoding failed for '{af.filename}': {exc}")

    # ------------------------------------------------------------------
    # Step 7 — Read / validate metadata
    # ------------------------------------------------------------------
    for af in result.input_files:
        try:
            meta = read_metadata(af.path)
            issues = validate_metadata(meta)
            if issues:
                for issue in issues:
                    result.errors.append(f"Metadata issue in '{af.filename}': {issue}")
            result.metadata_list.append(meta)
        except Exception as exc:
            result.metadata_list.append(TrackMetadata())
            result.errors.append(f"Metadata read failed for '{af.filename}': {exc}")

    # ------------------------------------------------------------------
    # Step 8 — Generate manifest
    # ------------------------------------------------------------------
    if config.generate_manifest:
        try:
            manifest = generate_manifest(
                result.metadata_list,
                analyses,
                result.qc_reports or None,
                filenames=[af.filename for af in result.input_files],
            )
            result.manifest = manifest

            manifest_dir = str(Path(out_dir) / "manifest")
            os.makedirs(manifest_dir, exist_ok=True)
            write_manifest_json(manifest, str(Path(manifest_dir) / "manifest.json"))
            write_manifest_csv(manifest, str(Path(manifest_dir) / "manifest.csv"))
        except Exception as exc:
            result.errors.append(f"Manifest generation failed: {exc}\n{traceback.format_exc()}")

    # ------------------------------------------------------------------
    # Step 9 — Artwork
    # ------------------------------------------------------------------
    artwork_info: Optional[ArtworkInfo] = None
    try:
        artwork_path = _find_artwork(config.input_dir)
        if artwork_path:
            artwork_info = check_artwork(artwork_path)
            result.artwork_info = artwork_info
    except Exception as exc:
        result.errors.append(f"Artwork check failed: {exc}")

    # ------------------------------------------------------------------
    # Step 10 — Promo assets
    # ------------------------------------------------------------------
    if config.generate_promo:
        promo_dir = str(Path(out_dir) / "promo")
        os.makedirs(promo_dir, exist_ok=True)
        promo = PromoAssets()

        try:
            if result.manifest:
                tracklist = generate_tracklist_text(result.manifest)
                tl_path = str(Path(promo_dir) / "tracklist.txt")
                with open(tl_path, "w", encoding="utf-8") as fh:
                    fh.write(tracklist)
                promo.tracklist_text_path = tl_path
        except Exception as exc:
            result.errors.append(f"Tracklist generation failed: {exc}")

        # Teasers for each track
        for af in result.input_files:
            try:
                teaser_out = str(Path(promo_dir) / f"{Path(af.path).stem}_teaser.mp3")
                if extract_teaser_snippet(af.path, teaser_out):
                    promo.teaser_paths.append(teaser_out)
            except Exception as exc:
                result.errors.append(f"Teaser extraction failed for '{af.filename}': {exc}")

        result.promo_assets = promo

    # ------------------------------------------------------------------
    # Step 11 — Launch checklist + risk score
    # ------------------------------------------------------------------
    try:
        checklist = generate_launch_checklist(
            result.manifest or ReleaseManifest(release_title="Unknown", artist="Unknown"),
            result.qc_reports,
            artwork_info,
        )
        result.launch_checklist = checklist
    except Exception as exc:
        result.errors.append(f"Launch checklist generation failed: {exc}")

    try:
        from united_masters.core.manifest import generate_submission_checklist  # noqa: PLC0415

        sub_check = generate_submission_checklist(
            result.manifest or ReleaseManifest(release_title="Unknown", artist="Unknown"),
            result.qc_reports,
            artwork_info,
        )
        result.risk_score = float(sub_check.get("risk_score", 0))
    except Exception as exc:
        result.errors.append(f"Risk score calculation failed: {exc}")

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_artwork(folder: str) -> Optional[str]:
    """Look for a JPEG or PNG file in *folder* that might be artwork."""
    image_names = {
        "cover", "artwork", "front", "album", "art", "folder", "thumb",
    }
    for path in Path(folder).iterdir():
        if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
            stem_lower = path.stem.lower()
            if any(n in stem_lower for n in image_names):
                return str(path)
    return None
