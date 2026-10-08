#!/usr/bin/env python3
"""Check Glass hunks against official Chromium source without a full checkout."""
import argparse
import base64
import concurrent.futures
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def validate_patch(text):
    """Reject malformed hunk counts instead of silently losing later hunks."""
    lines = text.splitlines()
    index = 0
    hunks = 0
    while index < len(lines):
        if lines[index].startswith("--- a/"):
            if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ b/"):
                raise ValueError("Missing new-file header")
            index += 2
            continue
        match = re.match(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", lines[index])
        if not match:
            raise ValueError(f"Unexpected patch content at line {index + 1}: {lines[index]!r}")
        old = int(match[2] or 1)
        new = int(match[4] or 1)
        index += 1
        while old or new:
            if index >= len(lines) or not lines[index] or lines[index][0] not in " +-":
                raise ValueError(f"Truncated hunk near line {index + 1}")
            prefix = lines[index][0]
            old -= prefix in " -"
            new -= prefix in " +"
            if old < 0 or new < 0:
                raise ValueError(f"Invalid hunk counts near line {index + 1}")
            index += 1
        hunks += 1
    return hunks


def check_contracts(destination):
    contracts = {
        "chrome/browser/ui/views/omnibox/omnibox_popup_view_views.cc":
            ["params.type = views::Widget::InitParams::TYPE_MENU;",
             "params.native_widget = new views::DesktopNativeWidgetAura(this);"],
        "ui/base/ui_base_features.cc": ["#elif BUILDFLAG(IS_LINUX)"],
        "ui/views/controls/menu/menu_scroll_view_container.cc":
            ["use_ash_system_ui_layout_ || ::features::IsGlassFrameEnabled()",
             "shadow_type = BubbleBorder::NO_SHADOW;"],
        "chrome/browser/ui/views/location_bar/location_bar_view.cc":
            ["omnibox_view_->SetBackgroundColor(features::IsGlassFrameEnabled()"],
    }
    for path, snippets in contracts.items():
        content = (destination / path).read_text()
        for snippet in snippets:
            if snippet not in content:
                raise ValueError(f"Required Glass integration missing in {path}: {snippet}")


def fetch(path, version, destination):
    url = f"https://chromium.googlesource.com/chromium/src/+/{version}/{path}?format=TEXT"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=45) as response:
                data = base64.b64decode(response.read(), validate=True)
            target = destination / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            return
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--patch", type=Path, default=ROOT / "chromium-glass-wayland.patch")
    parser.add_argument("--source-dir", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", args.version):
        parser.error("Expected a numeric Chromium version")
    patch_text = args.patch.read_text()
    hunks = validate_patch(patch_text)
    paths = sorted(set(re.findall(r"^--- a/(.+)$", patch_text, re.M)))
    if not paths or any(Path(p).is_absolute() or ".." in Path(p).parts for p in paths):
        parser.error("Patch has missing or unsafe source paths")
    with tempfile.TemporaryDirectory(prefix="glass-compat-") as temporary:
        destination = args.source_dir or Path(temporary)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            list(executor.map(lambda p: fetch(p, args.version, destination), paths))
        result = subprocess.run(
            ["patch", "--dry-run", "--batch", "--fuzz=0", "-p1", "-i", str(args.patch.resolve())],
            cwd=destination, text=True, capture_output=True,
        )
        contracts_verified = False
        if result.returncode == 0:
            subprocess.run(["patch", "--batch", "--fuzz=0", "-p1", "-i", str(args.patch.resolve())],
                           cwd=destination, check=True, capture_output=True)
            check_contracts(destination)
            contracts_verified = True
        report = {"version": args.version, "files": paths,
                  "hunks": hunks, "integration_contracts_verified": contracts_verified,
                  "patch_applies": result.returncode == 0,
                  "scope": "source hunks only; build and Wayland blur not verified",
                  "output": result.stdout + result.stderr}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
