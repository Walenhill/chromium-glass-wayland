import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import check_compatibility as compatibility
import stable_update as updater
import update_upstream as upstream


def manifest():
    version = "155.0.8059.39-1"
    return {"schema": 1, "repository": updater.REPO, "tag": "v" + version,
            "package_version": version, "package": f"chromium-glass-{version}-x86_64.pkg.tar.zst",
            "arch": "x86_64", "sha256": "a" * 64, "build_commit": "b" * 40,
            "visual_approved": True, "validation_policy": updater.POLICY}


def release():
    meta = manifest()
    names = ["stable.json", "release-attestation.json", meta["package"], "build-attestation.json"]
    return {"tag_name": meta["tag"], "draft": False, "prerelease": False,
            "assets": [{"name": name, "browser_download_url": updater.ASSET_BASE + meta["tag"] + "/" + name}
                       for name in names]}


class ManifestTests(unittest.TestCase):
    def test_approved_identity(self):
        meta = manifest()
        self.assertEqual(updater.check_manifest(meta, meta["tag"]), meta["package"])

    def test_reject_each_policy_violation(self):
        changes = {"schema": 2, "repository": "evil/repo", "package_version": "../bad",
                   "package": "../package.pkg.tar.zst", "arch": "aarch64", "sha256": "invalid",
                   "build_commit": "short", "visual_approved": "true", "validation_policy": "headless-only"}
        for key, value in changes.items():
            with self.subTest(key=key):
                meta = manifest()
                meta[key] = value
                with self.assertRaises(ValueError):
                    updater.check_manifest(meta, "v155.0.8059.39-1")

    def test_reject_tag_mismatch(self):
        with self.assertRaises(ValueError):
            updater.check_manifest(manifest(), "v155.0.8059.39-2")

    def test_asset_origin_and_duplicates(self):
        valid = release()
        self.assertTrue(updater.asset_url(valid, "stable.json").startswith(updater.ASSET_BASE))
        altered = copy.deepcopy(valid)
        altered["assets"][0]["browser_download_url"] = "https://evil.example/stable.json"
        with self.assertRaises(ValueError):
            updater.asset_url(altered, "stable.json")
        valid["assets"].append(valid["assets"][0])
        with self.assertRaises(ValueError):
            updater.asset_url(valid, "stable.json")


class UpdaterFlowTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.run_patch = patch.object(updater.subprocess, "run", side_effect=self.command)
        self.run_patch.start()
        self.euid_patch = patch.object(updater.os, "geteuid", return_value=0)
        self.euid_patch.start()
        self.output_patch = patch.object(updater.subprocess, "check_output", return_value="1\n")
        self.output_patch.start()

    def tearDown(self):
        self.run_patch.stop()
        self.euid_patch.stop()
        self.output_patch.stop()

    def command(self, args, **kwargs):
        self.calls.append(args)
        self.last_env = kwargs.get("env", {})
        return subprocess.CompletedProcess(args, 0, "chromium-glass 150.0.7871.186-11\n", "")

    def fake_fetch(self, url, target=None, limit=0):
        if target:
            target.write_text(json.dumps(manifest()) if target.name == "stable.json" else "{}")
            return b""
        return json.dumps(release()).encode()

    def assert_no_install(self):
        self.assertFalse(any(call[:2] == ["pacman", "-U"] for call in self.calls))

    def test_no_release_keeps_installed(self):
        with patch.object(updater, "fetch", side_effect=urllib.error.HTTPError("url", 404, "not found", {}, None)):
            updater.run(True)
        self.assert_no_install()

    def test_invalid_attestation_is_fail_closed(self):
        with patch.object(updater, "fetch", side_effect=self.fake_fetch), patch.object(
                updater, "verify", side_effect=ValueError("invalid signature")):
            with self.assertRaises(ValueError):
                updater.run(True)
        self.assert_no_install()

    def test_check_only_never_installs(self):
        with patch.object(updater, "fetch", side_effect=self.fake_fetch), patch.object(updater, "verify"):
            updater.run(False)
        self.assert_no_install()

    def test_running_browser_defers(self):
        with patch.object(updater, "fetch", side_effect=self.fake_fetch), patch.object(updater, "verify"), \
                patch.object(updater, "browser_running", return_value=True):
            updater.run(True)
        self.assert_no_install()

    def test_checksum_mismatch_never_installs(self):
        with patch.object(updater, "fetch", side_effect=self.fake_fetch), patch.object(updater, "verify"), \
                patch.object(updater, "browser_running", return_value=False):
            with self.assertRaises(ValueError):
                updater.run(True)
        self.assert_no_install()

    def test_browser_process_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            proc = Path(directory)
            (proc / "123").mkdir()
            (proc / "123/exe").symlink_to("/usr/lib/chromium/chromium (deleted)")
            self.assertTrue(updater.browser_running(proc))

    def test_verification_pins_identity_and_discards_user_token(self):
        with patch.dict(updater.os.environ, {"GH_TOKEN": "secret"}):
            updater.verify(Path("package"), Path("bundle.json"), "release.yml")
        command = self.calls[-1]
        self.assertIn("refs/heads/main", command)
        self.assertIn(updater.REPO + "/.github/workflows/release.yml", command)
        self.assertNotIn("GH_TOKEN", self.last_env)

    def test_bad_build_attestation_never_installs(self):
        def fetch_with_matching_hash(url, target=None, limit=0):
            result = self.fake_fetch(url, target, limit)
            if target and target.name == "stable.json":
                data = manifest()
                data["sha256"] = hashlib.sha256(b"{}").hexdigest()
                target.write_text(json.dumps(data))
            return result
        with patch.object(updater, "fetch", side_effect=fetch_with_matching_hash), \
                patch.object(updater, "verify", side_effect=[None, ValueError("wrong builder")]), \
                patch.object(updater, "browser_running", return_value=False):
            with self.assertRaises(ValueError):
                updater.run(True)
        self.assert_no_install()


class SourceTests(unittest.TestCase):
    def test_complete_patch(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(compatibility.validate_patch((root / "chromium-glass-wayland.patch").read_text()), 19)

    def test_reject_truncated_hunk(self):
        with self.assertRaises(ValueError):
            compatibility.validate_patch("--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n a\n")

    def test_reject_unprefixed_blank_line(self):
        with self.assertRaises(ValueError):
            compatibility.validate_patch("--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n a\n\n")

    def test_recipe_anchor_drift(self):
        with self.assertRaises(ValueError):
            upstream.replace_once("changed", r"^pkgname=chromium$", lambda _: "replacement")

    def test_version_validation(self):
        self.assertGreater(upstream.version_tuple("155.0.8059.39"), upstream.version_tuple("153.0.8010.52"))
        with self.assertRaises(ValueError):
            upstream.version_tuple("155.0/../evil")


if __name__ == "__main__":
    unittest.main()
