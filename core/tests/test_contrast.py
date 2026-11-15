"""Colour contrast the browser cannot check for us: WCAG AA needs 4.5:1 for normal text."""

import re
from pathlib import Path

from django.conf import settings

BASE_CSS = (Path(settings.BASE_DIR) / "core" / "static" / "core" / "base.css").read_text()


def _luminance(hex_color: str) -> float:
    channels = [int(hex_color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground: str, background: str) -> float:
    lighter, darker = sorted((_luminance(foreground), _luminance(background)), reverse=True)
    return (lighter + 0.05) / (darker + 0.05)


def test_contrast_helper_matches_known_values():
    assert round(contrast("#000000", "#ffffff"), 1) == 21.0
    assert round(contrast("#ffffff", "#ffffff"), 1) == 1.0


def test_danger_buttons_are_readable_in_light_and_dark():
    """UX-03: white text on the dark theme's pale red was 2.4:1 (Void, Reject, Delete)."""
    backgrounds = re.findall(r"--danger:\s*(#[0-9a-fA-F]{6})", BASE_CSS)
    inks = re.findall(r"--danger-ink:\s*(#[0-9a-fA-F]{3,6})", BASE_CSS)
    assert len(backgrounds) == len(inks) == 2, "one --danger and --danger-ink per theme"
    for background, ink in zip(backgrounds, inks, strict=True):
        ink = "#" + "".join(c * 2 for c in ink[1:]) if len(ink) == 4 else ink
        assert contrast(ink, background) >= 4.5, f"{ink} on {background}"
    assert "--btn-ink: var(--danger-ink)" in BASE_CSS
