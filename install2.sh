#!/bin/bash

YELLOW='\033[0;33m'
NC='\033[0m'

# Create a baseline
sudo python3 src/outbound_audit.py --save-baseline /etc/outbound-baseline.json

# Install the scripts
sudo cp src/outbound_audit.py /usr/local/bin/
sudo cp src/outbound_audit_cron.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/outbound_audit_cron.sh

# Schedule the nightly job
echo -e "${YELLOW}sudo crontab -e${NC}"
echo -e "${YELLOW}0 0 * * * EMAIL=you@example.com /usr/local/bin/outbound_audit_cron.sh${NC}"
