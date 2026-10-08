#!/usr/bin/env python3
"""Install only approved, attested releases; never compile or upgrade the OS."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request

REPO = "Walenhill/chromium-glass-wayland"
PACKAGE = "chromium-glass"
ASSET_BASE = f"https://github.com/{REPO}/releases/download/"
POLICY = "wayland-visual-v1"
MAX_PACKAGE = 512 * 1024 * 1024


def check_manifest(meta, tag):
    if meta.get("schema") != 1 or meta.get("repository") != REPO:
        raise ValueError("Unknown release manifest")
    version = meta.get("package_version", "")
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+-[1-9]\d*", version):
        raise ValueError("Invalid package version")
    if tag != "v" + version or meta.get("tag") != tag:
        raise ValueError("Release tag/version mismatch")
    expected = f"{PACKAGE}-{version}-x86_64.pkg.tar.zst"
    if meta.get("package") != expected or meta.get("arch") != "x86_64":
        raise ValueError("Unexpected package identity")
    if not re.fullmatch(r"[a-f0-9]{64}", meta.get("sha256", "")):
        raise ValueError("Invalid package hash")
    if not re.fullmatch(r"[a-f0-9]{40}", meta.get("build_commit", "")):
        raise ValueError("Invalid build commit")
    if meta.get("validation_policy") != POLICY or meta.get("visual_approved") is not True:
        raise ValueError("Release lacks real Wayland visual approval")
    return expected


def asset_url(release, name):
    matches = [a for a in release.get("assets", []) if a.get("name") == name]
    if len(matches) != 1:
        raise ValueError(f"Missing or ambiguous release asset: {name}")
    url = matches[0].get("browser_download_url", "")
    if url != ASSET_BASE + release["tag_name"] + "/" + name:
        raise ValueError("Unexpected release asset origin")
    return url


def fetch(url, target=None, limit=2 * 1024 * 1024):
    request = urllib.request.Request(url, headers={"User-Agent": "chromium-glass-updater/1"})
    with urllib.request.urlopen(request, timeout=90) as response:
        total = 0
        chunks = []
        stream = target.open("wb") if target else None
        try:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise ValueError("Release asset exceeds size limit")
                if stream:
                    stream.write(chunk)
                else:
                    chunks.append(chunk)
        finally:
            if stream:
                stream.close()
    return b"" if target else b"".join(chunks)


def verify(path, bundle, workflow, commit=None):
    command = ["gh", "attestation", "verify", str(path), "--bundle", str(bundle),
               "--repo", REPO, "--signer-workflow", f"{REPO}/.github/workflows/{workflow}"]
    if workflow == "release.yml":
        command += ["--source-ref", "refs/heads/main"]
    if commit:
        command += ["--source-digest", commit]
    # Public offline bundles need no personal GitHub token or login.
    env = {k: v for k, v in os.environ.items() if k not in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN")}
    env["GH_CONFIG_DIR"] = str(bundle.parent / "unused-gh-config")
    subprocess.run(command, check=True, env=env, timeout=180)


def browser_running(proc=Path("/proc")):
    for process in proc.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            exe = os.readlink(process / "exe").removesuffix(" (deleted)")
            if exe == "/usr/lib/chromium/chromium":
                return True
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue
    return False


def run(install=False):
    if install and os.geteuid() != 0:
        raise PermissionError("Installation requires the root systemd service")
    current = subprocess.run(["pacman", "-Q", PACKAGE], text=True, capture_output=True)
    if current.returncode:
        print("Chromium Glass is not installed; no action")
        return
    installed = current.stdout.split()[1]
    try:
        release = json.loads(fetch(f"https://api.github.com/repos/{REPO}/releases/latest"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            print("No published verified stable release; keeping installed browser")
            return
        raise
    if release.get("draft") is not False or release.get("prerelease") is not False:
        raise ValueError("Refusing an unpublished/prerelease build")
    tag = release.get("tag_name", "")
    if not re.fullmatch(r"v\d+\.\d+\.\d+\.\d+-[1-9]\d*", tag):
        raise ValueError("Unexpected stable tag")
    proposed = tag[1:]
    if int(subprocess.check_output(["vercmp", proposed, installed], text=True)) <= 0:
        print(f"Installed {installed}; no newer stable release")
        return
    with tempfile.TemporaryDirectory(prefix="glass-update-") as directory:
        stage = Path(directory)
        manifest = stage / "stable.json"
        approval = stage / "release-attestation.json"
        fetch(asset_url(release, manifest.name), manifest)
        fetch(asset_url(release, approval.name), approval)
        verify(manifest, approval, "release.yml")
        meta = json.loads(manifest.read_text())
        filename = check_manifest(meta, tag)
        if not install:
            print(f"Verified stable {proposed} available; check-only, not installed")
            return
        if browser_running() or Path("/var/lib/pacman/db.lck").exists():
            print("Browser or pacman is active; deferred until next timer run")
            return
        binary = stage / filename
        build = stage / "build-attestation.json"
        fetch(asset_url(release, filename), binary, MAX_PACKAGE)
        fetch(asset_url(release, build.name), build)
        with binary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != meta["sha256"]:
            raise ValueError("Package checksum mismatch")
        verify(binary, build, "build.yml", meta["build_commit"])
        identity = subprocess.check_output(["pacman", "-Qp", str(binary)], text=True).strip()
        if identity != f"{PACKAGE} {proposed}":
            raise ValueError("Package database identity does not match the approved manifest")
        # Recheck after downloading; never force-close a browser or bypass pacman locks.
        if browser_running() or Path("/var/lib/pacman/db.lck").exists():
            print("Browser/pacman started during download; installation deferred")
            return
        cache = Path("/var/cache/chromium-glass")
        cache.mkdir(mode=0o755, parents=True, exist_ok=True)
        cached = cache / filename
        if cached.is_symlink():
            raise ValueError("Unsafe cached package path")
        # /tmp may be tmpfs: copy first, then atomically rename on cache's FS.
        with tempfile.NamedTemporaryFile(prefix=".download-", dir=cache, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                with binary.open("rb") as source:
                    shutil.copyfileobj(source, stream)
                stream.flush()
                os.fsync(stream.fileno())
                temporary.chmod(0o644)
                os.replace(temporary, cached)
            finally:
                temporary.unlink(missing_ok=True)
        # No -Sy/-Syu, no forced dependency bypass, no signature-policy changes.
        # Missing/newer system dependencies stop the transaction normally.
        subprocess.run(["pacman", "-U", "--noconfirm", str(cached)], check=True, timeout=300)
        print(f"Installed approved Chromium Glass {proposed}; package retained in {cache}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        with open("/run/lock/chromium-glass-update.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            run(True)
    else:
        run()


if __name__ == "__main__":
    main()
