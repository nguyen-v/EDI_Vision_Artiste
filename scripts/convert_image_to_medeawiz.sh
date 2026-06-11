#!/usr/bin/env bash
# Convert a still image to a MedeaWiz-ready MP4 for Vision Artiste SD cards.
# Cross-platform entry point: scripts/convert_image_to_medeawiz.py
# (Use `python scripts/convert_image_to_medeawiz.py` on Windows.)

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "${SCRIPT_DIR}/convert_image_to_medeawiz.py" "$@"
