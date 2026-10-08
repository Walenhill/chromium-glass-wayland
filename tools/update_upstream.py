#!/usr/bin/env python3
"""Prepare a Glass candidate using Linux Stable and pinned Arch packaging."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
ARCH_URL = "https://gitlab.archlinux.org/archlinux/packaging/packages/chromium.git"
STABLE_URL = "https://chromiumdash.appspot.com/fetch_releases?channel=Stable&platform=Linux&num=1"


def latest():
    for attempt in range(3):
        try:
            with urllib.request.urlopen(STABLE_URL, timeout=30) as response:
                release = json.load(response)[0]
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    if release.get("channel") != "Stable" or release.get("platform") != "Linux":
        raise ValueError("Unexpected upstream release channel")
    return release["version"]


def version_tuple(value):
    if not re.fullmatch(r"\d+\.\d+\.\d+\.\d+", value):
        raise ValueError(f"Invalid version: {value!r}")
    return tuple(map(int, value.split(".")))


def replace_once(text, pattern, replacement):
    result, count = re.subn(pattern, lambda match: replacement(match), text, flags=re.M)
    if count != 1:
        raise ValueError(f"Arch recipe changed: expected one occurrence of {pattern!r}, got {count}")
    return result


def render(arch, commit, version, source_sha, glass_sha):
    if version_tuple(version)[0] != 155:
        raise ValueError("A new Chromium milestone needs a reviewed build overlay first")
    text = replace_once(arch, r"^pkgname=chromium$", lambda _: "pkgname=chromium-glass")
    text = replace_once(text, r"^pkgver=\S+$", lambda _: f"pkgver={version}")
    text = replace_once(text, r"^pkgrel=\S+$", lambda _: "pkgrel=1")
    text = replace_once(text, r"^_launcher_ver=(\d+)$", lambda m: m[0] +
                        f'\n_arch_pkg_commit={commit}\n_arch_pkg_base="https://gitlab.archlinux.org/archlinux/packaging/packages/chromium/-/raw/$_arch_pkg_commit"')
    text = replace_once(text, r"^_manual_clone=\d+$", lambda _: "_manual_clone=0")
    text = replace_once(text, r"^_system_clang=\d+$", lambda _: "_system_clang=0")
    # Use Chromium's matching LLVM/Rust/Crubit bundle to preserve its new font APIs.
    skipped = ['compiler-rt-adjust-paths.patch', 'chromium-149-drop-unknown-clang-flag.patch',
               'chromium-147-revert-clang-no-lifetime-dse-flag.patch',
               'chromium-147-rust-1.95-bytemuck.patch', 'chromium-153-crubit.patch',
               'chromium-149-build-with-wasm-rollup.patch', 'chromium-152-fix-gn-no-public_inputs.patch']
    for name in skipped:
        text, count = re.subn(r'^  patch[^\n]*' + re.escape(name) + r'[^\n]*\n', '', text, flags=re.M)
        if count != 1:
            raise ValueError(f"Expected one obsolete build patch command: {name}")
    text = replace_once(text, r"^pkgdesc=.*$", lambda _: 'pkgdesc="Chromium with native translucent browser chrome for Wayland compositors"')
    text = replace_once(text, r"^license=\([^\n]+\)$", lambda m: m[0] +
                        '\nprovides=("chromium=$pkgver")\nconflicts=(\'chromium\')\nbackup=(\'etc/chromium-flags.conf\')')
    source_match = re.search(r"^source=\([\s\S]*?\)\nsha256sums=", text, re.M)
    if not source_match:
        raise ValueError("Cannot locate Arch source array")
    block = source_match[0]
    block = re.sub(r"(?m)^(\s+)([A-Za-z0-9_.-]+\.patch)", r"\1$_arch_pkg_base/\2", block)
    block = block.replace(")\nsha256sums=", "\n        chromium-glass-wayland.patch)\nsha256sums=")
    text = text[:source_match.start()] + block + text[source_match.end():]
    text = replace_once(text, r"^sha256sums=\('[a-f0-9]{64}'", lambda _: f"sha256sums=('{source_sha}'")
    text = replace_once(text, r"(^sha256sums=\([\s\S]*?)\)\n\nif", lambda m: m[1] + f"\n            '{glass_sha}')\n\nif")
    text = replace_once(text, r"^prepare\(\) \{\n[\s\S]*?^  cd chromium-\$pkgver\n", lambda m: m[0] +
                        "\n  # Apply every Glass hunk strictly; reject context drift.\n  patch --batch --fuzz=0 -Np1 -i ../chromium-glass-wayland.patch\n")
    text = replace_once(text, r"^  # Allow building against system libraries in official builds$", lambda m:
                        '  python3 "$startdir/tools/fetch_esbuild.py" "$PWD"\n\n' + m[0])
    text = replace_once(text, r"^    ./tools/clang/scripts/update.py$", lambda m:
                        m[0] + '\n    python3 tools/update_pgo_profiles.py --target=linux update --gs-url-base=chromium-optimization-profiles/pgo_profiles')
    text = replace_once(text, r"^  gn gen out/Release --args=.*$", lambda m:
                        '  if command -v sccache >/dev/null; then\n    _flags+=(\'cc_wrapper="sccache"\')\n  fi\n' +
                        m[0].replace('  gn gen', '  buildtools/linux64/gn gen'))
    text = replace_once(text, r"^  ninja -C out/Release chrome chrome_sandbox chromedriver.unstripped$", lambda _:
                        '  ninja -j "${GLASS_BUILD_JOBS:-4}" -C out/Release chrome chrome_sandbox chromedriver.unstripped')
    text = replace_once(text, r"^  # Fill in common Chrome/Chromium AppData template with Chromium info$", lambda m:
                        "  install -Dvm644 /dev/stdin \"$pkgdir/etc/chromium-flags.conf\" <<'EOF'\n"
                        "--ozone-platform=wayland\n--enable-features=GlassFrame\n--class=chromium-glass\nEOF\n"
                        "  sed -i -e 's/^Name=Chromium$/Name=Chromium Glass/' \\\n"
                        "    -e '/^StartupNotify=true$/a StartupWMClass=chromium-glass' \\\n"
                        '    "$pkgdir/usr/share/applications/chromium.desktop"\n\n' + m[0])
    return text


def digest_source(version, source_tar):
    digest = hashlib.sha256()
    if source_tar:
        stream = source_tar.open("rb")
    else:
        url = f"https://commondatastorage.googleapis.com/chromium-browser-official/chromium-{version}-lite.tar.xz"
        stream = urllib.request.urlopen(url, timeout=120)
    with stream:
        while chunk := stream.read(4 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version")
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--arch-checkout", type=Path)
    parser.add_argument("--source-tar", type=Path)
    args = parser.parse_args()
    version = args.version or latest()
    current = re.search(r"^pkgver=(\S+)$", (ROOT / "PKGBUILD").read_text(), re.M)[1]
    report = {"current": current, "linux_stable": version,
              "update_available": version_tuple(version) > version_tuple(current)}
    print(json.dumps(report))
    if not args.prepare:
        return
    if version_tuple(version) < version_tuple(current):
        parser.error("Refusing a version downgrade")
    # Source compatibility is required before writing a new recipe.
    subprocess.run(["python3", str(ROOT / "tools/check_compatibility.py"), version], check=True)
    with tempfile.TemporaryDirectory(prefix="glass-arch-") as temporary:
        checkout = args.arch_checkout or Path(temporary) / "arch"
        if not args.arch_checkout:
            subprocess.run(["git", "-c", "http.version=HTTP/1.1", "clone", "--depth=1", ARCH_URL, str(checkout)], check=True)
        ref = "origin/main"
        commit = subprocess.check_output(["git", "-C", str(checkout), "rev-parse", ref], text=True).strip()
        arch = subprocess.check_output(["git", "-C", str(checkout), "show", f"{commit}:PKGBUILD"], text=True)
        arch_version = re.search(r"^pkgver=(\S+)$", arch, re.M)[1]
        if version_tuple(arch_version) > version_tuple(version):
            raise ValueError("Arch recipe is newer than the target; refusing a downgrade")
        source_sha = digest_source(version, args.source_tar)
        glass_sha = hashlib.sha256((ROOT / "chromium-glass-wayland.patch").read_bytes()).hexdigest()
        recipe = render(arch, commit, version, source_sha, glass_sha)
        (ROOT / "PKGBUILD").write_text(recipe)
        (ROOT / "upstream.json").write_text(json.dumps({
            "version": version, "arch_recipe_version": arch_version, "arch_commit": commit,
            "source_sha256": source_sha, "glass_patch_sha256": glass_sha,
            "status": "candidate; full build and visual validation required",
        }, indent=2) + "\n")
        readme = ROOT / "README.md"
        readme.write_text(re.sub(r"currently based on Chromium `[^`]+`", f"currently based on Chromium `{version}`", readme.read_text()))


if __name__ == "__main__":
    main()
