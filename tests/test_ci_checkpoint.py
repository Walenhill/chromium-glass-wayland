"""Checkpoint contract tests. Run on GitHub; no Chromium compilation."""
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
try:
    import ci_checkpoint as policy
except ImportError:
    policy = None


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(policy, "Missing resumable CI policy")
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_success_is_the_only_complete_state(self):
        self.assertEqual(policy.classify(0, False, 1, 0, 4), "complete")
        self.assertEqual(policy.classify(0, True, 1, 0, 4), "checkpoint")

    def test_compiler_error_does_not_retry(self):
        self.assertEqual(policy.classify(1, False, 1, 0, 10), "failed")

    def test_controlled_deadline_can_continue(self):
        self.assertEqual(policy.classify(-2, True, 1, 10, 20), "checkpoint")

    def test_last_slice_does_not_queue_a_seventh(self):
        self.assertEqual(policy.classify(-2, True, 6, 10, 20), "exhausted")

    def test_no_progress_stops_including_first_slice(self):
        self.assertEqual(policy.classify(-2, True, 2, 10, 10), "stalled")
        self.assertEqual(policy.classify(-2, True, 1, 0, 0), "stalled")

    def test_progress_counts_distinct_ninja_outputs(self):
        log = self.root / ".ninja_log"
        log.write_text("# ninja log v5\n0\t1\t2\ta.o\thash\n1\t2\t3\tb.o\thash\n2\t3\t4\ta.o\thash2\n")
        self.assertEqual(policy.progress(log), 2)
        self.assertEqual(policy.progress(self.root / "absent"), 0)

    def test_fingerprint_changes_on_source_or_packages(self):
        self.assertEqual(policy.fingerprint({"recipe": b"a"}, "clang 1", 100),
                         policy.fingerprint({"recipe": b"a"}, "clang 1", 100))
        self.assertNotEqual(policy.fingerprint({"recipe": b"a"}, "clang 1", 100),
                            policy.fingerprint({"recipe": b"b"}, "clang 1", 100))
        self.assertNotEqual(policy.fingerprint({"recipe": b"a"}, "clang 1", 100),
                            policy.fingerprint({"recipe": b"a"}, "clang 2", 100))

    def test_checkpoint_roundtrip_preserves_ninja_resume(self):
        source = self.root / "first"
        source.mkdir()
        (source / "build.ninja").write_text(
            'rule write\n  command = python3 -c "open(\'$out\', \'w\').write(\'done\')"\n'
            'build first.txt: write\nbuild second.txt: write first.txt\ndefault second.txt\n')
        subprocess.run(["ninja", "-C", str(source), "first.txt"], check=True, capture_output=True)
        cache = self.root / "cache"
        policy.save_checkpoint(source, cache, "a" * 64, 1)
        restored = self.root / "restored"
        self.assertEqual(policy.restore_checkpoint(restored, cache, "a" * 64), 1)
        previous = (restored / "first.txt").stat().st_mtime_ns
        subprocess.run(["ninja", "-C", str(restored)], check=True, capture_output=True)
        self.assertTrue((restored / "second.txt").is_file())
        self.assertEqual((restored / "first.txt").stat().st_mtime_ns, previous)
        self.assertEqual(policy.progress(restored / ".ninja_log"), 2)

    def test_identity_mismatch_does_not_extract(self):
        source = self.root / "source"
        source.mkdir()
        (source / "artifact.o").write_text("object")
        cache = self.root / "cache"
        policy.save_checkpoint(source, cache, "a" * 64, 1)
        restored = self.root / "restored"
        with self.assertRaises(ValueError):
            policy.restore_checkpoint(restored, cache, "b" * 64)
        self.assertFalse(restored.exists())

    def test_corruption_does_not_extract(self):
        source = self.root / "source"
        source.mkdir()
        (source / "artifact.o").write_text("object")
        cache = self.root / "cache"
        policy.save_checkpoint(source, cache, "a" * 64, 1)
        archive = cache / "out.tar.zst"
        with archive.open("ab") as stream:
            stream.write(b"corrupt")
        with self.assertRaises(ValueError):
            policy.restore_checkpoint(self.root / "restored", cache, "a" * 64)
        self.assertFalse((self.root / "restored").exists())

    def test_size_limit_does_not_publish_a_partial_checkpoint(self):
        source = self.root / "source"
        source.mkdir()
        (source / "file").write_bytes(os.urandom(4096))
        cache = self.root / "cache"
        with self.assertRaises(ValueError):
            policy.save_checkpoint(source, cache, "a" * 64, 1, max_bytes=32)
        self.assertFalse((cache / "manifest.json").exists())

    def test_archive_traversal_links_and_special_files_are_rejected(self):
        for name, kind in [("../escape", "file"), ("/absolute", "file"),
                           ("link", "symlink"), ("hard", "hardlink"), ("fifo", "fifo")]:
            with self.subTest(name=name):
                member = tarfile.TarInfo(name)
                member.type = {"file": tarfile.REGTYPE, "symlink": tarfile.SYMTYPE,
                               "hardlink": tarfile.LNKTYPE, "fifo": tarfile.FIFOTYPE}[kind]
                member.linkname = "../escape"
                with self.assertRaises(ValueError):
                    policy.validate_member(member)

    def test_source_timestamp_normalization_never_follows_links_or_out(self):
        source = self.root / "source"
        source.mkdir()
        outside = self.root / "outside"
        outside.write_text("not a build input")
        os.utime(outside, (200, 200))
        (source / "link").symlink_to(outside)
        (source / "code.cc").write_text("source")
        (source / "out").mkdir()
        artifact = source / "out/object.o"
        artifact.write_text("cached")
        os.utime(artifact, (300, 300))
        policy.normalize_sources(source, 100)
        self.assertEqual((source / "code.cc").stat().st_mtime, 100)
        self.assertEqual(outside.stat().st_mtime, 200)
        self.assertEqual(artifact.stat().st_mtime, 300)

    def test_deadline_kills_the_child_process_group(self):
        code = "import signal,time; signal.signal(signal.SIGINT, signal.SIG_IGN); time.sleep(20)"
        result, expired = policy.supervise([sys.executable, "-c", code], 0.2, grace=0.2)
        self.assertTrue(expired)
        self.assertNotEqual(result, 0)

    def test_real_error_is_not_reported_as_deadline(self):
        result, expired = policy.supervise([sys.executable, "-c", "raise SystemExit(7)"], 10)
        self.assertEqual(result, 7)
        self.assertFalse(expired)

    def test_workflow_key_ignores_generated_python_files(self):
        root = self.root / "repo"
        root.mkdir()
        for name in ("PKGBUILD", "upstream.json", "chromium-glass-wayland.patch"):
            (root / name).write_text("input")
        (root / "tools").mkdir()
        driver = root / "tools/build_in_container.sh"
        driver.write_text("real build input")
        self.assertTrue(hasattr(policy, "input_fingerprint"), "Missing stable input fingerprint")
        first = policy.input_fingerprint(root, "", 1)
        (root / "tools/__pycache__").mkdir()
        (root / "tools/__pycache__/ci_checkpoint.pyc").write_bytes(b"generated")
        self.assertEqual(policy.input_fingerprint(root, "", 1), first)
        driver.write_text("changed compiler input")
        self.assertNotEqual(policy.input_fingerprint(root, "", 1), first)

    def test_continuation_requires_a_visible_exact_branch_cache(self):
        self.assertTrue(hasattr(policy, "uploaded_checkpoint"), "Missing remote cache existence gate")
        entry = {"id": 1, "ref": "refs/heads/candidate", "key": "expected", "version": "v1",
                 "size_in_bytes": 100, "created_at": "2026-10-29T00:00:00Z",
                 "last_accessed_at": "2026-10-29T00:00:00Z"}
        payload = {"total_count": 1, "actions_caches": [entry]}
        self.assertTrue(policy.uploaded_checkpoint(payload, "expected", "refs/heads/candidate"))
        self.assertFalse(policy.uploaded_checkpoint(payload, "other", "refs/heads/candidate"))
        self.assertFalse(policy.uploaded_checkpoint(payload, "expected", "refs/heads/other"))
        self.assertFalse(policy.uploaded_checkpoint({"actions_caches": []}, "expected", "refs/heads/candidate"))

    def test_hardlinked_ninja_outputs_are_saved_as_regular_files(self):
        source = self.root / "source"
        source.mkdir()
        (source / "a.o").write_bytes(b"compiled object")
        os.link(source / "a.o", source / "b.o")
        cache = self.root / "cache"
        try:
            policy.save_checkpoint(source, cache, "a" * 64, 1)
        except ValueError as error:
            self.fail("Valid hardlinked build outputs were rejected: " + str(error))
        restored = self.root / "restored"
        policy.restore_checkpoint(restored, cache, "a" * 64)
        self.assertEqual((restored / "a.o").read_bytes(), b"compiled object")
        self.assertEqual((restored / "b.o").read_bytes(), b"compiled object")


if __name__ == "__main__":
    unittest.main()
