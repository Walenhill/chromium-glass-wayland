#!/usr/bin/env bash
set -euo pipefail

# This script is for an isolated disposable Arch container, never the host.
if [[ ! -f /.dockerenv && ! -f /run/.containerenv ]]; then
  printf 'Run this script inside a disposable Arch container.\n' >&2
  exit 1
fi
pacman -Syu --noconfirm --needed base-devel git sudo sccache
useradd --create-home builder
printf 'builder ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/glass-builder
chmod 0440 /etc/sudoers.d/glass-builder
chown -R builder:builder /build

su builder -s /bin/bash -c '
  set -euo pipefail
  mkdir -p artifacts
  python3 tools/validate_metadata.py
  makepkg --noconfirm --syncdeps --needed --nobuild 2>&1 | tee artifacts/prepare.log
  makepkg --noconfirm --noextract 2>&1 | tee artifacts/build.log
  sha256sum ./*.pkg.tar.zst > artifacts/SHA256SUMS.txt
  binary="src/chromium-$(sed -n "s/^pkgver=//p" PKGBUILD)/out/Release/chrome"
  "$binary" --version | tee artifacts/version.txt
  if ldd "$binary" | grep -q "not found"; then
    ldd "$binary" > artifacts/missing-libraries.txt
    exit 1
  fi
  "$binary" --headless --no-sandbox --disable-gpu --user-data-dir="$(mktemp -d)" --dump-dom about:blank > artifacts/headless.html
  grep -q "<html" artifacts/headless.html
  sccache --show-stats > artifacts/cache-stats.txt
'
