#!/usr/bin/env bash
# Rebuild the household views and copy them to the NAS (LAN only, never GitHub).
#
#   ./scripts/deploy-household.sh
#
# Steps: refresh the house's household export, build private/, rsync it to the NAS.
# Files are made web-readable here first (folders 755, files 644); rsync -a then keeps
# those permissions on the NAS, so Nginx can always read them. (macOS ships openrsync,
# which doesn't support --chmod, so permissions are set before copying instead.)
set -euo pipefail

SITE="$(cd "$(dirname "$0")/.." && pwd)"
HOUSE="$SITE/../house"
DEST="truenas_admin@truenas.local:/mnt/tank/apps/house-web/"

echo "1/3  Household export"
(cd "$HOUSE" && uv run exports/export.py household)

echo "2/3  Household views"
(cd "$SITE" && uv run build.py --household)

echo "3/3  Copy to the NAS"
chmod -R u=rwX,go=rX "$SITE/private"
rsync -av --delete "$SITE/private/" "$DEST"

echo "Done: http://truenas.local:8088"
