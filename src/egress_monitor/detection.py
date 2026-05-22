"""
detection.py — Pure anomaly detection and traffic summarization.

All functions here are side-effect free: they accept connection log entries
and return structured data. Nothing is printed. This makes them directly
testable without stdout capture.
"""

from collections import Counter
from datetime import datetime, timedelta

from .baseline import parse_known_networks, ip_in_known_network
from .log_parser import NORMAL_OUTBOUND_PORTS


def _allowed_dst_ports(entries: list[dict]) -> set[tuple]:
    """Return (dst, dpt) pairs for connections that were not blocked."""
    return set((e["dst"], e["dpt"]) for e in entries if not e["is_blocked"])


def detect_ollama_activity(entries: list[dict]) -> list[dict]:
    """Return all connection log entries where Ollama was the originating process."""
    return [e for e in entries if e["is_ollama"]]


def detect_blocked_attempts(entries: list[dict]) -> list[dict]:
    """
    Return connection log entries for truly blocked connections.

    Excludes double-logged entries: iptables LOG is non-terminating, so a packet
    logged at priority 2 (OUTBOUND_CONN) also hits priority 999 (OUTBOUND_BLOCKED).
    Truly blocked traffic appears in BLOCKED but not in any CONN entry.
    """
    allowed = _allowed_dst_ports(entries)
    return [
        e for e in entries
        if e["is_blocked"] and (e["dst"], e["dpt"]) not in allowed
    ]


def detect_anomalies(entries: list[dict], baseline: dict | None) -> list[dict]:
    """
    Identify anomalous outbound connections and return a list of anomaly dicts.

    Each anomaly dict has keys: type, severity, dst, port, count, detail.
    Severity levels: CRITICAL > HIGH > MEDIUM > LOW.
    """
    anomalies = []

    # --- Unusual destination ports ---
    unusual_port_entries = [
        e for e in entries
        if e["dpt"] > 0 and e["dpt"] not in NORMAL_OUTBOUND_PORTS
    ]
    if unusual_port_entries:
        unusual_ports = Counter((e["dst"], e["dpt"]) for e in unusual_port_entries)
        for (ip, port), count in unusual_ports.most_common(20):
            anomalies.append({
                "type": "UNUSUAL_PORT",
                "severity": "MEDIUM",
                "dst": ip,
                "port": port,
                "count": count,
                "detail": f"Port {port} is not in the standard outbound set",
            })

    # --- Blocked connection attempts ---
    blocked = detect_blocked_attempts(entries)
    if blocked:
        blocked_dsts = Counter((e["dst"], e["dpt"]) for e in blocked)
        for (ip, port), count in blocked_dsts.most_common(20):
            anomalies.append({
                "type": "BLOCKED_ATTEMPT",
                "severity": "HIGH",
                "dst": ip,
                "port": port,
                "count": count,
                "detail": f"Outbound connection was blocked {count} time(s)",
            })

    # --- Ollama outbound (always flagged as CRITICAL) ---
    ollama = detect_ollama_activity(entries)
    if ollama:
        ollama_dsts = Counter(e["dst"] for e in ollama)
        for ip, count in ollama_dsts.most_common():
            anomalies.append({
                "type": "OLLAMA_OUTBOUND",
                "severity": "CRITICAL",
                "dst": ip,
                "port": 0,
                "count": count,
                "detail": f"Ollama process initiated {count} outbound connection(s)",
            })

    # --- First-seen destinations vs. baseline ---
    if baseline:
        known_dsts = set(baseline.get("known_destinations", []))
        known_dst_ports = set(
            tuple(x) for x in baseline.get("known_destination_ports", [])
        )
        known_networks = parse_known_networks(baseline)
        current_dsts = set(e["dst"] for e in entries)
        current_dst_ports = set((e["dst"], e["dpt"]) for e in entries if e["dpt"] > 0)

        new_dsts = {
            ip for ip in (current_dsts - known_dsts)
            if not ip_in_known_network(ip, known_networks)
        }
        new_dst_ports = {
            (ip, port) for ip, port in (current_dst_ports - known_dst_ports)
            if not ip_in_known_network(ip, known_networks)
        }

        for ip in new_dsts:
            count = sum(1 for e in entries if e["dst"] == ip)
            anomalies.append({
                "type": "NEW_DESTINATION",
                "severity": "HIGH",
                "dst": ip,
                "port": 0,
                "count": count,
                "detail": "Destination NOT in baseline — never seen before",
            })

        for ip, port in new_dst_ports:
            if ip not in new_dsts:  # avoid double-flagging
                count = sum(1 for e in entries if e["dst"] == ip and e["dpt"] == port)
                anomalies.append({
                    "type": "NEW_DST_PORT",
                    "severity": "MEDIUM",
                    "dst": ip,
                    "port": port,
                    "count": count,
                    "detail": f"Known destination, but port {port} is new",
                })

    severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    anomalies.sort(key=lambda a: (severity_order.get(a["severity"], 99), -a["count"]))
    return anomalies


