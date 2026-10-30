#!/usr/bin/env bash
set -euo pipefail
# Never run package installation or build preparation on a desktop.
[[ "${GITHUB_ACTIONS:-}" == true && ( -f /.dockerenv || -f /run/.containerenv ) ]] || {
  printf 'This driver is restricted to a disposable GitHub Actions container.\n' >&2
  exit 1
}
snapshot=${GLASS_ARCH_SNAPSHOT:?Pinned Arch snapshot required}
[[ "$snapshot" =~ ^20[0-9]{2}/[0-9]{2}/[0-9]{2}$ ]] || exit 1
printf 'Server = https://archive.archlinux.org/repos/%s/$repo/os/$arch\n' "$snapshot" > /etc/pacman.d/mirrorlist
# A pinned snapshot (including downgrades in this disposable container) keeps ABI inputs fixed.
pacman -Syyuu --noconfirm --needed base-devel git sudo zstd python ninja
builder_uid=${GLASS_HOST_UID:?GitHub workspace owner required}
[[ "$builder_uid" =~ ^[1-9][0-9]*$ ]] || exit 1
useradd --create-home --uid "$builder_uid" builder
printf 'builder ALL=(ALL) NOPASSWD: ALL\n' > /etc/sudoers.d/glass-builder
chmod 0440 /etc/sudoers.d/glass-builder
# Do not chown .git: matching the runner UID preserves checkout ownership.
su builder -s /bin/bash -c '
  set -euo pipefail
  mkdir -p artifacts .checkpoint
  if [[ "${GLASS_PREPARE_ONLY:-false}" == true ]]; then
    makepkg --printsrcinfo > .SRCINFO
  fi
  python3 tools/validate_metadata.py
  timeout --signal=TERM --kill-after=120s 45m makepkg --noconfirm --syncdeps --needed --nobuild 2>&1 | tee artifacts/prepare.log
  makepkg --printsrcinfo > .SRCINFO
  version=$(sed -n "s/^pkgver=//p" PKGBUILD)
  source="$PWD/src/chromium-$version"
  output="$source/out/Release"
  export SOURCE_DATE_EPOCH=$(python3 -c "import json; print(json.load(open(\"upstream.json\")).get(\"source_date_epoch\", 1700000000))")
  python3 tools/ci_checkpoint.py normalize --source "$source" --epoch "$SOURCE_DATE_EPOCH"
  pacman -Q | LC_ALL=C sort > artifacts/packages.txt
  identity=$(python3 tools/ci_checkpoint.py identity --root "$PWD" --packages artifacts/packages.txt --epoch "$SOURCE_DATE_EPOCH")
  printf "%s\n" "$identity" > artifacts/checkpoint-identity.txt

  if [[ "${GLASS_PREPARE_ONLY:-false}" == true ]]; then
    (
      source /etc/makepkg.conf
      source ./PKGBUILD
      ninja() { printf "GN-only validation; Chromium compilation skipped.\n"; }
      cd src
      build
    ) 2>&1 | tee artifacts/gn.log
    printf "{\"state\":\"prepared\"}\n" > artifacts/build-state.json
    exit 0
  fi

  python3 tools/ci_checkpoint.py resume --cache "$PWD/.checkpoint" --attempt "${GLASS_BUILD_ATTEMPT:-1}" \
    --expected-key "${GLASS_EXPECTED_KEY:-}" --restored-key "${GLASS_RESTORED_KEY:-}" \
    --identity "${GLASS_EXPECTED_IDENTITY:-}" --progress "${GLASS_EXPECTED_PROGRESS:-0}"
  previous=$(python3 tools/ci_checkpoint.py restore --output "$output" --cache "$PWD/.checkpoint" --identity "$identity")
  set +e
  python3 tools/ci_checkpoint.py run --output "$output" --state artifacts/build-state.json \
    --seconds "${GLASS_BUILD_SECONDS:-16200}" --attempt "${GLASS_BUILD_ATTEMPT:-1}" --previous "$previous" \
    -- makepkg --noconfirm --noextract 2>&1 | tee artifacts/build.log
  result=${PIPESTATUS[0]}
  set -e
  state=$(python3 -c "import json; print(json.load(open(\"artifacts/build-state.json\"))[\"state\"])")
  if [[ "$state" == checkpoint ]]; then
    python3 tools/ci_checkpoint.py save --output "$output" --cache "$PWD/.checkpoint" --identity "$identity" | tee artifacts/checkpoint-save.json
    python3 -c "import json,pathlib; p=pathlib.Path(\"artifacts/build-state.json\"); d=json.loads(p.read_text()); d[\"checkpoint_saved\"]=True; d[\"identity\"]=\"$identity\"; p.write_text(json.dumps(d,indent=2)+\"\\n\")"
    exit 0
  fi
  (( result == 0 )) && [[ "$state" == complete ]] || exit 1
  sha256sum ./*.pkg.tar.zst > artifacts/SHA256SUMS.txt
  binary="$output/chrome"
  "$binary" --version | tee artifacts/version.txt
  if ldd "$binary" | grep -q "not found"; then
    ldd "$binary" > artifacts/missing-libraries.txt
    exit 1
  fi
  timeout --signal=TERM --kill-after=15s 90s "$binary" --headless --no-sandbox --disable-gpu \
    --user-data-dir="$(mktemp -d)" --dump-dom about:blank > artifacts/headless.html
  grep -q "<html" artifacts/headless.html
'
