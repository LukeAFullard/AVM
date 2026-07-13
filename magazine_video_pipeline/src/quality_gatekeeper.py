import json
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

@dataclass
class GateViolation:
    gate_name: str
    scene_ref_id: str
    violation_type: str
    current_value: float
    target_range: str
    reprompt_instruction: str

class QualityGateException(Exception):
    def __init__(self, violations: List[GateViolation]):
        self.violations = violations
        super().__init__(f"Failed {len(violations)} quality gates.")

class VideoQualityGatekeeper:
    def __init__(self, min_wpm: float = 135.0, max_wpm: float = 185.0, min_crop_area_pct: float = 12.0):
        self.min_wpm = min_wpm
        self.max_wpm = max_wpm
        self.min_crop_area_pct = min_crop_area_pct

    def validate_project(self, storyboard: Dict[str, Any], render_manifest: Dict[str, Any], whisper_timestamps: Dict[str, List[Dict[str, Any]]]) -> bool:
        violations: List[GateViolation] = []
        all_units = storyboard.get("hooks", []) + storyboard.get("body_scenes", [])

        for unit in all_units:
            ref_id = unit.get("hook_id") or unit.get("scene_id")
            timestamps = whisper_timestamps.get(ref_id, [])

            wpm_viol = self._check_reading_speed(ref_id, unit["spoken_narration"], timestamps)
            if wpm_viol: violations.append(wpm_viol)

            overflow_viol = self._check_caption_overflow(ref_id, timestamps)
            if overflow_viol: violations.append(overflow_viol)

        for scene_manifest in render_manifest.get("scene_manifests", []):
            ref_id = scene_manifest["scene_ref_id"]
            visual_source = scene_manifest.get("visual_source", {})
            if visual_source.get("source_type") == "magazine_scan":
                bbox = visual_source.get("crop_bbox_pct", [0, 0, 100, 100])
                crop_viol = self._check_crop_boundaries(ref_id, bbox)
                if crop_viol: violations.append(crop_viol)

        if violations:
            raise QualityGateException(violations)
        return True

    def _check_reading_speed(self, ref_id: str, text: str, timestamps: List[Dict[str, Any]]) -> Optional[GateViolation]:
        if not timestamps or len(timestamps) < 2: return None
        word_count = len(text.split())
        duration_sec = timestamps[-1]["end"] - timestamps[0]["start"]
        if duration_sec <= 0: return None
        actual_wpm = (word_count / duration_sec) * 60.0

        if actual_wpm < self.min_wpm:
            return GateViolation("ReadingSpeedWPM", ref_id, "PACING_TOO_SLOW", round(actual_wpm, 1), f"{self.min_wpm}-{self.max_wpm} WPM", f"Narration for '{ref_id}' is too slow ({round(actual_wpm,1)} WPM). Rewrite to be more punchy.")
        elif actual_wpm > self.max_wpm:
            return GateViolation("ReadingSpeedWPM", ref_id, "PACING_TOO_FAST", round(actual_wpm, 1), f"{self.min_wpm}-{self.max_wpm} WPM", f"Narration for '{ref_id}' is too fast ({round(actual_wpm,1)} WPM). Shorten word count by ~20%.")
        return None

    def _check_caption_overflow(self, ref_id: str, timestamps: List[Dict[str, Any]]) -> Optional[GateViolation]:
        for item in timestamps:
            word = item.get("word", "").strip()
            if len(word) > 14:
                return GateViolation("CaptionOverflow", ref_id, "WORD_LENGTH_OVERFLOW", len(word), "Max 14 chars per word", f"The word '{word}' in '{ref_id}' will visually clip. Replace with a shorter synonym.")
            duration = item["end"] - item["start"]
            if duration < 0.08 and len(word) > 4:
                return GateViolation("CaptionOverflow", ref_id, "CAPTION_FLICKER_RISK", round(duration*1000, 1), "Min 80ms display duration", f"The phrase containing '{word}' in '{ref_id}' is spoken too rapidly. Remove filler words.")
        return None

    def _check_crop_boundaries(self, ref_id: str, bbox: List[float]) -> Optional[GateViolation]:
        if len(bbox) != 4:
            return GateViolation("CropBoundaries", ref_id, "INVALID_BBOX_FORMAT", len(bbox), "[xmin, ymin, xmax, ymax]", f"Crop bounding box for '{ref_id}' must contain exactly 4 numerical percentage values.")
        xmin, ymin, xmax, ymax = bbox
        if not (0 <= xmin < xmax <= 100) or not (0 <= ymin < ymax <= 100):
            return GateViolation("CropBoundaries", ref_id, "OUT_OF_BOUNDS_OR_INVERTED", 0.0, "0 <= min < max <= 100", f"Bounding box [{xmin}, {ymin}, {xmax}, {ymax}] for '{ref_id}' is geometrically invalid.")
        area_pct = ((xmax - xmin) * (ymax - ymin)) / 100.0
        if area_pct < self.min_crop_area_pct:
            return GateViolation("CropBoundaries", ref_id, "EXTREME_ZOOM_PIXELATION", round(area_pct, 2), f">= {self.min_crop_area_pct}% area", f"Crop area for '{ref_id}' is only {round(area_pct,1)}%. Expand box to prevent pixelation.")
        return None