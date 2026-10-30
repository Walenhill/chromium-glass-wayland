#!/usr/bin/env bash
set -euo pipefail
if (( EUID != 0 )); then
  printf 'Run with: sudo bash tools/install_updater.sh\n' >&2
  exit 1
fi
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
for dependency in python3 gh pacman vercmp systemctl; do
  command -v "$dependency" >/dev/null || { printf 'Missing dependency: %s\n' "$dependency" >&2; exit 1; }
done
gh attestation verify --help >/dev/null
install -Dm644 "$root/tools/stable_update.py" /usr/local/lib/chromium-glass/stable_update.py
install -Dm644 "$root/systemd/chromium-glass-update.service" /etc/systemd/system/chromium-glass-update.service
install -Dm644 "$root/systemd/chromium-glass-update.timer" /etc/systemd/system/chromium-glass-update.timer
systemctl daemon-reload
systemctl enable --now chromium-glass-update.timer
printf 'Approved stable auto-updates enabled. OS upgrades and running browser restarts are not performed.\n'
