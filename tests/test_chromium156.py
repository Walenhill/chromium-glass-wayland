"""Reviewed Chromium 156 recipe contracts, using pinned official Arch input."""
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import update_upstream as upstream


class Chromium156Tests(unittest.TestCase):
    def fixture(self):
        return (Path(__file__).parent / "fixtures/arch-156.PKGBUILD").read_text()

    def test_reviewed_156_recipe_is_valid_and_uses_bundled_tools(self):
        try:
            result = upstream.render(self.fixture(), "8ec86828d5fad19ff66ec7fcaebfe223c9252838",
                                     "156.0.8078.73", "a" * 64, "b" * 64)
        except ValueError as error:
            self.fail("Reviewed Chromium 156 recipe was rejected: " + str(error))
        subprocess.run(["bash", "-n"], input=result, text=True, check=True)
        inspect = result + '\nprintf "%s|%s|%s|%s" "$pkgname" "$pkgver" "$_system_clang" "$_manual_clone"\n'
        values = subprocess.check_output(["bash"], input=inspect, text=True)
        self.assertEqual(values, "chromium-glass|156.0.8078.73|0|0")

    def test_unreviewed_future_milestone_still_fails_closed(self):
        with self.assertRaises(ValueError):
            upstream.render(self.fixture(), "8ec86828d5fad19ff66ec7fcaebfe223c9252838",
                            "157.0.1.2", "a" * 64, "b" * 64)

    def test_full_source_preparation_is_rejected_outside_github(self):
        self.assertTrue(hasattr(upstream, "require_ci"), "Missing remote-only preparation guard")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                upstream.require_ci()

    def test_menu_constructor_hunk_preserves_both_upstream_layer_names(self):
        import re
        import tempfile
        patch_text = (Path(__file__).resolve().parents[1] / "chromium-glass-wayland.patch").read_text()
        section = patch_text.split("--- a/ui/views/controls/menu/menu_scroll_view_container.cc\n", 1)[1]
        hunk = next(m.group(0) for m in re.finditer(r"(?ms)^@@.*?(?=^@@|\Z)", section)
                    if "AddChildView(std::make_unique<View>())" in m.group(0))
        for name in ("MenuScrollViewContainer/background", "MenuScrollViewContainer:Background"):
            with self.subTest(layer=name), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "menu.cc"
                source.write_text("// padding\n" * 246 +
                    "                                    ->use_ash_system_ui_layout()) {\n"
                    "  SetUseDefaultFillLayout(true);\n"
                    "  background_view_ = AddChildView(std::make_unique<View>());\n"
                    "  if (use_ash_system_ui_layout_) {\n"
                    "    // Enable background blur for ChromeOS system context menu.\n"
                    "    background_view_->SetPaintToLayer();\n"
                    "    auto* background_layer = background_view_->layer();\n"
                    f'    background_layer->SetName("{name}");\n'
                    "    if (ShouldApplyBackgroundBlur()) {}\n  }\n}\n")
                result = subprocess.run(["patch", "--batch", "--fuzz=0", "-p1"],
                    input="--- a/menu.cc\n+++ b/menu.cc\n" + hunk, cwd=directory,
                    text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("::features::IsGlassFrameEnabled()", source.read_text())
                self.assertIn(f'SetName("{name}")', source.read_text())

    def test_source_fetch_uses_official_mirror_after_gitiles_timeout(self):
        import io
        import tempfile
        import urllib.error
        import check_compatibility as compatibility
        def download(url, timeout=0):
            url = getattr(url, "full_url", url)
            if url.startswith("https://chromium.googlesource.com/"):
                raise urllib.error.HTTPError(url, 504, "Gateway Timeout", {}, None)
            if url == "https://raw.githubusercontent.com/chromium/chromium/156.0.8078.73/ui/views/menu.cc":
                return io.BytesIO(b"// official mirror fixture\n")
            raise AssertionError("Unexpected download origin: " + url)
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(compatibility.urllib.request, "urlopen", side_effect=download), \
                patch.object(compatibility.time, "sleep"):
            try:
                compatibility.fetch("ui/views/menu.cc", "156.0.8078.73", Path(directory))
            except Exception as error:
                self.fail("A temporary primary outage must use the official mirror: " + str(error))
            self.assertEqual((Path(directory) / "ui/views/menu.cc").read_bytes(),
                             b"// official mirror fixture\n")

    def test_packaging_overlay_produces_one_glass_startup_class(self):
        import tempfile
        recipe = upstream.render(self.fixture(), "8ec86828d5fad19ff66ec7fcaebfe223c9252838",
                                 "156.0.8078.73", "a" * 64, "b" * 64)
        marker = 'install -Dvm644 /dev/stdin "$pkgdir/etc/chromium-flags.conf"'
        overlay = recipe.split(marker, 1)[1].split("\nEOF\n", 1)[1]
        overlay = overlay.split("\n\n  # Fill in common", 1)[0]
        for current in ("StartupWMClass=chromium\n", "", "StartupWMClass=chromium\nStartupWMClass=old\n"):
            with self.subTest(current=current), tempfile.TemporaryDirectory() as directory:
                desktop = Path(directory) / "usr/share/applications/chromium.desktop"
                desktop.parent.mkdir(parents=True)
                desktop.write_text("[Desktop Entry]\nName=Chromium\nStartupNotify=true\n" + current)
                subprocess.run(["bash", "-e", "-c", overlay],
                               env={**os.environ, "pkgdir": directory}, check=True)
                classes = [line for line in desktop.read_text().splitlines() if line.startswith("StartupWMClass=")]
                self.assertEqual(classes, ["StartupWMClass=chromium-glass"])


if __name__ == "__main__":
    unittest.main()
