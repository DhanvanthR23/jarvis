#!/usr/bin/env bash
# G12: Sets up the external audit anchor with immutable append-only attributes.
# Must be run as root.

set -e

ANCHOR_DIR="/var/log/jarvis"
ANCHOR_FILE="${ANCHOR_DIR}/anchor.log"

if [ "$EUID" -ne 0 ]; then
  echo "Please run as root to configure chattr +a on the audit anchor."
  exit 1
fi

mkdir -p "${ANCHOR_DIR}"
touch "${ANCHOR_FILE}"

# Make it append-only at the filesystem level
chattr +a "${ANCHOR_FILE}"

echo "Audit anchor created and set to append-only at: ${ANCHOR_FILE}"
echo "Verify with: lsattr ${ANCHOR_FILE}"
