#!/bin/bash

# 1. Copy the scripts into place
sudo cp outbound_audit.py /usr/local/bin/outbound_audit.py
sudo cp outbound_audit_cron.sh /usr/local/bin/outbound_audit_cron.sh
sudo chmod +x /usr/local/bin/outbound_audit_cron.sh

# 2. Re-run the updated firewall setup (skips localhost now)
sudo bash setup_outbound_logging.sh

# 3. Let logs accumulate for a day or two, then snapshot the baseline
sudo /usr/bin/python3 /usr/local/bin/outbound_audit.py --save-baseline /etc/outbound-baseline.json

# 4. Install the cron job
sudo crontab -e
# Add this line:
# 0 0 * * * /usr/local/bin/outbound_audit_cron.sh
