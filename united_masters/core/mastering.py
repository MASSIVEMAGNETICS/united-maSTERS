"""
mastering.py — Mastering preset definitions with full explainability.

Each preset describes a signal chain as a series of processing stages.
The app does NOT apply DSP directly (that requires DAW plug-ins or specialist
libraries); instead it produces an actionable processing roadmap that the
engineer or automated tool can follow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from united_masters.core.analyze import AudioAnalysis


# ---------------------------------------------------------------------------
# Preset data
# ---------------------------------------------------------------------------

PRESETS: Dict[str, Dict[str, Any]] = {
    "streaming_safe": {
        "display_name": "Streaming Safe",
        "lufs_target_min": -11.5,
        "lufs_target_max": -10.5,
        "true_peak_ceiling": -1.0,
        "description": (
            "Safe for all major streaming platforms (Spotify, Apple Music, Tidal, YouTube). "
            "Balanced loudness without pumping or distortion. Passes every platform's "
            "loudness normalisation pass without being turned down significantly."
        ),
        "use_case": "Most general releases, pop, R&B, soul",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "Apply 30 Hz high-pass filter to remove sub-sonic rumble.",
                "tradeoff": "Minimal — removes inaudible energy that wastes headroom.",
            },
            {
                "stage": "tonal_correction",
                "action": "Subtle broad EQ curve to balance low/mid/high energy.",
                "tradeoff": "Colouration risk if applied too aggressively.",
            },
            {
                "stage": "glue_compression",
                "action": "Gentle bus compression (ratio 2:1, slow attack) for cohesion.",
                "tradeoff": "Reduces transient punch if threshold is too low.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak transparent limiter ceiling at -1.0 dBTP.",
                "tradeoff": "Possible inter-sample distortion if gains are too high upstream.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise integrated loudness to target window (-11.5 to -10.5 LUFS).",
                "tradeoff": "None — gain-only operation, does not alter dynamics.",
            },
        ],
    },
    "loud_modern_rap": {
        "display_name": "Loud Modern Rap",
        "lufs_target_min": -9.5,
        "lufs_target_max": -8.5,
        "true_peak_ceiling": -1.0,
        "description": (
            "Aggressive loudness target suited to contemporary rap/hip-hop where "
            "in-your-face presence is expected. Will be turned down by streaming "
            "normalisation — the effect is heard in non-normalised contexts (clubs, "
            "radio) and as perceived density."
        ),
        "use_case": "Modern rap, drill, boom-bap with dense production",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "40 Hz high-pass to tighten low end.",
                "tradeoff": "Slight sub-bass reduction.",
            },
            {
                "stage": "low_end_containment",
                "action": "Side-chain-aware low-end management to keep kick/808 distinct.",
                "tradeoff": "Over-processing can make bass feel thin.",
            },
            {
                "stage": "clipper",
                "action": "Soft clipper to shave transients and gain 2–3 dB of perceived loudness.",
                "tradeoff": "Harmonic distortion increases — subtle saturation colour is a feature here.",
            },
            {
                "stage": "glue_compression",
                "action": "Medium bus compression (ratio 4:1) for density.",
                "tradeoff": "Drum transients are reduced; 'knock' may suffer.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak limiter at -1.0 dBTP.",
                "tradeoff": "Heavy limiting artefacts if mix is too loud entering this stage.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise to -9.5 to -8.5 LUFS window.",
                "tradeoff": "Aggressive target — will be turned down ~2 dB on Spotify/Apple Music.",
            },
        ],
    },
    "warm_hip_hop": {
        "display_name": "Warm Hip-Hop",
        "lufs_target_min": -10.5,
        "lufs_target_max": -9.5,
        "true_peak_ceiling": -1.0,
        "description": (
            "Classic warm hip-hop sound. Preserves low-mid body, adds analogue-like "
            "saturation, keeps snare and vocal presence without harshness."
        ),
        "use_case": "Classic hip-hop, boom-bap, jazz-rap, lo-fi",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "30 Hz high-pass — preserve warmth down to low bass.",
                "tradeoff": "Minimal.",
            },
            {
                "stage": "low_mid_body",
                "action": "Gentle +1 dB shelf around 200 Hz to add warmth and weight.",
                "tradeoff": "Can add muddiness if mix already has too much 200–400 Hz.",
            },
            {
                "stage": "soft_transient_shave",
                "action": "Slow-attack transient shaper to glue mix without killing punch.",
                "tradeoff": "Snare/drum attack slightly rounded.",
            },
            {
                "stage": "glue_compression",
                "action": "Soft knee 2:1 compression for analogue warmth.",
                "tradeoff": "Slight reduction in dynamic range.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak limiter at -1.0 dBTP.",
                "tradeoff": "Standard.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise to -10.5 to -9.5 LUFS.",
                "tradeoff": "Moderate loudness — suitable for streaming and download.",
            },
        ],
    },
    "vocal_forward": {
        "display_name": "Vocal Forward",
        "lufs_target_min": -10.5,
        "lufs_target_max": -9.0,
        "true_peak_ceiling": -1.0,
        "description": (
            "Designed for releases where vocal clarity and presence is the priority. "
            "Boosts 2–5 kHz presence region, controls harshness at 6–8 kHz, "
            "leaves instrumental dynamics largely untouched."
        ),
        "use_case": "R&B, melodic rap, singer-songwriter, pop ballads",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "30 Hz high-pass.",
                "tradeoff": "Minimal.",
            },
            {
                "stage": "presence_focus_2_5khz",
                "action": "Narrow +1.5 dB bell at 2.5 kHz to bring vocals forward.",
                "tradeoff": "Can cause fatigue if mix is already bright.",
            },
            {
                "stage": "harshness_control",
                "action": "Dynamic EQ cut at 6–8 kHz triggered by peaks — de-essing at master bus level.",
                "tradeoff": "May reduce air/shimmer on bright instruments.",
            },
            {
                "stage": "glue_compression",
                "action": "Light bus compression (1.5:1) — preserve dynamics.",
                "tradeoff": "Minimal.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak limiter at -1.0 dBTP.",
                "tradeoff": "Standard.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise to -10.5 to -9.0 LUFS.",
                "tradeoff": "Slightly louder target to ensure vocal presence survives normalisation.",
            },
        ],
    },
    "trap_808_heavy": {
        "display_name": "Trap / 808-Heavy",
        "lufs_target_min": -9.5,
        "lufs_target_max": -8.0,
        "true_peak_ceiling": -1.0,
        "description": (
            "Optimised for trap and 808-driven productions. Sub-bass mono below 110 Hz "
            "prevents phase issues on mono speakers. Anti-pump side-chain keeps "
            "808 pumping feel intentional rather than accidental."
        ),
        "use_case": "Trap, drill, auto-tune heavy, dark hip-hop",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "40 Hz high-pass for very tight sub.",
                "tradeoff": "Cuts deepest sub rumble.",
            },
            {
                "stage": "sub_control_mono_below_110hz",
                "action": "Mid/side processing: mono sum below 110 Hz, keep stereo above.",
                "tradeoff": "Essential for vinyl/mono compatibility. No audible loss on stereo playback.",
            },
            {
                "stage": "anti_pump_sidechain",
                "action": "Side-chain compressor triggered by kick to control 808 ducking.",
                "tradeoff": "If threshold is wrong, can make 808 feel disconnected from kick.",
            },
            {
                "stage": "clipper",
                "action": "Clipper after compression to maximise perceived loudness.",
                "tradeoff": "Heavy clipping degrades quality — keep gain reduction < 3 dB.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak limiter at -1.0 dBTP.",
                "tradeoff": "Standard.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise to -9.5 to -8.0 LUFS.",
                "tradeoff": "Very loud — will be attenuated on all streaming platforms.",
            },
        ],
    },
    "clean_dynamic": {
        "display_name": "Clean & Dynamic",
        "lufs_target_min": -13.0,
        "lufs_target_max": -11.0,
        "true_peak_ceiling": -1.0,
        "description": (
            "High dynamic range master suitable for audiophile platforms (Tidal HiFi, "
            "Qobuz, Bandcamp lossless) and licensing. Minimal processing — preserves "
            "the mix engineer's dynamics and intent."
        ),
        "use_case": "Jazz, classical, acoustic, singer-songwriter, audiophile releases",
        "chain": [
            {
                "stage": "high_pass_cleanup",
                "action": "20 Hz high-pass only — very gentle rumble removal.",
                "tradeoff": "Minimal.",
            },
            {
                "stage": "minimal_compression",
                "action": "Optional light compression (1.2:1 ratio) for occasional peaks only.",
                "tradeoff": "May be omitted entirely for fully dynamic masters.",
            },
            {
                "stage": "true_peak_limiter",
                "action": "True-peak limiter at -1.0 dBTP.",
                "tradeoff": "Standard.",
            },
            {
                "stage": "loudness_normalization",
                "action": "Normalise to -13.0 to -11.0 LUFS for dynamic headroom.",
                "tradeoff": "Will sound quieter in non-normalised contexts.",
            },
        ],
    },
}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------

@dataclass
class MasteringPreset:
    name: str
    display_name: str
    lufs_target_min: float
    lufs_target_max: float
    true_peak_ceiling: float
    description: str
    use_case: str
    chain: List[Dict[str, str]] = field(default_factory=list)

    @property
    def lufs_target_midpoint(self) -> float:
        return (self.lufs_target_min + self.lufs_target_max) / 2


def get_preset(name: str) -> MasteringPreset:
    """Return a MasteringPreset by key. Raises KeyError for unknown presets."""
    if name not in PRESETS:
        available = ", ".join(PRESETS.keys())
        raise KeyError(f"Unknown preset '{name}'. Available: {available}")
    data = PRESETS[name]
    return MasteringPreset(
        name=name,
        display_name=data["display_name"],
        lufs_target_min=data["lufs_target_min"],
        lufs_target_max=data["lufs_target_max"],
        true_peak_ceiling=data["true_peak_ceiling"],
        description=data["description"],
        use_case=data["use_case"],
        chain=data["chain"],
    )


def get_recommendation_explanation(
    preset_name: str, analysis: AudioAnalysis
) -> Dict[str, Any]:
    """
    Return a structured explanation dict describing WHY this preset was chosen
    and what the user should expect from each stage.
    """
    preset = get_preset(preset_name)

    why_parts: List[str] = []

    lufs = analysis.integrated_lufs
    crest = analysis.crest_factor_db
    bpm = analysis.estimated_bpm

    if lufs < -18:
        why_parts.append(f"Source is very quiet ({lufs:.1f} LUFS) — extra headroom preserved.")
    elif lufs > -8:
        why_parts.append(f"Source is already very loud ({lufs:.1f} LUFS) — minimal gain needed.")
    else:
        why_parts.append(f"Source loudness is {lufs:.1f} LUFS, within typical mix range.")

    if crest > 18:
        why_parts.append("High crest factor indicates a very dynamic recording — minimal compression recommended.")
    elif crest < 6:
        why_parts.append("Low crest factor suggests the mix is already heavily limited or compressed.")

    if bpm:
        why_parts.append(f"Estimated BPM: {bpm}.")

    if analysis.is_clipped:
        why_parts.append("⚠  Clipping detected in source — repair recommended before mastering.")

    chain_explanation = [
        f"Stage {i + 1} — {step['stage']}: {step['action']}"
        for i, step in enumerate(preset.chain)
    ]

    tradeoffs = [
        f"{step['stage']}: {step['tradeoff']}"
        for step in preset.chain
        if step.get("tradeoff")
    ]

    # Alternatives
    alternatives: List[str] = []
    for alt_name, alt_data in PRESETS.items():
        if alt_name == preset_name:
            continue
        alt_min = alt_data["lufs_target_min"]
        alt_max = alt_data["lufs_target_max"]
        # Suggest louder alternatives if source is already loud
        if lufs > -10 and alt_min >= preset.lufs_target_min:
            alternatives.append(f"{alt_name} ({alt_data['display_name']})")
        # Suggest quieter/dynamic alternatives if source is very dynamic
        elif lufs < -16 and alt_max <= -11:
            alternatives.append(f"{alt_name} ({alt_data['display_name']})")

    return {
        "preset": preset_name,
        "display_name": preset.display_name,
        "target_lufs": f"{preset.lufs_target_min} to {preset.lufs_target_max} LUFS",
        "true_peak_ceiling": f"{preset.true_peak_ceiling} dBTP",
        "why": " ".join(why_parts),
        "chain_explanation": chain_explanation,
        "tradeoffs": tradeoffs,
        "alternatives": alternatives[:3],
        "use_case": preset.use_case,
    }
