#!/usr/bin/env python3
"""Promote a successful attested build only through the visual-approval workflow."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from stable_update import REPO, PACKAGE, POLICY, check_manifest


def main():
    if os.environ.get("GITHUB_REF") != "refs/heads/main":
        raise ValueError("Approval must run from main")
    run_id = sys.argv[1]
    if not run_id.isdecimal():
        raise ValueError("Build run must be a numeric ID")
    run = json.loads(subprocess.check_output(["gh", "api", f"repos/{REPO}/actions/runs/{run_id}"], text=True))
    if (run.get("path") != ".github/workflows/build.yml" or
            run.get("conclusion") != "success" or run.get("status") != "completed" or
            run.get("event") not in ("workflow_dispatch", "push") or
            run.get("head_repository", {}).get("full_name") != REPO):
        raise ValueError("Not a successful trusted candidate build")
    sha = run["head_sha"]
    if not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ValueError("Invalid build revision")
    subprocess.run(["git", "fetch", "origin", sha], check=True)
    # Accept a tested branch merged into main without requiring recompilation,
    # but only if all build inputs are byte-identical to the approved checkout.
    subprocess.run(["git", "diff", "--exit-code", sha, "HEAD", "--",
                    "PKGBUILD", ".SRCINFO", "upstream.json", "chromium-glass-wayland.patch",
                    "tools", ".github/workflows/build.yml"], check=True)
    subprocess.run(["python3", "tools/validate_metadata.py"], check=True)
    out = Path("release")
    out.mkdir(exist_ok=False)
    subprocess.run(["gh", "run", "download", run_id, "--repo", REPO,
                    "--name", "chromium-glass-candidate", "--dir", str(out)], check=True)
    recipe = Path("PKGBUILD").read_text()
    version = re.search(r"^pkgver=(\S+)$", recipe, re.M)[1]
    rel = re.search(r"^pkgrel=(\S+)$", recipe, re.M)[1]
    package_version = version + "-" + rel
    filename = f"{PACKAGE}-{package_version}-x86_64.pkg.tar.zst"
    binary = out / filename
    candidates = list(out.glob("*.pkg.tar.zst"))
    if candidates != [binary] or not binary.is_file():
        raise ValueError("Unexpected candidate package set")
    evidence = out / "artifacts"
    bundle = evidence / "build-attestation.json"
    subprocess.run(["gh", "attestation", "verify", str(binary), "--bundle", str(bundle),
                    "--repo", REPO, "--signer-workflow", f"{REPO}/.github/workflows/build.yml",
                    "--source-digest", sha], check=True)
    if not (evidence / "headless.html").is_file() or "<html" not in (evidence / "headless.html").read_text():
        raise ValueError("Missing successful runtime smoke evidence")
    if version not in (evidence / "version.txt").read_text():
        raise ValueError("Unexpected compiled Chromium version")
    with binary.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    meta = {"schema": 1, "repository": REPO, "tag": "v" + package_version,
            "package_version": package_version, "package": filename, "arch": "x86_64",
            "sha256": digest, "build_commit": sha, "build_run": int(run_id),
            "validation_policy": POLICY, "visual_approved": True,
            "approved_by": os.environ["GITHUB_ACTOR"]}
    check_manifest(meta, meta["tag"])
    (out / "stable.json").write_text(json.dumps(meta, indent=2) + "\n")
    (out / "build-attestation.json").write_bytes(bundle.read_bytes())
    (out / "notes.md").write_text(
        f"Experimental Chromium Glass {package_version}.\n\n"
        "Compiled in a clean Arch container; headless/version/library checks passed.\n"
        "Maintainer approved Wayland blur, menus, search popups and a second window.\n"
        f"Build evidence: https://github.com/{REPO}/actions/runs/{run_id}\n\n"
        "The auto-updater verifies the approval and build attestations, package identity "
        "and SHA-256. Compatibility with every compositor/GPU is not guaranteed.\n")


if __name__ == "__main__":
    main()
