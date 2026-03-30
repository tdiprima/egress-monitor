# egress-monitor

Monitor all outbound network connections on a Rocky Linux server and get email alerts when something unexpected phones home — especially Ollama.

## Why This Exists

You're running an LLM inference server (Ollama) and you want to know if it ever makes outbound connections it shouldn't. More broadly, you want a daily record of everything your server calls out to, and an alert when something new shows up.

## How It Works

1. Firewalld logs every outbound TCP/UDP connection to `/var/log/outbound-connections.log`
2. You let logs accumulate for a day or two, then snapshot a **baseline** (what "normal" looks like)
3. A cron job runs every night, compares that day's traffic against your baseline, and emails you only if something new or suspicious appeared

No alerts on quiet nights. Alerts when Ollama dials out, a new IP appears, or a blocked connection is attempted.

## Full Setup: Do This Once

### Step 1 — Enable firewall logging

```bash
sudo bash src/setup_outbound_logging.sh
```

This configures firewalld and rsyslog to write all outbound connections to `/var/log/outbound-connections.log`. It also sets up daily log rotation.

Verify it's working:

```bash
sudo tail -f /var/log/outbound-connections.log
```

You should see lines like:

```
Mar 20 14:23:01 server1 kernel: OUTBOUND_CONN_TCP: IN= OUT=eth0 SRC=10.0.0.5 DST=104.18.32.7 DPT=443 ...
```

### Step 2 — Wait 1 to 2 days

**Do not skip this.** Let your server run normally so the log fills up with real traffic. The baseline you create in the next step is only useful if it reflects actual normal activity.

### Step 3 — Create a baseline

```bash
sudo python3 src/outbound_audit.py --save-baseline /etc/outbound-baseline.json
```

This snapshots every known destination IP and port. Future audits flag anything not in this file.

### Step 4 — Install the scripts

```bash
sudo cp src/outbound_audit.py /usr/local/bin/
sudo cp src/outbound_audit_cron.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/outbound_audit_cron.sh
```

### Step 5 — Set your alert email

```bash
export EMAIL="you@example.com"
```

Add this to `/etc/environment` or your cron environment so it persists across reboots.

### Step 6 — Schedule the nightly job

```bash
sudo crontab -e
```

Add this line:

```
0 0 * * * EMAIL=you@example.com /usr/local/bin/outbound_audit_cron.sh
```

This runs the audit every night at midnight, checks yesterday's traffic against your baseline, writes a report to `/var/log/outbound-audit-reports/`, and emails you only if something is wrong.

## That's It

After setup, you don't have to do anything. Check your inbox. If Ollama phones home, you'll know.

## Running It Manually

```bash
# Full report for today
sudo python3 /usr/local/bin/outbound_audit.py

# Only show Ollama activity
sudo python3 /usr/local/bin/outbound_audit.py --ollama-only

# Analyze a specific time window
sudo python3 /usr/local/bin/outbound_audit.py --after "2025-03-20 08:00" --before "2025-03-20 17:00"

# Compare against your baseline
sudo python3 /usr/local/bin/outbound_audit.py --baseline /etc/outbound-baseline.json
```

## What the Alerts Mean

| Severity | What It Means |
|----------|---------------|
| CRITICAL | Ollama made an outbound connection |
| HIGH | A new destination IP appeared, or a connection was blocked |
| MEDIUM | Known destination but a new port |
| LOW | Informational only |

## Requirements

- Rocky Linux (or any RHEL-compatible distro)
- `firewalld` running
- `rsyslog` running
- Python 3.9+
- `mailx` for email alerts — on RHEL/Rocky: `sudo dnf install s-nail -y`

<!-- `mail`, `mailx`, or `sendmail` for email alerts -->

<br>
