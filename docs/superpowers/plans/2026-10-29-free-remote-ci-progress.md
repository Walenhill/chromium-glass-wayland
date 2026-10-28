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

Task 1: complete — GREEN run 40774390681 (34 tests); cross-run probe 40774381220 -> 40774478915 restored progress 2 -> 3 without rebuilding the first output. Exact remote cache visibility gate passed; no Chromium compilation was used for this probe.
Task 2: RED run 40774787950 exposed the milestone guard and missing remote-only preparation guard.

Task 2: reviewed 156 renderer and remote-only guard pass in 40775631559 (37 tests). Source probe 40775624939 rejected one menu constructor hunk because upstream renamed a layer; context narrowed without changing Glass behavior. Added hardlink checkpoint regression before enabling long builds.

Task 2: complete — run 40778207204 verified official 156.0.8078.73 archive SHA256 cfdf8def1207b81af1231e5170bf849896cd353e72220ca05d93432e31551d59 against Arch 8ec86828d5fad19ff66ec7fcaebfe223c9252838; all Glass hunks and full package preparation succeeded; bundled GN produced 36218 targets / 5069 files. Generated candidate commit a828323839a1cf89b8f943eedd41796184fcbeb0.
Task 2: hardlinks regression RED 40776083166 -> GREEN unit suite 40777108339; mirrored source fetch RED 40778036397 -> GREEN 40778213237. All 40 tests pass.
Ruling: Preserve both upstream menu-layer names using balanced two-line context, rather than changing the layer's name or Glass behavior. Cost: strict application and regression checks remain required for future ports.
Task 3: in progress — independent whole-branch review and final remote verification pending; full Chromium compile not yet started.
