"""
app.py — Flask web application for the UnitedMasters Release Workbench.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict

from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from united_masters import __version__
from united_masters.logging_config import configure_logging

configure_logging()
app = Flask(__name__)

_secret = os.environ.get("UM_SECRET_KEY")
if not _secret:
    logging.warning(
        "UM_SECRET_KEY environment variable not set — using insecure default. "
        "Set UM_SECRET_KEY before deploying."
    )
    _secret = "um-workbench-dev-key"
app.secret_key = _secret

# Limit incoming request body to 16 MB (form fields only — no file upload).
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

# Sensitive system path prefixes that are never valid release-folder targets.
_BLOCKED_PATH_PREFIXES = (
    "/etc",
    "/bin",
    "/sbin",
    "/usr/bin",
    "/usr/sbin",
    "/boot",
    "/proc",
    "/sys",
    "/dev",
    "/run",
    "/var/run",
    "/root",
    "/tmp",
)

# Allowed preset keys — validated server-side before passing to the pipeline.
_ALLOWED_PRESETS = {
    "streaming_safe",
    "loud_modern_rap",
    "warm_hip_hop",
    "vocal_forward",
    "trap_808_heavy",
    "clean_dynamic",
}

# Allowed export format keys — validated server-side.
_ALLOWED_FORMATS = {
    "wav_16_44",
    "wav_24_44",
    "wav_24_48",
    "wav_24_96",
    "mp3_128",
    "mp3_192",
    "mp3_256",
    "mp3_320",
    "mp3_vbr",
    "flac",
}

# In-memory job store: {job_id: {"status": ..., "result": ..., "created_at": float}}
_jobs: Dict[str, Dict[str, Any]] = {}
_jobs_lock = threading.Lock()

# Jobs older than this are evicted from the in-memory store (seconds).
_JOB_TTL_SECONDS = 3600  # 1 hour


def _evict_old_jobs() -> None:
    """Remove completed jobs older than _JOB_TTL_SECONDS from the store."""
    cutoff = time.monotonic() - _JOB_TTL_SECONDS
    with _jobs_lock:
        expired = [
            jid for jid, job in _jobs.items()
            if job.get("status") != "running" and job.get("created_at", 0) < cutoff
        ]
        for jid in expired:
            del _jobs[jid]


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

@app.after_request
def add_security_headers(response: Response) -> Response:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "connect-src 'self';"
    )
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    """Liveness probe — returns 200 OK with a simple JSON payload."""
    return jsonify({"status": "ok", "version": __version__}), 200

@app.route("/")
def index():
    return render_template("index.html", version=__version__)


@app.route("/process", methods=["POST"])
def process():
    input_dir = request.form.get("input_dir", "").strip()
    raw_preset = request.form.get("preset", "streaming_safe")
    raw_formats = request.form.getlist("formats")

    # Validate preset against the allow-list.
    preset = raw_preset if raw_preset in _ALLOWED_PRESETS else "streaming_safe"

    # Validate each format key against the allow-list; silently drop unknowns.
    formats = [f for f in raw_formats if f in _ALLOWED_FORMATS]
    if not formats:
        formats = ["wav_16_44", "mp3_320", "flac"]

    if not input_dir:
        return render_template(
            "index.html",
            version=__version__,
            error="Please provide an input directory path.",
        )

    # Resolve to an absolute, canonical path so symlinks and relative segments
    # (e.g. "../../../etc") are fully expanded before any further checks.
    # This application is intentionally a local filesystem tool — the user
    # supplies a directory path that the pipeline reads from.  The resolved
    # path is checked against a blocklist of sensitive system directories
    # before any further use.
    try:
        resolved = Path(input_dir).resolve()
    except Exception:
        return render_template(
            "index.html",
            version=__version__,
            error="Invalid directory path.",
        )

    # Block well-known sensitive system directories.
    resolved_str = str(resolved)
    for blocked in _BLOCKED_PATH_PREFIXES:
        if resolved_str == blocked or resolved_str.startswith(blocked + "/"):
            return render_template(
                "index.html",
                version=__version__,
                error="Access to system directories is not permitted.",
            )

    # Confirm it is a real directory only after the blocklist check.
    if not resolved.is_dir():  # noqa: S603 — path validated above
        return render_template(
            "index.html",
            version=__version__,
            error=f"Directory not found: {Path(resolved_str).name}",
        )

    input_dir = resolved_str

    job_id = str(uuid.uuid4())
    output_dir = str(Path(input_dir) / "_output")

    _evict_old_jobs()

    with _jobs_lock:
        _jobs[job_id] = {"status": "running", "result": None, "error": None, "created_at": time.monotonic()}

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
            _jobs[job_id] = {"status": "done", "result": serialised, "error": None, "created_at": _jobs[job_id]["created_at"]}
    except Exception as exc:
        with _jobs_lock:
            _jobs[job_id] = {
                "status": "error",
                "result": None,
                "error": f"{exc}\n{traceback.format_exc()}",
                "created_at": _jobs[job_id]["created_at"],
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
