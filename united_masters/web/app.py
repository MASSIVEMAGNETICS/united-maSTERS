"""
app.py — Flask web application for the UnitedMasters Release Workbench.
"""

from __future__ import annotations

import threading
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, redirect, render_template, request, url_for

from united_masters import __version__

app = Flask(__name__)
app.secret_key = "um-workbench-dev-key"

# In-memory job store: {job_id: {"status": ..., "result": ...}}
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html", version=__version__)


@app.route("/process", methods=["POST"])
def process():
    input_dir = request.form.get("input_dir", "").strip()
    preset = request.form.get("preset", "streaming_safe")
    raw_formats = request.form.getlist("formats")
    formats = raw_formats if raw_formats else ["wav_16_44", "mp3_320", "flac"]

    if not input_dir:
        return render_template(
            "index.html",
            version=__version__,
            error="Please provide an input directory path.",
        )

    # Resolve to an absolute path and confirm it is a real directory.
    # This prevents relative-path traversal and symlink tricks.
    try:
        resolved = Path(input_dir).resolve()
    except Exception:
        return render_template(
            "index.html",
            version=__version__,
            error="Invalid directory path.",
        )

    if not resolved.is_dir():
        return render_template(
            "index.html",
            version=__version__,
            error=f"Directory not found: {input_dir}",
        )

    input_dir = str(resolved)

    job_id = str(uuid.uuid4())
    output_dir = str(Path(input_dir) / "_output")

    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "result": None, "error": None}

    thread = threading.Thread(
        target=_run_pipeline_job,
        args=(job_id, input_dir, output_dir, preset, formats),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("results", job_id=job_id))


@app.route("/results/<job_id>")
def results(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)

    if job is None:
        return render_template(
            "index.html",
            version=__version__,
            error=f"Job '{job_id}' not found.",
        ), 404

    if job["status"] == "running":
        # Auto-refresh every 3 seconds while running
        return render_template(
            "results.html",
            version=__version__,
            job_id=job_id,
            status="running",
            result=None,
            error=None,
        )

    if job["status"] == "error":
        return render_template(
            "results.html",
            version=__version__,
            job_id=job_id,
            status="error",
            result=None,
            error=job.get("error", "Unknown error"),
        )

    return render_template(
        "results.html",
        version=__version__,
        job_id=job_id,
        status="done",
        result=job["result"],
        error=None,
    )


@app.route("/api/status/<job_id>")
def job_status(job_id: str):
    """JSON endpoint for polling job status."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        return jsonify({"status": "not_found"}), 404
    return jsonify({"status": job["status"]})


# ---------------------------------------------------------------------------
# Background job runner
# ---------------------------------------------------------------------------

def _run_pipeline_job(
    job_id: str,
    input_dir: str,
    output_dir: str,
    preset: str,
    formats: list,
) -> None:
    try:
        from united_masters.pipeline import PipelineConfig, run_pipeline  # noqa: PLC0415

        config = PipelineConfig(
            input_dir=input_dir,
            output_dir=output_dir,
            mastering_preset=preset,
            export_formats=formats,
        )
        pipeline_result = run_pipeline(config)
        serialised = _serialise_result(pipeline_result)

        with _jobs_lock:
            _jobs[job_id] = {"status": "done", "result": serialised, "error": None}
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": None,
                "error": f"{exc}\n{traceback.format_exc()}",
            }


def _serialise_result(result) -> Dict[str, Any]:
    """Convert PipelineResult to a JSON-serialisable dict for the template."""
    files = [
        {"filename": f.filename, "path": f.path, "size_mb": f.file_size_mb}
        for f in result.input_files
    ]

    analyses = {}
    for af in result.input_files:
        an = result.audio_analyses.get(af.path)
        if an:
            analyses[af.filename] = {
                "duration_seconds": an.duration_seconds,
                "sample_rate": an.sample_rate,
                "bit_depth": an.bit_depth,
                "channels": an.channels,
                "integrated_lufs": an.integrated_lufs,
                "true_peak_dbfs": an.true_peak_dbfs,
                "crest_factor_db": an.crest_factor_db,
                "is_clipped": an.is_clipped,
                "dc_offset": an.dc_offset,
                "silence_at_start_ms": an.silence_at_start_ms,
                "silence_at_end_ms": an.silence_at_end_ms,
                "estimated_bpm": an.estimated_bpm,
                "error": an.error,
            }

    qc_reports = []
    for report in result.qc_reports:
        qc_reports.append({
            "file_path": report.file_path,
            "filename": Path(report.file_path).name,
            "passed": report.passed,
            "error_count": report.error_count,
            "warning_count": report.warning_count,
            "issues": [
                {"severity": i.severity, "code": i.code, "message": i.message}
                for i in report.issues
            ],
        })

    album_qc = [
        {"severity": i.severity, "code": i.code, "message": i.message}
        for i in result.album_qc_issues
    ]

    presets = {}
    for af in result.input_files:
        rec = result.preset_recommendations.get(af.path, {})
        if rec:
            presets[af.filename] = rec

    encoded = {}
    for af in result.input_files:
        enc_list = result.encoded_files.get(af.path, [])
        encoded[af.filename] = [
            {
                "format_key": e.format_key,
                "output_path": e.output_path,
                "success": e.success,
                "warning": e.warning,
                "error": e.error,
            }
            for e in enc_list
        ]

    manifest = None
    if result.manifest:
        m = result.manifest
        manifest = {
            "release_title": m.release_title,
            "artist": m.artist,
            "release_date": m.release_date,
            "total_duration_seconds": m.total_duration_seconds,
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
                }
                for t in m.tracks
            ],
        }

    consistency = None
    if result.consistency_report:
        cr = result.consistency_report
        consistency = {
            "mean_lufs": cr.mean_lufs,
            "lufs_variance": cr.lufs_variance,
            "loudness_balanced": cr.loudness_balanced,
            "recommended_target_lufs": cr.recommended_target_lufs,
            "outlier_tracks": cr.outlier_tracks,
            "sequence_suggestion": cr.sequence_suggestion,
        }

    artwork = None
    if result.artwork_info:
        ai = result.artwork_info
        artwork = {
            "path": ai.path,
            "width": ai.width,
            "height": ai.height,
            "format": ai.format,
            "file_size_kb": ai.file_size_kb,
            "is_square": ai.is_square,
            "meets_minimum_size": ai.meets_minimum_size,
            "color_mode": ai.color_mode,
            "warnings": ai.warnings,
        }

    return {
        "files": files,
        "analyses": analyses,
        "qc_reports": qc_reports,
        "album_qc": album_qc,
        "preset_recommendations": presets,
        "encoded": encoded,
        "manifest": manifest,
        "consistency": consistency,
        "artwork": artwork,
        "launch_checklist": result.launch_checklist,
        "risk_score": result.risk_score,
        "source_quality_warnings": result.source_quality_warnings,
        "errors": result.errors,
    }


if __name__ == "__main__":
    # Do not run with debug=True in production — use a WSGI server instead.
    app.run(debug=False, port=5000)
