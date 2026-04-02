"""
cli.py — Command-line interface using Click.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from united_masters import __version__


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _echo_header() -> None:
    click.echo(click.style(f"\n  UnitedMasters Release Workbench v{__version__}", fg="magenta", bold=True))
    click.echo(click.style("  ─" * 36, fg="magenta"))


def _echo_section(title: str) -> None:
    click.echo(click.style(f"\n▶  {title}", fg="cyan", bold=True))


def _echo_ok(msg: str) -> None:
    click.echo(click.style(f"  ✔  {msg}", fg="green"))


def _echo_warn(msg: str) -> None:
    click.echo(click.style(f"  ⚠  {msg}", fg="yellow"))


def _echo_err(msg: str) -> None:
    click.echo(click.style(f"  ✘  {msg}", fg="red"))


def _echo_info(msg: str) -> None:
    click.echo(f"     {msg}")


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
@click.version_option(__version__, prog_name="united-masters")
def cli() -> None:
    """UnitedMasters Release Workbench — local-first music release factory."""


# ---------------------------------------------------------------------------
# process
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--output", "-o", default=None, help="Output directory (default: <input_dir>/_output)")
@click.option("--preset", "-p", default="streaming_safe",
              type=click.Choice([
                  "streaming_safe", "loud_modern_rap", "warm_hip_hop",
                  "vocal_forward", "trap_808_heavy", "clean_dynamic",
              ]),
              help="Mastering preset family.")
@click.option("--formats", "-f", default="wav_16_44,mp3_320,flac",
              help="Comma-separated export format keys.")
@click.option("--no-qc", "skip_qc", is_flag=True, default=False, help="Skip QC checks.")
@click.option("--no-manifest", "skip_manifest", is_flag=True, default=False, help="Skip manifest generation.")
@click.option("--no-promo", "skip_promo", is_flag=True, default=False, help="Skip promo asset generation.")
def process(
    input_dir: str,
    output: str,
    preset: str,
    formats: str,
    skip_qc: bool,
    skip_manifest: bool,
    skip_promo: bool,
) -> None:
    """Run the full release pipeline on INPUT_DIR."""
    from united_masters.pipeline import PipelineConfig, run_pipeline  # noqa: PLC0415

    _echo_header()

    output_dir = output or str(Path(input_dir) / "_output")
    format_keys = [f.strip() for f in formats.split(",") if f.strip()]

    config = PipelineConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        mastering_preset=preset,
        export_formats=format_keys,
        run_qc=not skip_qc,
        generate_manifest=not skip_manifest,
        generate_promo=not skip_promo,
    )

    _echo_section(f"Processing: {input_dir}")
    _echo_info(f"Output:  {output_dir}")
    _echo_info(f"Preset:  {preset}")
    _echo_info(f"Formats: {', '.join(format_keys)}")

    with click.progressbar(length=11, label="  Running pipeline", width=40) as bar:
        result = run_pipeline(config)
        bar.update(11)

    # Source quality warnings
    if result.source_quality_warnings:
        _echo_section("Source Quality Warnings")
        for w in result.source_quality_warnings:
            _echo_warn(w)

    # Files
    _echo_section(f"Files ingested: {len(result.input_files)}")
    for af in result.input_files:
        _echo_info(f"{af.filename}  ({af.file_size_mb:.2f} MB)")

    # Analysis
    _echo_section("Audio Analysis")
    for af in result.input_files:
        an = result.audio_analyses.get(af.path)
        if an and not an.error:
            _echo_info(
                f"{af.filename}: {an.duration_seconds:.1f}s  "
                f"{an.integrated_lufs:.1f} LUFS  "
                f"Peak {an.true_peak_dbfs:.1f} dBFS  "
                f"{an.sample_rate} Hz  "
                f"{'CLIPPED' if an.is_clipped else 'OK'}"
            )
        elif an and an.error:
            _echo_warn(f"{af.filename}: {an.error}")

    # Preset recommendations
    _echo_section("Mastering Preset Recommendations")
    for af in result.input_files:
        rec = result.preset_recommendations.get(af.path, {})
        if rec:
            _echo_ok(f"{af.filename} → {rec.get('display_name', rec.get('preset', '?'))}")
            _echo_info(rec.get("why", ""))

    # QC
    if not skip_qc:
        _echo_section("QC Report")
        for report in result.qc_reports:
            fname = Path(report.file_path).name
            if report.passed:
                _echo_ok(f"{fname}: PASSED ({report.warning_count} warning(s))")
            else:
                _echo_err(f"{fname}: FAILED ({report.error_count} error(s), {report.warning_count} warning(s))")
            for issue in report.issues:
                fn = {"error": _echo_err, "warning": _echo_warn}.get(issue.severity, _echo_info)
                fn(f"  [{issue.code}] {issue.message}")

        for issue in result.album_qc_issues:
            _echo_warn(f"[ALBUM] [{issue.code}] {issue.message}")

    # Consistency
    if result.consistency_report:
        cr = result.consistency_report
        _echo_section("Album Consistency")
        _echo_info(f"Mean LUFS: {cr.mean_lufs:.1f}  Variance: {cr.lufs_variance:.1f} dB")
        _echo_info(f"Recommended target: {cr.recommended_target_lufs:.1f} LUFS")
        if cr.outlier_tracks:
            for ot in cr.outlier_tracks:
                _echo_warn(f"Outlier: {ot['filename']}  {ot['lufs']:.1f} LUFS  ({ot['delta_from_mean']:+.1f} dB from mean)")
        if cr.sequence_suggestion:
            _echo_info("Suggested track order: " + " → ".join(cr.sequence_suggestion))

    # Encoded files
    _echo_section("Encoded Deliverables")
    for af in result.input_files:
        enc_list = result.encoded_files.get(af.path, [])
        for enc in enc_list:
            if enc.success:
                _echo_ok(f"{af.filename} → {enc.format_key}: {enc.output_path}")
                if enc.warning:
                    _echo_warn(enc.warning)
            else:
                _echo_err(f"{af.filename} → {enc.format_key}: {enc.error}")

    # Manifest
    if result.manifest:
        _echo_section("Manifest")
        m = result.manifest
        _echo_ok(f"{m.release_title} by {m.artist}  ({len(m.tracks)} tracks  {m.total_duration_seconds:.0f}s)")

    # Launch checklist
    if result.launch_checklist:
        _echo_section("Launch Checklist")
        icons = {"done": "✔", "warning": "⚠", "todo": "○"}
        colours = {"done": "green", "warning": "yellow", "todo": "white"}
        for c in result.launch_checklist:
            icon = icons.get(c["status"], "?")
            colour = colours.get(c["status"], "white")
            note = f"  — {c['notes']}" if c.get("notes") else ""
            click.echo(click.style(f"  {icon}  {c['item']}{note}", fg=colour))

    # Risk score
    _echo_section("Risk Score")
    score = result.risk_score
    level_colour = "green" if score <= 20 else "yellow" if score <= 50 else "red"
    click.echo(click.style(f"  {score:.0f}/100", fg=level_colour, bold=True))

    # Pipeline errors
    if result.errors:
        _echo_section("Pipeline Errors / Warnings")
        for err in result.errors:
            _echo_warn(err)

    click.echo("")
    _echo_ok(f"Done. Output: {output_dir}\n")


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
def analyze(input_dir: str) -> None:
    """Analyse audio files in INPUT_DIR and print a report."""
    from united_masters.core.analyze import analyze_file  # noqa: PLC0415
    from united_masters.core.ingest import scan_folder  # noqa: PLC0415

    _echo_header()
    _echo_section(f"Analysing: {input_dir}")

    files = [f for f in scan_folder(input_dir) if f.is_supported]
    if not files:
        _echo_err("No supported audio files found.")
        sys.exit(1)

    for af in files:
        click.echo(click.style(f"\n  {af.filename}", bold=True))
        an = analyze_file(af.path)
        if an.error:
            _echo_err(f"Analysis error: {an.error}")
            continue
        rows = [
            ("Duration", f"{an.duration_seconds:.2f}s"),
            ("Sample rate", f"{an.sample_rate} Hz"),
            ("Bit depth", f"{an.bit_depth}-bit"),
            ("Channels", str(an.channels)),
            ("Integrated LUFS", f"{an.integrated_lufs:.2f}"),
            ("True peak", f"{an.true_peak_dbfs:.2f} dBFS"),
            ("Crest factor", f"{an.crest_factor_db:.1f} dB"),
            ("Clipped", "YES ⚠" if an.is_clipped else "No"),
            ("DC offset", f"{an.dc_offset:+.5f}"),
            ("Silence (head)", f"{an.silence_at_start_ms:.0f} ms"),
            ("Silence (tail)", f"{an.silence_at_end_ms:.0f} ms"),
            ("Est. BPM", f"{an.estimated_bpm:.1f}" if an.estimated_bpm else "N/A"),
        ]
        for k, v in rows:
            click.echo(f"    {k:<22} {v}")


# ---------------------------------------------------------------------------
# presets
# ---------------------------------------------------------------------------

@cli.command()
def presets() -> None:
    """List all available mastering presets."""
    from united_masters.core.mastering import PRESETS  # noqa: PLC0415

    _echo_header()
    _echo_section("Available Mastering Presets")

    for key, data in PRESETS.items():
        click.echo(click.style(f"\n  {key}", fg="cyan", bold=True))
        click.echo(f"    Display name : {data['display_name']}")
        click.echo(f"    LUFS target  : {data['lufs_target_min']} to {data['lufs_target_max']}")
        click.echo(f"    True peak    : {data['true_peak_ceiling']} dBTP")
        click.echo(f"    Use case     : {data['use_case']}")
        click.echo(f"    Description  : {data['description']}")
        click.echo(f"    Chain stages : {', '.join(s['stage'] for s in data['chain'])}")


# ---------------------------------------------------------------------------
# qc
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
def qc(input_dir: str) -> None:
    """Run QC checks on audio files in INPUT_DIR."""
    from united_masters.core.analyze import analyze_file  # noqa: PLC0415
    from united_masters.core.ingest import scan_folder  # noqa: PLC0415
    from united_masters.core.qc import run_album_qc, run_qc  # noqa: PLC0415

    _echo_header()
    _echo_section(f"QC: {input_dir}")

    files = [f for f in scan_folder(input_dir) if f.is_supported]
    if not files:
        _echo_err("No supported audio files found.")
        sys.exit(1)

    analyses = []
    reports = []
    for af in files:
        an = analyze_file(af.path)
        analyses.append(an)
        report = run_qc(af, an)
        reports.append(report)

        fname = click.style(af.filename, bold=True)
        status = click.style("PASS", fg="green") if report.passed else click.style("FAIL", fg="red")
        click.echo(f"\n  {fname}  [{status}]")
        for issue in report.issues:
            colour = {"error": "red", "warning": "yellow", "info": "cyan"}.get(issue.severity, "white")
            click.echo(click.style(f"    [{issue.severity.upper()}] {issue.code}: {issue.message}", fg=colour))

    album_issues = run_album_qc(files, analyses)
    if album_issues:
        _echo_section("Album-level QC")
        for issue in album_issues:
            colour = {"error": "red", "warning": "yellow"}.get(issue.severity, "white")
            click.echo(click.style(f"  [{issue.severity.upper()}] {issue.code}: {issue.message}", fg=colour))

    total_errors = sum(r.error_count for r in reports)
    total_warnings = sum(r.warning_count for r in reports)
    click.echo("")
    if total_errors:
        _echo_err(f"QC complete: {total_errors} error(s), {total_warnings} warning(s).")
        sys.exit(1)
    else:
        _echo_ok(f"QC complete: {total_errors} error(s), {total_warnings} warning(s).")


if __name__ == "__main__":
    cli()
