# Chromium 156 candidate — remote verification, 2026-10-29

Target Linux Stable: **156.0.8078.73-1**.
The installed maintainer browser is not replaced by this CI work.

## Evidence

- Remote-only guards prevent running the container build driver or full source
  preparation as a normal desktop command.
- All **43 updater/source/CI tests** pass on GitHub, including controlled timeout,
  actual errors, retry/stall bounds, checksum/identity/size rejection, archive
  traversal/link rejection, real hardlinked files, stable cache keys, and source
  mirror failover.
- Final cross-run probe **40781639673 -> 40781746368** restored two completed Ninja
  outputs and built the third without changing the first output's timestamp.
  The cache was verified through GitHub's API before automatic continuation.
- Chromium 156 renamed a menu background layer. The Glass patch retains the
  upstream name; a regression test applies the constructor hunk with both
  upstream names. Glass colors, alpha and feature behavior were not retuned.
- Source, dependency preparation and GN passed in run **40778207204**:
  official archive SHA-256 matches pinned Arch inputs; 36,218 GN targets were
  generated from 5,069 files. Subsequent desktop-entry packaging changes have
  a real rendered-overlay regression test. Full compilation, package smoke, native Wayland behavior,
  multi-window visual checks and performance are separate pending gates.

## Not a stable release

A checkpoint is not a package. The real Chromium build is not successful until
the remote run produces its package, version/library/headless evidence and
attestation. Native Wayland/GPU/blur checks and explicit visual approval remain
required before publication or installation. No desktop compiler, browser
installation, local source checkout or system configuration change is part of
this work.
