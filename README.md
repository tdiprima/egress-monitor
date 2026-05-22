# egress-monitor

Monitor all outbound network connections on a Rocky Linux server and get email alerts when something unexpected phones home — especially Ollama.

## When You Can't Afford to Not Know

You're running an LLM inference server. Ollama serves local models and is not supposed to make outbound connections. But how would you know if it did? Kernel logs fill with noise. There's no alerting out of the box. And the gap between "I assume this is fine" and "it has been calling home for three weeks" is exactly where incidents live.

The same problem applies to any long-running server process. New destination IPs appear. Unusual ports show up. Something gets blocked that wasn't blocked yesterday. Without a continuous record and a diff against known-good behavior, you find out about these things after the fact, if at all.

## How It Works

egress-monitor hooks into firewalld's direct rules to log every new outbound TCP and UDP connection to a dedicated file. It gives Ollama's own process-level traffic a separate log prefix so it can never be confused with client traffic calling *into* Ollama. A Python audit engine parses those logs, computes a summary, and runs anomaly detection: unusual ports, blocked attempts, and — most critically — any connection the Ollama process itself initiated.

You let logs accumulate for a day or two, snapshot a baseline of what normal looks like, and then a cron job runs every night. It compares yesterday's traffic against that baseline, writes a dated report to disk, and emails you only if something changed. Quiet nights produce no email. Ollama phoning home produces a CRITICAL alert before you've had your morning coffee.

Detection is handled by pure functions that return structured data — anomaly type, severity, destination, count, and a human-readable detail string — keeping the audit logic fully testable and independent from rendering.

## Example Alert

On a clean night you get nothing. On a night where Ollama made an outbound connection, the subject line reads:

```
[CRITICAL] inference-01: Ollama made outbound connections!
```

The body includes the destination IP, port, connection count, and first/last seen timestamps, followed by the full audit report and an investigation command you can paste directly into a terminal.

Running the audit manually produces a color terminal report:

```
══════════════════════════════════════════════════════════════════════════════
  OLLAMA OUTBOUND ACTIVITY
══════════════════════════════════════════════════════════════════════════════

  ⚠  OLLAMA MADE 3 OUTBOUND CONNECTION(S)

  Destination              Port       Count  First Seen   Last Seen
  ───────────────────────────────────────────────────────────────────────
  fastly.net (151.101.1.1) 443/HTTPS  3      03-20 02:14  03-20 02:14

  Action items:
  • Investigate what Ollama is reaching out to
  • Check if OLLAMA_HOST or model pull configs are set
```

The anomaly section surfaces severity-ranked findings across all connection types:

```
══════════════════════════════════════════════════════════════════════════════
  ANOMALY DETECTION
══════════════════════════════════════════════════════════════════════════════

  Found 2 anomalies:

  Severity  Type             Destination        Port   Count  Detail
  ──────────────────────────────────────────────────────────────────────────
  CRITICAL  OLLAMA_OUTBOUND  151.101.1.1        —      3      Ollama process initiated 3 outbound connection(s)
  HIGH      NEW_DESTINATION  203.0.113.42       —      1      Destination NOT in baseline — never seen before
```

## Full Setup

### Step 1 — Enable firewall logging

```bash
sudo bash src/setup_outbound_logging.sh
```

This configures firewalld direct rules and rsyslog to write all new outbound connections to `/var/log/outbound-connections.log`, with daily log rotation keeping 30 days of history.

Verify it's capturing traffic:

```bash
sudo tail -f /var/log/outbound-connections.log
curl -s https://example.com > /dev/null
# A new line should appear immediately
```

### Step 2 — Wait 1 to 2 days

Let your server run normally so the log fills up with real traffic. The baseline you create next is only as useful as the activity it captures. Do not skip this step.

### Step 3 — Snapshot a baseline

```bash
sudo python3 src/outbound_audit.py --save-baseline /etc/outbound-baseline.json
```

This records every destination IP, port, and CIDR network seen so far as "known good." Future audits flag anything not in this snapshot.

### Step 4 — Install

```bash
sudo pip3 install -e .
sudo cp src/outbound_audit_cron.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/outbound_audit_cron.sh
```

Without pip, copy the package manually:

```bash
sudo cp src/outbound_audit.py /usr/local/bin/
sudo cp -r src/egress_monitor /usr/local/lib/egress_monitor
sudo cp src/outbound_audit_cron.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/outbound_audit_cron.sh
```

### Step 5 — Schedule the nightly job

```bash
sudo crontab -e
```

Add:

```
0 0 * * * EMAIL=you@example.com /usr/local/bin/outbound_audit_cron.sh
```

This runs every night at midnight, analyzes the previous day's traffic against your baseline, writes a dated report to `/var/log/outbound-audit-reports/`, and emails you only if something is wrong.

## Running It Manually

```bash
# Full report for today
sudo outbound-audit

# Only show Ollama activity
sudo outbound-audit --ollama-only

# Analyze a specific time window
sudo outbound-audit --after "2025-03-20 08:00" --before "2025-03-20 17:00"

# Compare against your baseline
sudo outbound-audit --baseline /etc/outbound-baseline.json

# Skip DNS lookups for faster output
sudo outbound-audit --no-resolve
```

Or run directly without installing:

```bash
sudo python3 src/outbound_audit.py --baseline /etc/outbound-baseline.json
```

The tool exits with a structured code that the cron wrapper uses — no fragile text-scraping:

| Exit code | Meaning |
|-----------|---------|
| `0` | Clean — no anomalies |
| `1` | Anomalies detected |
| `2` | Ollama outbound activity detected |

## Alert Severity Reference

| Severity | Type | What it means |
|----------|------|----------------|
| CRITICAL | `OLLAMA_OUTBOUND` | The Ollama process initiated an outbound connection |
| HIGH | `NEW_DESTINATION` | A destination IP appeared that was not in the baseline |
| HIGH | `BLOCKED_ATTEMPT` | Something tried to reach out and was denied |
| MEDIUM | `UNUSUAL_PORT` | Traffic on a port outside the expected set (53, 80, 123, 443, 853) |
| MEDIUM | `NEW_DST_PORT` | Known destination, but a new port is being used |

## Requirements

- Rocky Linux or any RHEL-compatible distro (RHEL 8/9, AlmaLinux, CentOS Stream)
- `firewalld` running
- `rsyslog` running
- Python 3.9+
- `s-nail` for email alerts: `sudo dnf install s-nail -y`
