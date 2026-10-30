# Chromium 156 WebUI omnibox blur candidate

The installed 156.0.8078.73-1 candidate passed local launch and the user's
frame/menu checks, but WebUI suggestions showed sharp page content through
their translucent background.

The existing native popup patch touches OmniboxPopupViewViews. Chromium 156's
OmniboxPopupPresenterBase creates a different Aura child and shares
RoundedOmniboxResultsFrame, so native Wayland popup blur does not cover that
path.

The -2 candidate adds a backdrop filter only to the classic WebUI results
content layer on Linux when GlassFrame is enabled. Existing layout positions
that layer below the location-bar cutout; bottom corners stay rounded.
Legacy Views popups, WebUI-owned shadows, non-Linux platforms and GlassFrame
disabled are untouched. Frame, toolbar, menus, tint recipes and compositor
configuration are unchanged.

## Evidence and limits

- Failing regression: Actions 41011000598. Existing constructor leaves the
  results without a filter; its extracted setup fails the layer contract.
- The regression compiles and executes the actual patched constructor setup
  against a recording layer boundary for all 16 platform/feature/content/shadow
  combinations. It is not a rendered-pixel or full Chromium unit test.
- CI additionally applies every Glass hunk to pinned official Chromium source
  with zero fuzz. Full compilation and a native visual check are still required.
- Build only on free GitHub-hosted runners. No local source tree or compilation.
- Keep the installed -1 and preserved 150 rollback package; do not install this
  candidate automatically or merge/publish it before visual approval.
