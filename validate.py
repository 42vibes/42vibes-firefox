#!/usr/bin/env python3
"""Validate the 42vibes Firefox themes.

Checks, independently of build.py:

1. repository layout (two themes, no Chromium artifacts)
2. palette structure in vendor/palette.json
3. both manifests: valid JSON, manifest_version 2, metadata, required theme
   keys, hex syntax, hex values matching the expected palette roles,
   color_scheme, dark/light separation
4. icons: file exists, PNG signature, IHDR dimensions match the icon slot size
5. README.md / README.de.md: language switcher, identical section structure,
   installation/publishing/limits notes, exactly one deliberate
   Chromium/Chrome exclusion sentence
6. determinism: two consecutive build.py runs are byte-identical

Exit code 0 means everything passed.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
THEME_ROOT = ROOT / "firefox"
PALETTE_PATH = ROOT / "vendor" / "palette.json"
MODES = ("dark", "light")
ICON_SIZES = (48, 96, 128)
HEX_RE = re.compile(r"^#[0-9a-f]{6}$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

REQUIRED_COLORS = (
    "frame",
    "frame_inactive",
    "tab_background_text",
    "tab_text",
    "tab_selected",
    "tab_line",
    "toolbar",
    "toolbar_text",
    "toolbar_field",
    "toolbar_field_text",
    "toolbar_field_border",
    "toolbar_field_focus",
    "toolbar_top_separator",
    "toolbar_bottom_separator",
    "popup",
    "popup_text",
    "popup_border",
    "popup_highlight",
    "popup_highlight_text",
    "sidebar",
    "sidebar_text",
    "sidebar_border",
    "button_background_hover",
    "icons",
    "ntp_background",
    "ntp_text",
)

# Expected palette role per theme color, resolved against vendor/palette.json.
EXPECTED = {
    "frame": "semantic.bg",
    "frame_inactive": "semantic.bg_deep",
    "tab_background_text": "semantic.text_muted",
    "tab_text": "semantic.text",
    "tab_selected": "semantic.surface_high",
    "tab_line": "semantic.accent",
    "toolbar": "semantic.surface",
    "toolbar_text": "semantic.text",
    "toolbar_field": "semantic.surface",
    "toolbar_field_text": "semantic.text",
    "toolbar_field_border": "semantic.border",
    "toolbar_field_focus": "semantic.surface_high",
    "toolbar_top_separator": "semantic.bg_deep",
    "toolbar_bottom_separator": "semantic.bg_deep",
    "popup": "semantic.surface",
    "popup_text": "semantic.text",
    "popup_border": "semantic.border",
    "popup_highlight": "semantic.surface_high",
    "popup_highlight_text": "semantic.text",
    "sidebar": "semantic.surface",
    "sidebar_text": "semantic.text_muted",
    "sidebar_border": "semantic.border",
    "button_background_hover": "semantic.surface_high",
    "icons": "semantic.text_muted",
    "ntp_background": "semantic.bg",
    "ntp_text": "semantic.text",
}

NAMES = {"dark": "42vibes Dark", "light": "42vibes Light"}

README_RULES = {
    "README.md": {
        "switcher": "](README.de.md)",
        "phrases": (
            "about:debugging",
            "Load Temporary Add-on",
            "addons.mozilla.org",
            "AMO",
            "userChrome.css",
            "build.py",
            "Generated",
        ),
        "exclusion": "Chromium/Chrome is deliberately not covered.",
    },
    "README.de.md": {
        "switcher": "](README.md)",
        "phrases": (
            "about:debugging",
            "Temporäres Add-on laden",
            "addons.mozilla.org",
            "AMO",
            "userChrome.css",
            "build.py",
            "Generiert",
        ),
        "exclusion": "Chromium/Chrome wird bewusst nicht abgedeckt.",
    },
}

FORBIDDEN_DOC_PHRASES = (
    "chrome web store",
    "chromium.org",
    "manifest_version 3",
)


class Report:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.passes = 0

    def check(self, condition: bool, message: str) -> bool:
        if condition:
            self.passes += 1
        else:
            self.failures.append(message)
        return condition

    def fail(self, message: str) -> None:
        self.failures.append(message)


def load_palette(report: Report) -> dict:
    if not report.check(PALETTE_PATH.is_file(), "vendor/palette.json is missing"):
        return {}
    try:
        palette = json.loads(PALETTE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        report.fail(f"vendor/palette.json is not valid JSON: {exc}")
        return {}

    for mode in MODES:
        section = palette.get(mode)
        if not report.check(isinstance(section, dict), f"palette: missing mode '{mode}'"):
            continue
        for group in ("semantic", "ansi"):
            values = section.get(group)
            if not report.check(
                isinstance(values, dict) and values,
                f"palette: missing group {mode}.{group}",
            ):
                continue
            for name, value in values.items():
                report.check(
                    isinstance(value, str) and bool(HEX_RE.match(value)),
                    f"palette: {mode}.{group}.{name} is not a lowercase #rrggbb value: {value!r}",
                )
    return palette


def resolve(palette: dict, mode: str, path: str) -> str | None:
    group, name = path.split(".", 1)
    try:
        return palette[mode][group][name]
    except (KeyError, TypeError):
        return None


def png_info(data: bytes) -> tuple[int, int, int, int] | None:
    """Return (width, height, bit_depth, color_type) from a PNG, or None."""
    if len(data) < 33 or data[:8] != PNG_SIGNATURE or data[12:16] != b"IHDR":
        return None
    width, height = struct.unpack(">II", data[16:24])
    bit_depth = data[24]
    color_type = data[25]
    return width, height, bit_depth, color_type


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast(first: str, second: str) -> float:
    a, b = relative_luminance(first), relative_luminance(second)
    lighter, darker = max(a, b), min(a, b)
    return (lighter + 0.05) / (darker + 0.05)


def check_layout(report: Report) -> None:
    for relative in (
        "build.py",
        "validate.py",
        "Makefile",
        "LICENSE",
        "README.md",
        "README.de.md",
        "vendor/palette.json",
    ):
        report.check((ROOT / relative).is_file(), f"missing repository file: {relative}")

    for forbidden in ("chromium", "chrome", "dist/chromium"):
        report.check(
            not (ROOT / forbidden).exists(),
            f"Chromium artifact present: {forbidden}/",
        )


def check_manifests(report: Report, palette: dict) -> dict[str, dict]:
    manifests: dict[str, dict] = {}

    for mode in MODES:
        theme_dir = THEME_ROOT / f"42vibes-{mode}"
        manifest_path = theme_dir / "manifest.json"
        label = f"firefox/42vibes-{mode}/manifest.json"

        if not report.check(manifest_path.is_file(), f"{label}: missing"):
            continue
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.fail(f"{label}: invalid JSON ({exc})")
            continue
        manifests[mode] = data

        report.check(data.get("manifest_version") == 2, f"{label}: manifest_version must be 2")
        report.check(data.get("name") == NAMES[mode], f"{label}: name must be '{NAMES[mode]}'")
        version = data.get("version")
        report.check(
            isinstance(version, str) and bool(VERSION_RE.match(version)),
            f"{label}: version is missing or not x.y.z ({version!r})",
        )
        description = data.get("description")
        report.check(
            isinstance(description, str) and len(description.strip()) >= 20,
            f"{label}: description is missing or too short",
        )

        theme = data.get("theme")
        if not report.check(isinstance(theme, dict), f"{label}: theme object missing"):
            continue
        properties = theme.get("properties")
        report.check(
            isinstance(properties, dict) and properties.get("color_scheme") == mode,
            f"{label}: theme.properties.color_scheme must be '{mode}'",
        )

        colors = theme.get("colors")
        if not report.check(isinstance(colors, dict), f"{label}: theme.colors missing"):
            continue
        report.check(
            set(colors) == set(REQUIRED_COLORS),
            f"{label}: theme.colors keys mismatch; missing={sorted(set(REQUIRED_COLORS) - set(colors))} "
            f"unexpected={sorted(set(colors) - set(REQUIRED_COLORS))}",
        )

        for role in REQUIRED_COLORS:
            value = colors.get(role)
            if not report.check(
                isinstance(value, str) and bool(HEX_RE.match(value)),
                f"{label}: {role} is not a lowercase #rrggbb value ({value!r})",
            ):
                continue
            expected_path = EXPECTED[role]
            expected = resolve(palette, mode, expected_path)
            report.check(
                value == expected,
                f"{label}: {role}={value} should be {expected_path}={expected}",
            )

        # Readability of the main toolbar text roles.
        if all(isinstance(colors.get(role), str) for role in ("toolbar", "toolbar_text", "tab_background_text")):
            ratio = contrast(colors["toolbar_text"], colors["toolbar"])
            report.check(
                ratio >= 7.0,
                f"{label}: toolbar_text on toolbar contrast {ratio:.1f}:1 is below 7:1",
            )
            ratio = contrast(colors["tab_background_text"], colors["toolbar"])
            report.check(
                ratio >= 4.5,
                f"{label}: tab_background_text on toolbar contrast {ratio:.1f}:1 is below 4.5:1",
            )

        icons = data.get("icons")
        if report.check(isinstance(icons, dict), f"{label}: icons object missing"):
            report.check(
                set(icons) == {str(size) for size in ICON_SIZES},
                f"{label}: icon sizes must be {list(ICON_SIZES)}, got {sorted(icons)}",
            )
            for size in ICON_SIZES:
                relative = icons.get(str(size))
                if not report.check(
                    isinstance(relative, str),
                    f"{label}: icons[{size}] missing",
                ):
                    continue
                icon_path = theme_dir / relative
                if not report.check(icon_path.is_file(), f"{label}: icon file missing: {relative}"):
                    continue
                raw = icon_path.read_bytes()
                info = png_info(raw)
                if not report.check(info is not None, f"{label}: {relative} is not a PNG"):
                    continue
                width, height, depth, color_type = info  # type: ignore[misc]
                report.check(
                    (width, height) == (size, size),
                    f"{label}: {relative} is {width}x{height}, expected {size}x{size}",
                )
                report.check(
                    depth == 8 and color_type in (2, 3, 6),
                    f"{label}: {relative} has unexpected PNG depth/color type "
                    f"({depth}/{color_type})",
                )

    # Dark and light must actually differ.
    if set(manifests) == set(MODES):
        dark = manifests["dark"]["theme"]["colors"]
        light = manifests["light"]["theme"]["colors"]
        differing = [role for role in REQUIRED_COLORS if dark.get(role) != light.get(role)]
        report.check(
            len(differing) == len(REQUIRED_COLORS),
            f"dark and light share identical colors for: "
            f"{sorted(set(REQUIRED_COLORS) - set(differing))}",
        )
        for role in ("frame", "toolbar", "tab_text", "ntp_background"):
            report.check(
                dark.get(role) != light.get(role),
                f"dark/light {role} are identical ({dark.get(role)})",
            )
        report.check(
            manifests["dark"].get("description") != manifests["light"].get("description"),
            "dark and light manifests share the same description",
        )

        icon_hashes = {}
        for mode in MODES:
            for size in ICON_SIZES:
                icon = THEME_ROOT / f"42vibes-{mode}" / "icons" / f"icon-{size}.png"
                if icon.is_file():
                    icon_hashes[(mode, size)] = hashlib.sha256(icon.read_bytes()).hexdigest()
        for size in ICON_SIZES:
            dark_hash = icon_hashes.get(("dark", size))
            light_hash = icon_hashes.get(("light", size))
            report.check(
                dark_hash is not None and dark_hash != light_hash,
                f"icons/icon-{size}.png is identical for dark and light",
            )

    return manifests


def check_readmes(report: Report) -> None:
    headings: dict[str, list[str]] = {}

    for filename, rules in README_RULES.items():
        path = ROOT / filename
        if not report.check(path.is_file(), f"{filename}: missing"):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()

        report.check(
            bool(lines) and lines[0].startswith("# "),
            f"{filename}: must start with a level-1 heading",
        )
        switcher = next((line for line in lines[1:4] if line.strip()), "")
        report.check(
            rules["switcher"] in switcher,
            f"{filename}: language switcher must sit directly below the H1 "
            f"(expected link target {rules['switcher']})",
        )

        headings[filename] = [
            match.group(1) for match in re.finditer(r"^(#{1,6})\s", text, re.MULTILINE)
        ]

        lowered = text.lower()
        for phrase in rules["phrases"]:
            report.check(
                phrase.lower() in lowered,
                f"{filename}: required content missing: {phrase!r}",
            )
        report.check(
            "Load unpacked" not in text and "chrome://extensions" not in text,
            f"{filename}: contains Chromium installation instructions",
        )

        # Exactly one mention of Chrome: the deliberate exclusion sentence.
        # `userChrome.css` is a file name required elsewhere in the docs, so it
        # is removed before counting.
        report.check(
            rules["exclusion"] in text,
            f"{filename}: exclusion sentence missing: {rules['exclusion']!r}",
        )
        mentions = len(re.findall("chrome", lowered.replace("userchrome.css", "")))
        report.check(
            mentions == 1,
            f"{filename}: expected exactly one Chromium/Chrome mention "
            f"(the exclusion sentence), found {mentions}",
        )
        for phrase in FORBIDDEN_DOC_PHRASES:
            report.check(
                phrase not in lowered,
                f"{filename}: contains forbidden phrase {phrase!r}",
            )
        report.check(
            "no commit" not in lowered and "kein commit" not in lowered,
            f"{filename}: should not document commit instructions",
        )

    if len(headings) == 2:
        en, de = headings["README.md"], headings["README.de.md"]
        report.check(
            len(en) >= 7,
            f"README.md: expected at least 7 headings, found {len(en)}",
        )
        report.check(
            en == de,
            f"READMEs must use the same section structure; EN={en} DE={de}",
        )


def generated_files() -> list[Path]:
    files: list[Path] = []
    for mode in MODES:
        theme_dir = THEME_ROOT / f"42vibes-{mode}"
        files.append(theme_dir / "manifest.json")
        files.extend(theme_dir / "icons" / f"icon-{size}.png" for size in ICON_SIZES)
    return files


def snapshot() -> dict[str, str]:
    result = {}
    for path in generated_files():
        if path.is_file():
            result[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def check_determinism(report: Report, runs: int = 2) -> None:
    before = snapshot()
    if not report.check(bool(before), "determinism: no generated files to compare"):
        return

    for run in range(1, runs + 1):
        result = subprocess.run(
            [sys.executable, str(ROOT / "build.py")],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if not report.check(
            result.returncode == 0,
            f"determinism: build.py run {run} failed with exit {result.returncode}: "
            f"{result.stderr.strip()}",
        ):
            return
        after = snapshot()
        changed = sorted(
            path for path in set(before) | set(after) if before.get(path) != after.get(path)
        )
        report.check(
            not changed,
            f"determinism: build.py run {run} changed bytes in: {changed}",
        )
        before = after


def main() -> int:
    report = Report()

    check_layout(report)
    palette = load_palette(report)
    if palette:
        check_manifests(report, palette)
    check_readmes(report)
    check_determinism(report)

    for failure in report.failures:
        print(f"FAIL {failure}")
    print(f"\nvalidate: {report.passes} checks passed, {len(report.failures)} failed")
    return 0 if not report.failures else 1


if __name__ == "__main__":
    sys.exit(main())
