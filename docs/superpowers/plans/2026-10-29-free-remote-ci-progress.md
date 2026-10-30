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

Final review: fresh reviewer examined e71b68c..73dbbcd. Important: timeout could hide a previously logged Ninja failure; continuation did not require the exact cache at the consumer. Minor regraded Important: duplicate StartupWMClass can break real launcher/window association. All three enter the single RED/GREEN fix pass.
Final: Ruling: Regrade duplicate desktop keys as Important — a reasonable user expects correct launcher association, not conflicting keys. Cost if left: platform-dependent wrong grouping/launch association.

Final: fixed deadline masking — real parallel Ninja error/drain test RED 40781095814 -> GREEN 40781643713, full suite 43/43. Persisted child output is scanned before checkpoint classification.
Final: fixed lost-checkpoint continuation — producer key/identity/progress are passed and enforced before source preparation and again in the container; missing/older checkpoint regression RED -> GREEN in the same suite. Exact cross-run resume passed 40781639673 -> 40781746368.
Final: fixed duplicate desktop startup class — real rendered sed overlay on existing/missing/duplicate fields RED -> GREEN, full suite 43/43.
Final: Ruling: Actual Chromium compile/link, checkpoint size and runner resource sufficiency remain empirical acceptance gates — a miniature probe cannot prove them. Cost: a full run may stop at a resource/size/stall bound; no paid fallback or endless retry is authorized.
Final: Ruling: Native Wayland/GPU/second-window/installation checks remain pending and cannot run on the desktop without later authorization. Cost: appearance/runtime compatibility is unverified; no stable approval.
Final: Ruling: Preserving CFI/ThinLTO/PGO recipe flags is not a security audit. Cost: the experimental build carries no vulnerability-free guarantee.
Final: Ruling: Scheduled-update activation, main merge, stable release and updater installation are deferred until complete binary/visual validation. Cost: automatic desktop updates are not active yet.
Final review: all reviewed Important issues (including regraded desktop association) fixed with RED/GREEN evidence; no deferred Minor findings. No second reviewer dispatched.
Task 3: CI harness and source port verified. The full remote Chromium build is the next asynchronous acceptance gate. Keep this candidate head frozen during the chain; record live run URLs in PR #2 rather than changing source mid-build.
