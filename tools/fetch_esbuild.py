#!/usr/bin/env python3
"""Fetch the exact esbuild binary required by the bundled DevTools JS module."""
import base64
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import tarfile
import urllib.request

root = Path(sys.argv[1]).resolve()
devtools = root / "third_party/devtools-frontend/src"
version = json.loads((devtools / "node_modules/esbuild/package.json").read_text())["version"]
if not re.fullmatch(r"\d+\.\d+\.\d+", version):
    raise ValueError("Invalid bundled esbuild version")
with urllib.request.urlopen(f"https://registry.npmjs.org/@esbuild/linux-x64/{version}", timeout=60) as response:
    metadata = json.load(response)
url = metadata["dist"]["tarball"]
if not url.startswith("https://registry.npmjs.org/@esbuild/linux-x64/"):
    raise ValueError("Unexpected esbuild download URL")
with urllib.request.urlopen(url, timeout=120) as response:
    data = response.read()
integrity = "sha512-" + base64.b64encode(hashlib.sha512(data).digest()).decode()
if integrity != metadata["dist"]["integrity"]:
    raise ValueError("esbuild npm integrity mismatch")
with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
    binary = archive.extractfile("package/bin/esbuild").read()
target = devtools / "third_party/esbuild/esbuild"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_bytes(binary)
target.chmod(0o755)
print(f"Fetched verified esbuild {version} for the DevTools JS wrapper")
