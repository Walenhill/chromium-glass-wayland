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


if __name__ == "__main__":
    unittest.main()
