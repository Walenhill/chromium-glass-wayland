# Chromium Glass for Wayland

An Arch Linux package for Chromium with native translucent browser chrome.
The patch enables Chromium's existing `GlassFrame` path on Linux and assigns
semi-transparent colors to the tab strip, toolbar, omnibox, panels, and menus
so a Wayland compositor can blur the content behind the window.

The package launches Chromium with:

```text
--ozone-platform=wayland
--enable-features=GlassFrame
--class=chromium-glass
```

## Build and install

Building Chromium takes substantial time, memory, and disk space.

```bash
git clone https://github.com/Walenhill/chromium-glass-wayland.git
cd chromium-glass-wayland
makepkg -s
sudo pacman -U chromium-glass-*.pkg.tar.zst
```

The package conflicts with and provides `chromium`, so pacman will offer to
replace the regular Arch Chromium package. It keeps Chromium's standard profile
path and desktop-file identity.

## Hyprland

Chromium reports the Wayland app-id `chromium-glass`. A minimal Hyprland rule is:

```ini
windowrule {
    name = chromium-glass
    match:class = ^(chromium-glass)$
    opacity = 0.999 0.999
    no_blur = false
}
```

Blur also needs to be enabled globally. On configurations where the window is
transparent but remains sharp, disabling blur `xray` and
`new_optimizations` may be required:

```ini
decoration {
    blur {
        enabled = true
        xray = false
        new_optimizations = false
    }
}
```

The exact rule syntax can vary between Hyprland configuration frameworks.

## Repository layout

- `chromium-glass-wayland.patch` is the transparency patch maintained here.
- Arch build-fix patches are downloaded from a pinned official packaging tag
  and verified with SHA-256 instead of being duplicated in this repository.
- `PKGBUILD` and `.SRCINFO` describe the reproducible Arch package.

## Notes

- This is an unofficial Chromium build.
- Rebuild promptly when Arch updates Chromium, especially for security fixes.
- The package is currently based on Chromium `150.0.7871.186`.
- The packaging base comes from the official Arch Linux Chromium package.
