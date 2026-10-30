#!/usr/bin/env python3
"""Bounded GitHub-only build supervision and validated Ninja checkpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import subprocess
import tarfile
import sys
import threading
import time

MAX_BYTES = 8 * 1024 ** 3
MAX_RAW_BYTES = 64 * 1024 ** 3
MAX_ATTEMPTS = 6


def classify(returncode, timed_out, attempt, previous_progress, current_progress, failure_evidence=False):
    if failure_evidence:
        return "failed"
    if returncode == 0 and not timed_out:
        return "complete"
    if not timed_out:
        return "failed"
    if current_progress <= previous_progress:
        return "stalled"
    if attempt >= MAX_ATTEMPTS:
        return "exhausted"
    return "checkpoint"


def progress(log):
    if not log.exists():
        return 0
    outputs = set()
    for line in log.read_text(errors="replace").splitlines():
        fields = line.split("\t")
        if len(fields) >= 5 and not line.startswith("#"):
            outputs.add(fields[3])
    return len(outputs)


def fingerprint(files, packages, epoch):
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
    digest.update(packages.encode() + b"\0" + str(epoch).encode())
    return digest.hexdigest()


def input_fingerprint(root, packages, epoch):
    paths = ["PKGBUILD", "upstream.json", "chromium-glass-wayland.patch"]
    paths += [str(p.relative_to(root)) for p in (root / "tools").glob("*")
              if p.is_file() and p.suffix in (".py", ".sh")]
    return fingerprint({p: (root / p).read_bytes() for p in paths}, packages, epoch)


def uploaded_checkpoint(payload, key, ref):
    return any(entry.get("key") == key and entry.get("ref") == ref and
               type(entry.get("size_in_bytes")) is int and entry["size_in_bytes"] > 0
               for entry in payload.get("actions_caches", []))


def require_resume(attempt, expected_key, restored_key, expected_identity, expected_progress, manifest):
    if attempt == 1 and not expected_key:
        return
    if not expected_key or restored_key != expected_key:
        raise ValueError("Required exact checkpoint is unavailable; refusing a fresh automatic build")
    if not re.fullmatch("[a-f0-9]{64}", expected_identity) or expected_progress <= 0:
        raise ValueError("Missing continuation identity/progress")
    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise ValueError("Required checkpoint manifest is unavailable")
    if manifest.get("identity") != expected_identity or manifest.get("progress") != expected_progress:
        raise ValueError("Required checkpoint identity/progress does not match the producer")


def failed_output(path):
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", path.read_text(errors="replace"))
    return any(line.lstrip().startswith("FAILED:") or
               "ninja: build stopped: subcommand failed" in line
               for line in text.splitlines())


def validate_member(member):
    path = PurePosixPath(member.name)
    if path.is_absolute() or ".." in path.parts or "\\" in member.name:
        raise ValueError("Checkpoint path escapes the output directory")
    if not (member.isfile() or member.isdir()):
        raise ValueError("Checkpoint links and special files are not allowed")


def supervise(command, seconds, grace=120, log=None):
    if seconds <= 0 or grace <= 0:
        raise ValueError("Build deadline must be positive")
    stream = None
    reader = None
    errors = []
    if log:
        log.parent.mkdir(parents=True, exist_ok=True)
        stream = log.open("wb")
    child = subprocess.Popen(command, start_new_session=True,
                             stdout=subprocess.PIPE if stream else None,
                             stderr=subprocess.STDOUT if stream else None)
    def signal_group(value):
        try:
            os.killpg(child.pid, value)
        except ProcessLookupError:
            pass
    if stream:
        def copy_output():
            try:
                for chunk in iter(lambda: child.stdout.read1(65536), b""):
                    stream.write(chunk)
                    stream.flush()
                    console = getattr(sys.stdout, "buffer", None)
                    if console:
                        console.write(chunk)
                    else:
                        sys.stdout.write(chunk.decode("utf-8", errors="replace"))
                    sys.stdout.flush()
            except Exception as error:
                errors.append(error)
                signal_group(signal.SIGKILL)
        reader = threading.Thread(target=copy_output, daemon=True)
        reader.start()
    expired = False
    try:
        try:
            result = child.wait(timeout=seconds)
        except subprocess.TimeoutExpired:
            expired = True
            signal_group(signal.SIGINT)
            try:
                result = child.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                signal_group(signal.SIGKILL)
                result = child.wait()
    finally:
        if expired or child.poll() is None:
            signal_group(signal.SIGKILL)
            child.wait()
        if reader:
            reader.join(timeout=10)
            if reader.is_alive():
                signal_group(signal.SIGKILL)
                reader.join(timeout=5)
            if reader.is_alive():
                raise RuntimeError("Build subprocess retained its output pipe after termination")
        if stream:
            stream.close()
    if errors:
        raise RuntimeError("Could not persist build failure evidence") from errors[0]
    return result, expired

def normalize_sources(source, epoch):
    if source.is_symlink() or not source.is_dir() or epoch < 1:
        raise ValueError("Invalid prepared source directory or epoch")
    for directory, directories, files in os.walk(source, followlinks=False):
        directories[:] = [name for name in directories if name not in ("out", ".git")]
        for name in files:
            path = Path(directory) / name
            if not path.is_symlink():
                os.utime(path, (epoch, epoch), follow_symlinks=False)


def inspect_archive(archive):
    total = 0
    with subprocess.Popen(["zstd", "-qdc", "--", str(archive)], stdout=subprocess.PIPE) as decoder:
        try:
            with tarfile.open(fileobj=decoder.stdout, mode="r|") as stream:
                for member in stream:
                    validate_member(member)
                    total += member.size
                    if total > MAX_RAW_BYTES:
                        raise ValueError("Checkpoint exceeds uncompressed size limit")
        except Exception:
            decoder.kill()
            decoder.wait()
            raise
        if decoder.wait():
            raise ValueError("Invalid checkpoint compression")


def save_checkpoint(output, cache, identity, completed, max_bytes=MAX_BYTES):
    if not output.is_dir() or output.is_symlink():
        raise ValueError("Missing Ninja outputs")
    if not re.fullmatch("[a-f0-9]{64}", identity):
        raise ValueError("Invalid checkpoint identity")
    cache.mkdir(parents=True, exist_ok=True)
    temporary = cache / "out.tar.zst.part"
    try:
        subprocess.run(["tar", "--hard-dereference", "-I", "zstd -T2 -3", "-cf", str(temporary),
                        "-C", str(output), "."], check=True)
        if temporary.stat().st_size > max_bytes:
            raise ValueError("Checkpoint exceeds the free-cache size budget")
        inspect_archive(temporary)
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        temporary.replace(cache / "out.tar.zst")
        manifest = {"schema": 1, "identity": identity, "progress": completed, "sha256": digest}
        (cache / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    finally:
        temporary.unlink(missing_ok=True)


def restore_checkpoint(output, cache, identity):
    manifest_path = cache / "manifest.json"
    archive = cache / "out.tar.zst"
    if not manifest_path.exists() and not archive.exists():
        return 0
    if not manifest_path.is_file() or not archive.is_file() or archive.is_symlink():
        raise ValueError("Incomplete checkpoint")
    meta = json.loads(manifest_path.read_text())
    if meta.get("schema") != 1 or meta.get("identity") != identity:
        raise ValueError("Checkpoint input/toolchain identity mismatch")
    if type(meta.get("progress")) is not int or meta["progress"] < 0:
        raise ValueError("Invalid checkpoint progress")
    if archive.stat().st_size > MAX_BYTES:
        raise ValueError("Checkpoint exceeds the free-cache size budget")
    with archive.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != meta.get("sha256"):
            raise ValueError("Checkpoint checksum mismatch")
    # Validate the WHOLE archive before creating/writing any output.
    inspect_archive(archive)
    if output.is_symlink() or (output.exists() and any(output.iterdir())):
        raise ValueError("Refusing to overwrite existing Ninja output")
    output.mkdir(parents=True, exist_ok=True)
    with subprocess.Popen(["zstd", "-qdc", "--", str(archive)], stdout=subprocess.PIPE) as decoder:
        with tarfile.open(fileobj=decoder.stdout, mode="r|") as stream:
            stream.extractall(output, filter="data")
        if decoder.wait():
            raise ValueError("Checkpoint decompression failed")
    return meta["progress"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    identity = commands.add_parser("identity")
    identity.add_argument("--root", type=Path, required=True)
    identity.add_argument("--packages", type=Path, required=True)
    identity.add_argument("--epoch", type=int, required=True)
    normalize = commands.add_parser("normalize")
    normalize.add_argument("--source", type=Path, required=True)
    normalize.add_argument("--epoch", type=int, required=True)
    for name in ("save", "restore"):
        action = commands.add_parser(name)
        action.add_argument("--output", type=Path, required=True)
        action.add_argument("--cache", type=Path, required=True)
        action.add_argument("--identity", required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("--cache", type=Path, required=True)
    resume.add_argument("--attempt", type=int, required=True)
    resume.add_argument("--expected-key", required=True)
    resume.add_argument("--restored-key", required=True)
    resume.add_argument("--identity", required=True)
    resume.add_argument("--progress", type=int, required=True)
    action = commands.add_parser("run")
    action.add_argument("--output", type=Path, required=True)
    action.add_argument("--state", type=Path, required=True)
    action.add_argument("--seconds", type=int, required=True)
    action.add_argument("--attempt", type=int, required=True)
    action.add_argument("--previous", type=int, required=True)
    action.add_argument("argv", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command == "identity":
        print(input_fingerprint(args.root, args.packages.read_text(), args.epoch))
    elif args.command == "normalize":
        normalize_sources(args.source, args.epoch)
    elif args.command == "save":
        print(json.dumps(save_checkpoint(args.output, args.cache, args.identity,
                                         progress(args.output / ".ninja_log"))))
    elif args.command == "restore":
        print(restore_checkpoint(args.output, args.cache, args.identity))
    elif args.command == "resume":
        path = args.cache / "manifest.json"
        manifest = json.loads(path.read_text()) if path.is_file() and not path.is_symlink() else None
        require_resume(args.attempt, args.expected_key, args.restored_key,
                       args.identity, args.progress, manifest)
    else:
        if not 1 <= args.attempt <= MAX_ATTEMPTS:
            parser.error("Slice number must be in 1..6")
        command = args.argv[1:] if args.argv[:1] == ["--"] else args.argv
        if not command:
            parser.error("Missing build command")
        started = time.monotonic()
        log = args.state.parent / "command.log"
        result, timed_out = supervise(command, args.seconds, log=log)
        failure = failed_output(log)
        done = progress(args.output / ".ninja_log")
        state = classify(result, timed_out, args.attempt, args.previous, done, failure)
        meta = {"state": state, "attempt": args.attempt, "previous_progress": args.previous,
                "progress": done, "returncode": result, "deadline_reached": timed_out,
                "failure_evidence": failure, "elapsed_seconds": round(time.monotonic() - started)}
        args.state.parent.mkdir(parents=True, exist_ok=True)
        args.state.write_text(json.dumps(meta, indent=2) + "\n")
        print(json.dumps(meta), flush=True)
        return 0 if state in ("complete", "checkpoint") else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
