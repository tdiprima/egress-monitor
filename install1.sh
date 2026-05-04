#!/bin/bash

YELLOW='\033[0;33m'
NC='\033[0m'

rm -rf egress-monitor

# Uninstall the scripts
sudo rm /usr/local/bin/outbound_audit.py
sudo rm /usr/local/bin/outbound_audit_cron.sh

git clone https://github.com/tdiprima/egress-monitor.git
cd egress-monitor

# Enable firewall logging
sudo bash src/setup_outbound_logging.sh

# Verify it's working
sudo tail -f /var/log/outbound-connections.log

# Wait 1 to 2 days for log data to accumulate
comeback_date=$(date -d "+2 days" "+%Y-%m-%d")
echo -e "${YELLOW}Come back on ${comeback_date} to create baseline.${NC}"
