# Free remote Chromium Stable CI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a current Chromium Glass candidate remotely without losing progress to hosted-job timeouts.
**Architecture:** Stable Arch build inputs, bounded compiler process groups, compressed Ninja output checkpoints in the existing GitHub cache, and bounded continuation.
**Tech Stack:** GitHub Actions, Arch container, Python standard library, Ninja, zstd.
**Spec:** docs/superpowers/specs/2026-10-29-free-remote-ci-design.md

## Global Constraints
- GitHub-hosted standard runners only; no local builds/downloads/packages/system changes and no paid resources.
- Keep security/optimization flags and require actual binary/visual validation before release.
- 4h30m build slices; 6h job ceiling; at most six automatic slices; checkpoint maximum 8 GiB.
- Existing candidate PR only; no main merge or installation.

## Review Focus
- Corrupt or path-escaping archive must fail before modifying source.
- Real compiler errors must not become retryable checkpoints.
- Package or toolchain mismatch must not reuse stale objects.
- An unchanged checkpoint must stop continuation.
- A checkpoint-only run must not qualify for release approval.

### Task 1: Resumable build policy
**Files:** Create tools/ci_checkpoint.py, tests/test_ci_checkpoint.py; modify build workflow and container build driver.
**Interfaces:** classify(returncode, timed_out, attempt, previous_progress, progress) -> state; fingerprint(inputs) -> SHA256; save/restore(output, checkpoint, identity); supervise(command, seconds).
- [ ] Write behavior tests and run them on GitHub: expected RED (missing policy).
- [ ] Implement controlled process-group timeout, checkpoint validation, identity and progress guards.
- [ ] Run all unit tests plus a real small Ninja resume probe on GitHub: expected GREEN.
- [ ] Integrate restore/save/continuation and validate workflow syntax remotely.
- [ ] Commit and ledger evidence.

### Task 2: Current upstream candidate
**Files:** tools/update_upstream.py; generated PKGBUILD/.SRCINFO/upstream.json; reviewed Glass patch if required; remote preparation workflow.
**Interfaces:** official Stable -> pinned reviewed recipe and source hashes -> source preparation report consumed by build.
- [ ] Add target milestone/recipe behavior tests; observe RED remotely.
- [ ] Port generator and Glass hunks to official Stable using pinned Arch inputs.
- [ ] Download/hash archive and run complete prepare on GitHub only.
- [ ] Run metadata, all tests, patch application and GN generation checks remotely: expected GREEN.
- [ ] Commit generated candidate files and ledger evidence.

### Task 3: Integrated remote verification and handoff
**Files:** docs/UPDATES.md, compatibility evidence, remote execution ledger; release gate changes if needed.
**Interfaces:** candidate workflow -> completed package and provenance OR explicit pending/failure.
- [ ] Run short forced checkpoint and real Ninja restore probe before the long Chromium build.
- [ ] Review the complete branch independently; fix important findings with RED/GREEN tests.
- [ ] Start full remote candidate build only after gates pass.
- [ ] Report exact run URL and distinguish CI/source success from unfinished binary/visual checks.
