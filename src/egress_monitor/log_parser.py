"""
log_parser.py — Parse raw firewalld/iptables LOG lines into connection log entries.
"""

import re
import sys
from datetime import datetime

# Matches kernel log lines from iptables/firewalld LOG target
# Example: Mar 20 14:23:01 server1 kernel: OUTBOUND_CONN_TCP: IN= OUT=eth0 SRC=10.0.0.5 DST=104.18.32.7 ...
LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\w+\s+\d+\s+\d+:\d+:\d+)\s+"  # syslog timestamp
    r"(?P<hostname>\S+)\s+"                           # hostname
    r"kernel:\s*"                                      # kernel prefix
    r"(?P<prefix>\S+?):\s+"                            # our log prefix (OUTBOUND_CONN_TCP, OLLAMA_OUTBOUND_TCP, etc.)
    r"(?P<fields>.*)"                                  # key=value fields
)

FIELD_PATTERN = re.compile(r"(\w+)=(\S*)")

# Well-known ports for display
KNOWN_PORTS = {
    22: "SSH", 25: "SMTP", 53: "DNS", 80: "HTTP", 123: "NTP",
    443: "HTTPS", 465: "SMTPS", 587: "SMTP-SUB", 853: "DNS-TLS",
    993: "IMAPS", 995: "POP3S", 3306: "MySQL", 5432: "PostgreSQL",
    5672: "AMQP", 6379: "Redis", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
    9090: "Prometheus", 9200: "Elasticsearch", 11434: "Ollama",
    27017: "MongoDB",
}

# Ports that are generally expected for outbound traffic
NORMAL_OUTBOUND_PORTS = {53, 80, 123, 443, 853}


def parse_syslog_timestamp(ts_str: str, year: int = None) -> datetime:
    """Parse syslog-style 'Mar 20 14:23:01' timestamps."""
    if year is None:
        year = datetime.now().year
    try:
        return datetime.strptime(f"{year} {ts_str}", "%Y %b %d %H:%M:%S")
    except ValueError:
        return None


def parse_log_line(line: str) -> dict | None:
    """Parse a single log line into a connection log entry dict."""
    m = LOG_PATTERN.match(line.strip())
    if not m:
        return None

    fields_raw = m.group("fields")
    fields = dict(FIELD_PATTERN.findall(fields_raw))

    return {
        "timestamp": parse_syslog_timestamp(m.group("timestamp")),
        "hostname": m.group("hostname"),
        "prefix": m.group("prefix"),
        "src": fields.get("SRC", ""),
        "dst": fields.get("DST", ""),
        "dpt": int(fields.get("DPT", 0)),
        "spt": int(fields.get("SPT", 0)),
        "proto": fields.get("PROTO", "").upper(),
        "out_iface": fields.get("OUT", ""),
        "in_iface": fields.get("IN", ""),
        "uid": fields.get("UID", ""),
        "is_ollama": "OLLAMA" in m.group("prefix"),
        "is_blocked": "BLOCKED" in m.group("prefix"),
        "raw": line.strip(),
    }


def _is_internal_iface(iface: str) -> bool:
    """Return True for interfaces whose traffic never leaves the machine."""
    return iface in ("lo",) or iface.startswith(("docker", "br-", "veth"))


def read_log_file(path: str) -> list[dict]:
    """Read and parse an entire log file, dropping internal-interface traffic."""
    entries = []
    try:
        with open(path, "r") as f:
            for line in f:
                entry = parse_log_line(line)
                if entry and entry["timestamp"] and not _is_internal_iface(entry["out_iface"]):
                    entries.append(entry)
    except FileNotFoundError:
        print(f"ERROR: Log file not found: {path}", file=sys.stderr)
        print("  Has setup_outbound_logging.sh been run yet?", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"ERROR: Permission denied: {path}", file=sys.stderr)
        print("  Try running with sudo.", file=sys.stderr)
        sys.exit(1)
    return entries
