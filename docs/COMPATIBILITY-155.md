# Chromium 155 candidate checks — 2026-10-08

Target: Linux Stable **155.0.8059.39**, recipe release `-1`.
Pinned Arch packaging: `e01d89c346c9c67fda9b444b3355b2eda85a4f56`
(the Arch recipe itself is for 153.0.8010.52).

Confirmed locally:

- Official release archive SHA-256 matches `upstream.json` and `.SRCINFO`.
- All 19 Glass hunks apply with zero fuzz to 9 upstream source files.
- Required native omnibox popup integration is present after patching. The old
  patch contained malformed blank context lines; GNU patch could miss the final
  popup hunk, leaving a recipe which looked patched but lacked `TYPE_MENU` and
  `DesktopNativeWidgetAura`. The strict parser now rejects that failure.
- All 14 patches actually used by the recipe apply to 28 release-archive files.
- Full `makepkg --nobuild --nodeps` preparation succeeds, including exact
  DevTools esbuild and Chromium's matching LLVM/Rust/Crubit toolchain.
- Bundled GN **2562 (cfcd774b98f3)** generates 35,780 targets from 5,045 files.
  System GN 0.2385 is incompatible with this source. The recipe therefore uses
  the bundled GN rather than disabling new GN features/header checks.
- 17 updater/source regression tests, workflow syntax checks, systemd unit
  verification and packaging metadata checks pass.
- The live updater check correctly keeps the installed browser: the repository
  has no verified stable GitHub Release yet.

Not yet confirmed: full compilation/linking, packaged binary runtime, native
Wayland blur, GPU/driver compatibility, multi-window visual behavior,
performance, and a complete signed-release-to-install transaction. The current
local interface compilation is a diagnostic build, not approval evidence.

The installed known-working version remains **150.0.7871.186-11**. Do not call
this Chromium 155 candidate stable or enable automatic publication on the basis
of the source/metadata checks alone.
