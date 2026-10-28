# Project status

> **Experimental project — remote update in progress**

Chromium Glass is an unofficial, experimental Chromium modification. It is a
personal research project rather than a production-ready browser distribution,
and it should not be treated as an official Chromium build.

Development resumed on 29 October 2026 after the earlier temporary pause.
A Chromium 156 candidate is being prepared through free GitHub-hosted CI.
Source/recipe/GN checks are not a completed browser build or visual approval.

## Published version

The latest stable version currently published in this repository is
`150.0.7871.186-11`.

## Known limitations and problems

- **Security updates are not automatic.** The published build can lag behind
  upstream Chromium and therefore may miss current security fixes. Do not
  assume it has the same security status as the current official Arch Chromium
  package.
- **A current verified binary is not available yet.** Maintained compilation
  now runs on GitHub, using bounded checkpoints rather than the desktop.
  The new candidate still requires full compilation and runtime/visual checks.
- **The patch is version-sensitive.** Chromium UI and compositor internals
  change frequently, so every upstream update requires porting, rebuilding, and
  visual testing. A newer Chromium port is currently unfinished and is not part
  of the published stable version.
- **Blur is compositor-dependent.** Chromium provides translucent surfaces,
  while the actual background blur comes from the Wayland compositor. Hyprland
  needs a manual `chromium-glass` window rule and compatible blur settings.
  Other compositors have not been validated.
- **Blur behavior can be configuration-sensitive.** Hyprland options such as
  `xray`, `new_optimizations`, opacity rules, themes, and compositor updates can
  make a surface transparent without producing the intended blur.
- **Some UI surfaces can look inconsistent.** Menus, bubbles, omnibox results,
  shadows, rounded edges, and newly introduced Chromium panels may use separate
  layers. Depending on the theme and Chromium state, their tint or blur can
  differ from the main browser chrome.
- **Platform support is narrow.** The package is intended for Arch Linux on
  x86_64 with native Wayland, and has primarily been tested on Hyprland.
- **Installation replaces the regular Chromium package.** `chromium-glass`
  provides and conflicts with `chromium` while retaining Chromium's normal
  profile identity. Back up important browser data and keep a rollback path.
- **Testing is currently personal and limited.** There is no comprehensive
  automated visual, compositor, upgrade, or multi-GPU test suite.

While a current verified Glass release is unavailable, the official Arch Chromium package is the
safer choice for users who prioritize prompt security updates and predictable
maintenance over the experimental glass appearance.
