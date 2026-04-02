"""
artwork.py — Artwork validation and extraction.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ArtworkRequirements:
    min_size: int = 3000
    recommended_size: int = 3000
    formats: List[str] = field(default_factory=lambda: ["JPEG", "PNG"])


_REQUIREMENTS = ArtworkRequirements()


@dataclass
class ArtworkInfo:
    path: str
    width: int
    height: int
    format: str
    file_size_kb: float
    is_square: bool
    meets_minimum_size: bool
    color_mode: str
    warnings: List[str] = field(default_factory=list)


def check_artwork(image_path: str) -> ArtworkInfo:
    """
    Validate an artwork image file and return an ArtworkInfo with any warnings.
    """
    warnings: List[str] = []

    try:
        from PIL import Image  # noqa: PLC0415
    except ImportError:
        return ArtworkInfo(
            path=image_path,
            width=0,
            height=0,
            format="UNKNOWN",
            file_size_kb=0.0,
            is_square=False,
            meets_minimum_size=False,
            color_mode="UNKNOWN",
            warnings=["Pillow not installed — artwork validation skipped."],
        )

    try:
        with Image.open(image_path) as img:
            width, height = img.size
            fmt = img.format or "UNKNOWN"
            mode = img.mode
    except Exception as exc:
        return ArtworkInfo(
            path=image_path,
            width=0,
            height=0,
            format="UNKNOWN",
            file_size_kb=0.0,
            is_square=False,
            meets_minimum_size=False,
            color_mode="UNKNOWN",
            warnings=[f"Could not open image: {exc}"],
        )

    size_kb = round(Path(image_path).stat().st_size / 1024, 1)
    is_square = width == height
    meets_min = width >= _REQUIREMENTS.min_size and height >= _REQUIREMENTS.min_size

    if not is_square:
        warnings.append(
            f"Artwork is not square ({width}×{height}). "
            "All major distributors require a 1:1 square image."
        )

    if not meets_min:
        warnings.append(
            f"Artwork is smaller than the recommended minimum "
            f"({width}×{height} < {_REQUIREMENTS.min_size}×{_REQUIREMENTS.min_size}). "
            "Most distributors require at least 3000×3000 px."
        )
    elif width < 3000 or height < 3000:
        warnings.append(
            f"Artwork is {width}×{height}. "
            f"Recommended size is {_REQUIREMENTS.recommended_size}×{_REQUIREMENTS.recommended_size} px."
        )

    if fmt.upper() not in [f.upper() for f in _REQUIREMENTS.formats]:
        warnings.append(
            f"Artwork format '{fmt}' may not be accepted by all distributors. "
            f"Preferred formats: {', '.join(_REQUIREMENTS.formats)}."
        )

    if mode not in ("RGB", "L"):
        warnings.append(
            f"Artwork color mode is '{mode}'. "
            "RGB is required for most distributors (not RGBA, CMYK, etc.)."
        )

    if size_kb > 20_000:
        warnings.append(
            f"Artwork file is very large ({size_kb:.0f} KB). "
            "Consider optimising to reduce upload times."
        )

    return ArtworkInfo(
        path=image_path,
        width=width,
        height=height,
        format=fmt,
        file_size_kb=size_kb,
        is_square=is_square,
        meets_minimum_size=meets_min,
        color_mode=mode,
        warnings=warnings,
    )


def extract_artwork_from_audio(audio_path: str, output_dir: str) -> Optional[str]:
    """
    Attempt to extract embedded artwork from *audio_path* and save it to
    *output_dir*. Returns the output file path or None if extraction failed.
    """
    try:
        import mutagen  # noqa: PLC0415

        tag = mutagen.File(audio_path)
        if tag is None:
            return None

        image_data: Optional[bytes] = None
        image_ext = ".jpg"

        # ID3 (MP3)
        if hasattr(tag, "tags") and tag.tags:
            for key in list(tag.tags.keys()):
                if "APIC" in str(key):
                    frame = tag.tags[key]
                    image_data = frame.data
                    mime = getattr(frame, "mime", "image/jpeg")
                    image_ext = ".png" if "png" in mime.lower() else ".jpg"
                    break

        # FLAC
        if image_data is None and hasattr(tag, "pictures") and tag.pictures:
            pic = tag.pictures[0]
            image_data = pic.data
            image_ext = ".png" if "png" in pic.mime.lower() else ".jpg"

        # MP4 / M4A
        if image_data is None and hasattr(tag, "get"):
            try:
                covr = tag.get("covr")
                if covr:
                    image_data = bytes(covr[0])
            except Exception:
                pass

        if image_data is None:
            return None

        stem = Path(audio_path).stem
        output_path = str(Path(output_dir) / f"{stem}_artwork{image_ext}")
        os.makedirs(output_dir, exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(image_data)
        return output_path

    except Exception:
        return None
