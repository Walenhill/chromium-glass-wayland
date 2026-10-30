#!/usr/bin/env python3
"""Reject stale recipe/SRCINFO hashes or a mismatched upstream manifest."""
import hashlib
import json
from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
meta = json.loads((root / "upstream.json").read_text())
recipe = (root / "PKGBUILD").read_text()
info = (root / ".SRCINFO").read_text()
version = re.search(r"^pkgver=(\S+)$", recipe, re.M)[1]
assert version == meta["version"], "Recipe version does not match upstream.json"
assert re.search(r"^\s*pkgver = (\S+)$", info, re.M)[1] == version, "Stale .SRCINFO version"
digest = hashlib.sha256((root / "chromium-glass-wayland.patch").read_bytes()).hexdigest()
assert digest == meta["glass_patch_sha256"], "Stale Glass manifest hash"
assert digest in recipe and digest in info, "Stale Glass recipe/SRCINFO hash"
assert meta["source_sha256"] in recipe and meta["source_sha256"] in info, "Stale source hash"
assert re.fullmatch(r"[a-f0-9]{40}", meta["arch_commit"]), "Arch packaging must be pinned to a commit"
assert f'_arch_pkg_commit={meta["arch_commit"]}' in recipe, "Incorrect Arch revision"
print(f"Metadata verified for Chromium Glass {version}")
