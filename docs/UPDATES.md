# Updates and release validation

Chromium Glass is experimental. Source compatibility, a successful compile,
and actual compositor blur are three different checks; none substitutes for
the others. A candidate is never automatically considered stable.

## Maintainer pipeline

All source archives, package dependencies, GN generation, tests and Chromium
compilation run on **standard GitHub-hosted ubuntu-24.04 runners**, not the
maintainer's desktop. Larger runners, external build servers and paid cache
capacity are not enabled.

1. Dispatch `build.yml` with `prepare=true` to resolve official Linux Stable,
   verify its complete archive against the pinned Arch recipe when versions
   match, port/validate every Glass hunk with zero fuzz, prepare all build
   dependencies, and generate GN. Only validated PKGBUILD/.SRCINFO/upstream
   metadata are committed to the candidate branch. This is not a binary build.
2. Dispatch `probe=true` for a short real Ninja build spanning two GitHub runs.
   It must restore the first run's outputs and finish without recompiling the
   completed first file before a new checkpoint implementation is trusted.
3. Dispatch `compile=true` for the real build. Each slice has a controlled
   **4h30m compilation deadline**, below GitHub's six-hour job limit. It saves
   compressed `out/Release`, including Ninja's dependency/log state, explicitly
   before the job ends. The next run must restore that exact checkpoint key, identity and progress
   before preparing sources; an evicted/missing/older checkpoint fails instead
   of silently restarting. It then continues automatically.
4. The cache key is frozen before generated files appear. Actual package
   inventory, pinned source/recipe/tool inputs and a stable source epoch bind
   the checkpoint identity. The Arch container digest and repository snapshot
   are pinned; mismatches, corrupt archives, traversal/links, oversized
   checkpoints, no progress, or actual compiler errors stop the chain. Persisted Ninja failure evidence
   overrides a deadline, including an error logged while other edges drain.
   Hardlinked outputs are archived as regular files. The checkpoint ceiling is
   **8 GiB compressed / 64 GiB uncompressed**; the existing cache quota is not
   increased. Automatic continuation requires a visible exact branch cache and
   stops after at most **six slices**. This is not an infinite retry loop.
5. Only a complete package with version/library/headless checks gets a build
   attestation. A successful checkpoint-only workflow is **not** a successful
   browser build and cannot pass release promotion. Cache expiry/eviction or a
   source/ABI change can still require rebuilding; the tiny probe is evidence
   for the mechanism, not proof of full Chromium performance or compatibility.
6. Check that exact candidate in native Wayland with an isolated test profile:
   toolbar and tabs, omnibox/history, main/context menus, bubbles/extensions,
   light/dark themes, rounded edges and **a second new window**. Check resource
   usage with menus open and closed.
7. Merge only tested inputs to `main`. Run `release.yml` from main with the
   successful complete build run ID and `visual_approved=true`. It verifies
   origin, unchanged build inputs, attestation and smoke evidence before
   publishing the package and signed approval manifest.

The scheduled `update.yml` pipeline is inactive until merged to the default
branch. It does not make untested builds stable. Recipe ports currently cover
reviewed milestones **155 and 156**; an unknown milestone fails closed for
review. A maintainer approval is not an automated visual test or security audit.
Artifact availability is limited by configured retention; no stable release
exists merely because candidate inputs or source checks passed.

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
python3 tools/check_compatibility.py 156.0.8078.73 --report compatibility.json
python3 tools/check_packaging.py /path/to/chromium-156.0.8078.73-lite.tar.xz
```
