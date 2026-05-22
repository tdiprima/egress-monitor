#!/usr/bin/env bash
# =============================================================================
# install1.sh — Fresh install from a clean clone (Step 1 of 2)
#
# This script clones the repository into a NEW directory and runs the firewall
# logging setup. Run this on a host that does NOT already have egress-monitor.
#
# If you are UPDATING an existing install, use install2.sh instead.
#
# Usage:
#   cd /tmp
#   bash install1.sh
# =============================================================================

set -euo pipefail

YELLOW='\033[0;33m'
NC='\033[0m'

TARGET_DIR="egress-monitor"

if [[ -d "${TARGET_DIR}" ]]; then
    echo "ERROR: Directory '${TARGET_DIR}' already exists in $(pwd)."
    echo "       Move to a clean working directory, or use install2.sh to update an existing install."
    exit 1
fi

git clone https://github.com/tdiprima/egress-monitor.git "${TARGET_DIR}"
cd "${TARGET_DIR}"

# Enable firewall logging
sudo bash src/setup_outbound_logging.sh

# Let logs accumulate for a day or two before creating the baseline
comeback_date=$(date --date="+2 days" "+%Y-%m-%d")
echo -e "${YELLOW}Come back on ${comeback_date} to create your baseline (see README.md Step 3).${NC}"
