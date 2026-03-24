# Egress Monitor

Outbound egress monitor for Rocky Linux servers — firewalld logging setup + Python log parser with anomaly detection for Ollama LLM hosts.

## When You Don't Know What Your LLMs Are Calling Home To

Running Ollama on a shared server means trusting that the LLM process behaves. But does it? Firewalld permits outbound traffic by default and logs nothing. Without visibility into outbound connections, you have no way to know whether Ollama — or anything else on the server — is reaching out to unexpected destinations, on unusual ports, or at unusual times.

## What This Toolkit Does

A two-part setup: a bash script that instruments firewalld to log every new outbound TCP/UDP connection (allowed and blocked), and a Python script that parses those logs and surfaces anything worth investigating.

The setup script adds direct iptables rules to firewalld's OUTPUT chain, routes the kernel log messages to a dedicated file via rsyslog, and configures logrotate so logs don't fill the disk. Optionally, it installs `conntrack` for structured connection tracking via a systemd service.

The audit script reads the log file, parses each kernel log line, and produces three reports:

- **Summary** — top destinations, ports, source hosts, hourly distribution, protocol breakdown
- **Ollama activity** — dedicated section that flags any connection initiated by the Ollama process, with first/last seen timestamps and suggested firewall block commands
- **Anomaly detection** — flags unusual ports, blocked outbound attempts, and (with a baseline) any destination or port combination never seen before

## Example Output

```
════════════════════════════════════════════════════════════════════════════════
  OLLAMA OUTBOUND ACTIVITY
════════════════════════════════════════════════════════════════════════════════

  ⚠  OLLAMA MADE 3 OUTBOUND CONNECTION(S)

  Destination               Port     Count  First Seen   Last Seen
  ──────────────────────────────────────────────────────────────────
  ollama.ai (104.21.8.42)   443/HTTPS  3    03-20 09:14  03-20 11:02

  Action items:
  • Investigate what Ollama is reaching out to
  • Check if OLLAMA_HOST or model pull configs are set
  • Consider blocking with: firewall-cmd --direct --add-rule ipv4 filter OUTPUT 0 \
      -m owner --uid-owner ollama -j REJECT
```

## Usage

**Step 1 — Set up logging on the server (run once, requires root):**

```bash
sudo bash setup_outbound_logging.sh

# With conntrack for structured connection tracking:
sudo bash setup_outbound_logging.sh --with-conntrack
```

Logs are written to `/var/log/outbound-connections.log`. Verify it's working:

```bash
tail -f /var/log/outbound-connections.log
curl -s https://example.com > /dev/null   # should generate an entry
```

**Step 2 — Analyze the logs:**

```bash
# Analyze today's logs
sudo python3 outbound_audit.py

# Only show Ollama's outbound activity
sudo python3 outbound_audit.py --ollama-only

# Analyze a specific log file
sudo python3 outbound_audit.py -f /var/log/outbound-connections.log

# Filter to a time window
sudo python3 outbound_audit.py --after "2025-03-20 08:00" --before "2025-03-20 17:00"

# Show top 20 results instead of default 10
sudo python3 outbound_audit.py -n 20

# Skip reverse DNS lookups (faster)
sudo python3 outbound_audit.py --no-resolve
```

**Baseline comparison — detect new activity over time:**

```bash
# Save a snapshot of current "normal" traffic
sudo python3 outbound_audit.py --save-baseline /etc/outbound-baseline.json

# Later, compare against it to flag anything new
sudo python3 outbound_audit.py --baseline /etc/outbound-baseline.json
```

**To remove all outbound logging rules:**

```bash
firewall-cmd --permanent --direct --remove-rules ipv4 filter OUTPUT
firewall-cmd --permanent --direct --remove-rules ipv6 filter OUTPUT
firewall-cmd --reload
rm -f /etc/rsyslog.d/10-outbound-connections.conf
systemctl restart rsyslog
```

**Requirements:** Rocky Linux with firewalld running. Python 3.10+ (stdlib only). Root access for setup and log reads.