def compute_summary(entries: list[dict]) -> dict:
    """
    Compute traffic summary statistics from a list of connection log entries.

    Returns a dict with counts, top destinations, top ports, hourly distribution,
    and protocol breakdown — all as plain data, ready for any renderer.
    """
    if not entries:
        return {"empty": True}

    blocked = detect_blocked_attempts(entries)
    allowed = [e for e in entries if not e["is_blocked"]]
    ollama = detect_ollama_activity(entries)

    ts_min = min(e["timestamp"] for e in entries)
    ts_max = max(e["timestamp"] for e in entries)

    dst_counter = Counter(e["dst"] for e in entries)
    port_counter = Counter(e["dpt"] for e in entries if e["dpt"] > 0)
    src_counter = Counter(e["src"] for e in entries)
    proto_counter = Counter(e["proto"] for e in entries if e["proto"])

    now = datetime.now()
    cutoff_24h = now - timedelta(hours=24)
    recent = [e for e in entries if e["timestamp"] >= cutoff_24h]
    hourly = Counter(e["timestamp"].hour for e in recent)

    # Tag which destination IPs have Ollama traffic
    ollama_dsts = set(e["dst"] for e in ollama)

    return {
        "empty": False,
        "total": len(entries),
        "allowed_count": len(allowed),
        "blocked_count": len(blocked),
        "ollama_count": len(ollama),
        "ts_min": ts_min,
        "ts_max": ts_max,
        "top_destinations": dst_counter.most_common(),
        "top_ports": port_counter.most_common(),
        "top_sources": src_counter.most_common(),
        "hourly": hourly,
        "protocols": proto_counter.most_common(),
        "ollama_dsts": ollama_dsts,
        "has_recent": bool(recent),
    }


def compute_ollama_detail(entries: list[dict]) -> dict:
    """
    Compute per-destination Ollama connection detail for report rendering.

    Returns a dict with the raw Ollama entries and a per-(dst,port) breakdown
    including first/last seen timestamps.
    """
    ollama = detect_ollama_activity(entries)
    if not ollama:
        return {"found": False, "entries": [], "by_dst_port": []}

    dst_port_counter = Counter((e["dst"], e["dpt"]) for e in ollama)
    by_dst_port = []
    for (ip, port), count in dst_port_counter.most_common():
        matching = [e for e in ollama if e["dst"] == ip and e["dpt"] == port]
        by_dst_port.append({
            "dst": ip,
            "port": port,
            "count": count,
            "first_seen": min(e["timestamp"] for e in matching),
            "last_seen": max(e["timestamp"] for e in matching),
        })

    return {
        "found": True,
        "total": len(ollama),
        "entries": ollama,
        "by_dst_port": by_dst_port,
    }
