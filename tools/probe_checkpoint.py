#!/usr/bin/env python3
"""A tiny real Ninja build proving cross-run cache restoration, never Chromium."""
import argparse
import json
import os
from pathlib import Path
import subprocess

from ci_checkpoint import fingerprint, progress, restore_checkpoint, save_checkpoint, classify, supervise

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--attempt", type=int, required=True)
args = parser.parse_args()
output = Path(".probe-output").resolve()
cache = Path(".checkpoint").resolve()
artifacts = Path("artifacts")
artifacts.mkdir(exist_ok=True)
identity = fingerprint({"probe": b"three serial one-second Ninja edges v1"}, "ninja", 100)
previous = restore_checkpoint(output, cache, identity)
if not previous:
    output.mkdir(exist_ok=True)
    (output / "build.ninja").write_text(
        "rule one\n  command = sleep 1; printf done > $out\n"
        "build one: one\nbuild two: one one\nbuild three: one two\ndefault three\n")
before = (output / "one").stat().st_mtime_ns if (output / "one").exists() else None
result, expired = supervise(["ninja", "-j", "1", "-C", str(output)], 2.3 if args.attempt == 1 else 30)
done = progress(output / ".ninja_log")
state = classify(result, expired, args.attempt, previous, done)
meta = {"state": state, "progress": done, "previous_progress": previous,
        "attempt": args.attempt, "identity": identity, "checkpoint_saved": False}
if state == "checkpoint":
    save_checkpoint(output, cache, identity, done)
    meta["checkpoint_saved"] = True
elif state == "complete":
    if args.attempt < 2 or previous < 1:
        raise ValueError("Probe did not demonstrate restoration from an earlier GitHub run")
    if (output / "one").stat().st_mtime_ns != before:
        raise ValueError("Ninja recompiled an output restored from checkpoint")
    meta["restored_without_rebuild"] = True
(artifacts / "build-state.json").write_text(json.dumps(meta, indent=2) + "\n")
print(json.dumps(meta), flush=True)
raise SystemExit(0 if state in ("checkpoint", "complete") else 1)
