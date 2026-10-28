# SDD ledger — plan: docs/superpowers/plans/2026-10-29-free-remote-ci.md
Spec: docs/superpowers/specs/2026-10-29-free-remote-ci-design.md
Base: e71b68cbdbf014ad7e747251cdb3b6cd34638778

Ruling: Execute natively without further design questions — the user selected the offered free approach and said to do it; no paid/external runner may be enabled.
Ruling: Remote branch/API replaces local worktree, scratch scripts and on-host test runs — explicit no-PC constraint takes precedence over local skill bookkeeping helpers. Cost: remote CI latency and API commits.
Ruling: Save complete Ninja outputs rather than rely solely on a bounded compiler cache — prevents cache eviction from resetting progress. Cost: checkpoint size is limited to 8 GiB; exceeding it is an explicit failure, not permission to buy storage.
Pre-flight: Task 1 produces state/identity consumed by Task 2's driver and Task 3's publication gate; only state complete may attest/publish. Source hash + package inventory bind restored outputs.

Task 1: core RED confirmed in run 40772179454 (15 missing-policy failures); GREEN confirmed in run 40772617231 (32 tests, including real Ninja resume).
Ruling: A pinned container digest and Arch snapshot 2026/10/28 freeze dependency inputs across slices; actual pacman inventory additionally binds checkpoint identity. Cost: snapshot refresh needs a new identity/rebuild.

Task 1: cross-run probe 40773639917/40773760134 exposed a changing cache key caused by generated __pycache__ files. Regression run 40774135230 confirms two RED tests for stable key inputs and exact remote cache visibility.
