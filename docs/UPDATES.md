# Updates and release validation

Chromium Glass is experimental. Source compatibility, a successful compile,
and actual compositor blur are three different checks; none substitutes for
the others. A candidate is never automatically considered stable.

## Maintainer pipeline

1. `update.yml` checks official **Linux Stable** daily and opens a candidate PR.
   The Arch recipe is pinned to a commit. Strict patch counts, zero-fuzz
   application and required integration snippets reject incomplete ports.
2. `build.yml` prepares/builds in a disposable Arch container, caches compiler
   output, checks runtime libraries, version and headless startup, and attaches
   a build attestation. Full builds need substantial disk/RAM and time; runners
   without 80 GiB free fail early. A configured build runner can be selected
   through the workflow's `runner` input. Nothing is installed on the desktop.
3. Check the exact candidate in native Wayland with an isolated test profile:
   toolbar and inactive/active tabs, omnibox/history, main and context menus,
   bubbles/extensions, light/dark themes, rounded edges, and **a second new
   window**. Check CPU/RAM responsiveness with menus both closed and open.
   Do not approve a regression just because the build is successful.
4. Merge the tested inputs to `main`. Run `release.yml` **from main** with the
   successful build run ID and `visual_approved=true`. It checks build origin,
   attestation, unchanged build inputs and smoke evidence. It publishes the
   package plus `stable.json`, a build attestation and a separate approval
   attestation. Existing release assets are not overwritten.

The approval is a maintainer's human decision, not an automated visual test or
security audit. These attestations authenticate the build/approval workflows;
they do not prove that Chromium has no vulnerabilities. Future milestones
currently stop for a reviewed port; the recipe generator supports milestone
155 only. Security updates in that milestone still require a rebuild/test.

## Desktop automatic installation

Prerequisites: an installed `chromium-glass` package, Python, pacman, GitHub CLI
with `gh attestation verify`, systemd, and access to public GitHub/Sigstore.
No personal GitHub token is needed for downloaded public attestation bundles.

```bash
# Read-only release check; no installation.
python3 tools/stable_update.py

# Enable automatic installation of approved stable releases.
sudo bash tools/install_updater.sh

systemctl status chromium-glass-update.timer
journalctl -u chromium-glass-update.service
```

The root-owned updater checks hourly and shortly after boot. It accepts only
non-prerelease packages from `Walenhill/chromium-glass-wayland` with a signed
approval from `release.yml` on `main`, an authenticated build provenance,
matching SHA-256, package identity, and a strictly newer package version.
Unsigned/malformed releases and network/verification errors fail closed.

It does not compile Chromium, modify compositor rules, upgrade the OS, change
pacman's signature policy, or force-close/restart the browser. Installation is
deferred while a Chromium process or pacman transaction is detected, including
a second check after downloads. This is a best-effort process check, not a
global lock preventing the user from starting Chromium at the same instant.
Missing/outdated system dependencies stop pacman normally; resolve these as
part of your regular Arch maintenance rather than permitting partial upgrades.

There are **no verified stable GitHub Releases yet**. Enabling the timer before
the first approved release therefore leaves the installed working build alone.
Prepared files alone do not mean the host timer is enabled; verify its status.
The scheduled GitHub workflows activate only after merge to the default branch.
Opening candidate PRs with `GITHUB_TOKEN` also requires the repository Actions
setting "Allow GitHub Actions to create and approve pull requests". The workflow
only creates update PRs: it never approves or merges them. A disabled setting
causes candidate publication to fail rather than installing an unchecked build.

## Rollback and disabling

Downloaded approved packages remain in `/var/cache/chromium-glass`. A package
installed before enabling this updater is not automatically backed up: keep its
original package and a backup of the Chromium profile before the first upgrade.
Downgrading the browser does not undo profile-format migrations.

```bash
sudo systemctl disable --now chromium-glass-update.timer
# With the browser closed, install the explicit known-good package you kept:
sudo pacman -U /absolute/path/to/known-good-chromium-glass.pkg.tar.zst
```

Source-only diagnosis commands:

```bash
python3 -m unittest discover -s tests -v
python3 tools/validate_metadata.py
python3 tools/check_compatibility.py 155.0.8059.39 --report compatibility.json
python3 tools/check_packaging.py /path/to/chromium-155.0.8059.39-lite.tar.xz
```
