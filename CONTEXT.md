# Egress Monitor — Domain Vocabulary

Terms used consistently across code, docs, and commit messages.

## Core Concepts

**Outbound connection**
A network packet originating from the monitored host destined for an external address. Internal-only traffic (loopback, Docker bridges, veth pairs) is explicitly excluded.

**Connection log entry**
A single parsed record from `/var/log/outbound-connections.log`, produced by the firewalld/iptables LOG target. Contains: timestamp, source IP, destination IP, destination port, protocol, log prefix, and a flag indicating whether the initiating process was Ollama.

**Log prefix**
The iptables LOG prefix embedded in each connection log entry. Encodes intent:
- `OUTBOUND_CONN_TCP` / `OUTBOUND_CONN_UDP` — allowed outbound traffic
- `OLLAMA_OUTBOUND_TCP` / `OLLAMA_OUTBOUND_UDP` — traffic originated by the Ollama process
- `OUTBOUND_BLOCKED` — traffic that reached the catch-all rule (did not match earlier allow rules)

**Ollama outbound**
An outbound connection where the log prefix indicates the Ollama inference process itself initiated the connection (not a client calling into Ollama). This is the primary threat signal the tool was built to detect.

**Baseline**
A JSON snapshot of known-good traffic patterns: the set of destination IPs, destination ports, and CIDR networks observed during a representative "normal" period. Saved with `--save-baseline`; used by anomaly detection to identify new or unexpected destinations.

**Anomaly**
A deviation from baseline or a categorically suspicious event. Anomalies have a type (`UNUSUAL_PORT`, `BLOCKED_ATTEMPT`, `OLLAMA_OUTBOUND`, `NEW_DESTINATION`, `NEW_DST_PORT`) and a severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`).

**Audit run**
A single execution of `outbound_audit.py` over a specified time window against a log file, optionally compared to a baseline. Produces a summary, an Ollama report, and an anomaly report.

**Audit report**
The rendered output of an audit run. Can be displayed to a terminal (ANSI color) or written to a plain-text file for email delivery.

**Egress monitoring**
The broader practice this tool supports: continuously recording all outbound network connections from a host and alerting when unexpected patterns emerge.

## System Components

**Firewall logging layer** (`setup_outbound_logging.sh`)
Configures firewalld direct rules and rsyslog to capture all new outbound connections to a dedicated log file. Sets up logrotate for retention.

**Audit engine** (`outbound_audit.py`)
Parses the connection log, computes summaries and anomalies, renders reports to terminal or file.

**Cron wrapper** (`outbound_audit_cron.sh`)
Nightly scheduled audit: runs the audit engine against yesterday's traffic, writes a report file, and sends an email alert if anomalies are found.
