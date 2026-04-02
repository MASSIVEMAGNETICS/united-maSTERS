"""
test_mastering.py — Tests for the mastering presets module.
"""

import pytest

from united_masters.core.analyze import AudioAnalysis
from united_masters.core.mastering import (
    PRESETS,
    MasteringPreset,
    get_preset,
    get_recommendation_explanation,
)

ALL_PRESET_NAMES = [
    "streaming_safe",
    "loud_modern_rap",
    "warm_hip_hop",
    "vocal_forward",
    "trap_808_heavy",
    "clean_dynamic",
]


class TestPresetsDict:
    def test_all_six_presets_defined(self):
        for name in ALL_PRESET_NAMES:
            assert name in PRESETS

    def test_each_preset_has_required_keys(self):
        required = {"display_name", "lufs_target_min", "lufs_target_max", "true_peak_ceiling",
                    "description", "use_case", "chain"}
        for name, data in PRESETS.items():
            missing = required - set(data.keys())
            assert not missing, f"Preset '{name}' missing keys: {missing}"

    def test_chain_stages_have_stage_and_action(self):
        for name, data in PRESETS.items():
            for stage in data["chain"]:
                assert "stage" in stage, f"Preset '{name}' chain item missing 'stage'"
                assert "action" in stage, f"Preset '{name}' chain item missing 'action'"

    def test_lufs_targets_are_sensible(self):
        for name, data in PRESETS.items():
            assert data["lufs_target_min"] < data["lufs_target_max"], \
                f"Preset '{name}': min LUFS must be < max LUFS"
            assert -20 <= data["lufs_target_min"] <= -6, \
                f"Preset '{name}': min LUFS out of expected range"

    def test_true_peak_ceiling_is_negative(self):
        for name, data in PRESETS.items():
            assert data["true_peak_ceiling"] < 0, \
                f"Preset '{name}': true_peak_ceiling should be negative dBTP"


class TestGetPreset:
    def test_returns_mastering_preset_instance(self):
        preset = get_preset("streaming_safe")
        assert isinstance(preset, MasteringPreset)

    def test_all_presets_retrievable(self):
        for name in ALL_PRESET_NAMES:
            preset = get_preset(name)
            assert preset.name == name

    def test_unknown_preset_raises_key_error(self):
        with pytest.raises(KeyError, match="Unknown preset"):
            get_preset("nonexistent_preset")

    def test_lufs_midpoint_calculation(self):
        preset = get_preset("streaming_safe")
        expected = (preset.lufs_target_min + preset.lufs_target_max) / 2
        assert preset.lufs_target_midpoint == expected

    def test_chain_populated(self):
        for name in ALL_PRESET_NAMES:
            preset = get_preset(name)
            assert len(preset.chain) >= 3, f"Preset '{name}' should have at least 3 chain stages"

    def test_streaming_safe_display_name(self):
        p = get_preset("streaming_safe")
        assert p.display_name == "Streaming Safe"

    def test_loud_modern_rap_is_louder_than_clean_dynamic(self):
        loud = get_preset("loud_modern_rap")
        clean = get_preset("clean_dynamic")
        assert loud.lufs_target_max > clean.lufs_target_max


class TestMasteringPresetDataclass:
    def test_name_field(self):
        p = get_preset("warm_hip_hop")
        assert p.name == "warm_hip_hop"

    def test_description_is_string(self):
        p = get_preset("vocal_forward")
        assert isinstance(p.description, str)
        assert len(p.description) > 10

    def test_use_case_is_string(self):
        p = get_preset("trap_808_heavy")
        assert isinstance(p.use_case, str)


class TestGetRecommendationExplanation:
    def _make_analysis(self, lufs=-12.0, crest=10.0, bpm=100.0, clipped=False) -> AudioAnalysis:
        a = AudioAnalysis()
        a.integrated_lufs = lufs
        a.crest_factor_db = crest
        a.estimated_bpm = bpm
        a.is_clipped = clipped
        return a

    def test_returns_dict_with_expected_keys(self):
        analysis = self._make_analysis()
        result = get_recommendation_explanation("streaming_safe", analysis)
        expected_keys = {"preset", "display_name", "target_lufs", "true_peak_ceiling",
                         "why", "chain_explanation", "tradeoffs", "alternatives", "use_case"}
        assert expected_keys.issubset(set(result.keys()))

    def test_why_mentions_lufs(self):
        analysis = self._make_analysis(lufs=-14.5)
        result = get_recommendation_explanation("streaming_safe", analysis)
        assert "LUFS" in result["why"]

    def test_clipping_warning_in_why(self):
        analysis = self._make_analysis(clipped=True)
        result = get_recommendation_explanation("streaming_safe", analysis)
        assert "Clipping" in result["why"] or "clipping" in result["why"].lower()

    def test_chain_explanation_is_list(self):
        analysis = self._make_analysis()
        result = get_recommendation_explanation("warm_hip_hop", analysis)
        assert isinstance(result["chain_explanation"], list)
        assert len(result["chain_explanation"]) > 0

    def test_tradeoffs_is_list(self):
        analysis = self._make_analysis()
        result = get_recommendation_explanation("trap_808_heavy", analysis)
        assert isinstance(result["tradeoffs"], list)

    def test_alternatives_is_list(self):
        analysis = self._make_analysis()
        result = get_recommendation_explanation("streaming_safe", analysis)
        assert isinstance(result["alternatives"], list)

    def test_works_for_all_presets(self):
        analysis = self._make_analysis()
        for name in ALL_PRESET_NAMES:
            result = get_recommendation_explanation(name, analysis)
            assert result["preset"] == name
