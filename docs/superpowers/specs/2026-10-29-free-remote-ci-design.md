# Remote-only Chromium Stable and resumable free CI
Date: 2026-10-29. User selected the free GitHub Actions approach and delegated technical details.

## Intent
Build the current Linux Stable Chromium with the existing Glass appearance, exclusively on standard GitHub-hosted runners. No local Chromium downloads, builds, dependencies, installation, system configuration, or paid services.

## Chosen approach and alternatives
Use bounded build slices, saving a compressed complete Ninja output checkpoint before the six-hour hosted-job limit, and restore it on the next job. A compiler cache alone can evict older objects and does not retain Ninja's dependency graph; the full output checkpoint is the implementer's choice to preserve forward progress.
A larger remote server was considered but rejected: the user chose the free option. Raising the hosted job limit is not available.

## Requirements
- Resolve official Linux Stable; initially 156.0.8078.73. Review/apply all Glass hunks, not merely the version number.
- Keep Chromium matching LLVM/Rust/Crubit, CFI, ThinLTO, PGO, and codecs; do not trade protections or appearance for build time.
- Run tests and source preparation only on GitHub. Edit the existing candidate branch through the GitHub API; do not create a local checkout/worktree.
- Stable source/build/package inputs and source timestamps across slices; reject incompatible checkpoints.
- Archive only out/Release, validate archive members and a SHA-256 digest before restore, and enforce an 8 GiB checkpoint ceiling within the existing default cache quota. Never enable paid cache storage or larger runners.
- Build deadline 4h30m, controlled interruption, reserve time to save. Full job ceiling remains 6h.
- No automatic retry on compiler/preparation/test failure. Maximum six automatic slices. Detect unchanged progress and stop rather than looping.
- A checkpoint is not a successful binary: attestation, package/runtime smoke and visual approval remain separate gates.
- Do not merge or release/install an unverified candidate.

## Acceptance
Remote regression tests include success, build error, deadline checkpoint, retry bound, stalled progress, archive traversal/link rejection, corruption/identity rejection, and a real small Ninja checkpoint/resume probe. Official source checks must pass for the target. Full Chromium compilation remains pending until a real package, version/library/headless evidence and build attestation exist.
