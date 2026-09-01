#!/bin/bash
set -euo pipefail

# Rebuild caches in the target rootfs after all desktop files and themes exist.
# Missing optional tools are intentionally ignored for minimal profiles.
if command -v update-desktop-database >/dev/null 2>&1 && [ -d /usr/share/applications ]; then
    update-desktop-database /usr/share/applications >/dev/null 2>&1 || true
fi

if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    for theme in /usr/share/icons/*; do
        [ -d "$theme" ] || continue
        [ -f "$theme/index.theme" ] || continue
        gtk-update-icon-cache -f -t "$theme" >/dev/null 2>&1 || true
    done
fi

if command -v fc-cache >/dev/null 2>&1; then
    fc-cache -f >/dev/null 2>&1 || true
fi
