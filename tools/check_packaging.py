#!/usr/bin/env python3
"""Apply the complete packaging patch sequence to files from the release tar."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_tar", type=Path)
    parser.add_argument("--arch-checkout", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    meta = json.loads((ROOT / "upstream.json").read_text())
    info = subprocess.check_output(["makepkg", "--printsrcinfo"], cwd=ROOT, text=True)
    sources = re.findall(r"^\s*source = (.+)$", info, re.M)
    hashes = re.findall(r"^\s*sha256sums = (.+)$", info, re.M)
    expected = dict(zip((s.rsplit("/", 1)[-1] for s in sources), hashes, strict=True))
    with args.source_tar.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != meta["source_sha256"]:
            raise ValueError("Release archive checksum mismatch")
    recipe = (ROOT / "PKGBUILD").read_text()
    commands = re.findall(r"^  patch[^\n]+$", recipe, re.M)
    with tempfile.TemporaryDirectory(prefix="glass-packaging-") as temporary:
        directory = Path(temporary)
        source_root = args.source_dir or directory / "source"
        source_root.mkdir(parents=True, exist_ok=True)
        patches = []
        required = set()
        for command in commands:
            name = re.search(r"([^/\s\"]+\.patch)", command)[1]
            prefix_match = re.search(r" -d ([^\s]+)", command)
            prefix = prefix_match[1] if prefix_match else ""
            if (ROOT / name).is_file():
                data = (ROOT / name).read_bytes()
            elif args.arch_checkout:
                data = subprocess.check_output(["git", "-C", str(args.arch_checkout), "show", f'{meta["arch_commit"]}:{name}'])
            else:
                url = f'https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/{meta["arch_commit"]}/{name}'
                with urllib.request.urlopen(url, timeout=45) as response:
                    data = response.read()
            if hashlib.sha256(data).hexdigest() != expected[name]:
                raise ValueError(f"Patch checksum mismatch: {name}")
            patch_path = directory / name
            patch_path.write_bytes(data)
            if args.source_dir:
                (source_root / ".patches").mkdir(exist_ok=True)
                (source_root / ".patches" / name).write_bytes(data)
            for path in re.findall(r"^(?:---|\+\+\+) [ab]/([^\t\n ]+)", data.decode(), re.M):
                full_path = Path(prefix) / path
                if full_path.is_absolute() or ".." in full_path.parts:
                    raise ValueError("Unsafe patch path")
                required.add(full_path.as_posix())
            patches.append((name, prefix, patch_path))
        # Stream the archive; copy only the regular files used by the patches.
        found = set()
        with tarfile.open(args.source_tar, "r|xz") as archive:
            for member in archive:
                name = member.name.removeprefix("./")
                prefix = f'chromium-{meta["version"]}/'
                if not name.startswith(prefix):
                    continue
                path = name[len(prefix):]
                if path in required and member.isfile():
                    target = source_root / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.extractfile(member).read())
                    if args.source_dir:
                        pristine = source_root / ".pristine" / path
                        pristine.parent.mkdir(parents=True, exist_ok=True)
                        pristine.write_bytes(target.read_bytes())
                    found.add(path)
        results = []
        for name, prefix, patch_path in patches:
            cwd = source_root / prefix
            cwd.mkdir(parents=True, exist_ok=True)
            result = subprocess.run(["patch", "--batch", "--forward", "--fuzz=0", "-p1", "-i", str(patch_path)],
                                    cwd=cwd, text=True, capture_output=True)
            results.append({"patch": name, "applies": result.returncode == 0,
                            "output": result.stdout + result.stderr})
        report = {"version": meta["version"], "files_checked": len(found),
                  "patches": results, "all_apply": all(r["applies"] for r in results),
                  "scope": "source and patch checks; compiler and runtime not verified"}
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
        return 0 if report["all_apply"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
