"""
baseline.py — Save and load known-good traffic pattern baselines.
"""

import ipaddress
import json
import sys
from datetime import datetime


def save_baseline(entries: list[dict], path: str) -> None:
    """Save current traffic patterns as a known-good baseline JSON file."""
    destinations = list(set(e["dst"] for e in entries))
    dst_ports = list(set((e["dst"], e["dpt"]) for e in entries if e["dpt"] > 0))

    baseline = {
        "created": datetime.now().isoformat(),
        "entry_count": len(entries),
        "known_destinations": destinations,
        "known_destination_ports": dst_ports,
        "known_ports": list(set(e["dpt"] for e in entries if e["dpt"] > 0)),
    }

    with open(path, "w") as f:
        json.dump(baseline, f, indent=2)

    print(f"\n✓ Baseline saved to {path}")
    print(f"  {len(destinations)} unique destinations, {len(dst_ports)} unique dst:port pairs")
    print(f"  Use with: outbound_audit.py --baseline {path}")


def load_baseline(path: str) -> dict | None:
    """Load a previously saved baseline. Exits on missing or malformed file."""
    if not path:
        return None
    try:
        with open(path, "r") as f:
            baseline = json.load(f)
        print(f"  Loaded baseline from {path} "
              f"({baseline.get('entry_count', '?')} entries, "
              f"created {baseline.get('created', '?')})",
              file=sys.stderr)
        return baseline
    except FileNotFoundError:
        print(f"ERROR: Baseline file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"ERROR: Invalid JSON in baseline: {path}", file=sys.stderr)
        sys.exit(1)


def parse_known_networks(baseline: dict) -> list:
    """Return list of ip_network objects from the baseline's known_networks field."""
    networks = []
    for cidr in baseline.get("known_networks", []):
        try:
            networks.append(ipaddress.ip_network(cidr, strict=False))
        except ValueError:
            pass
    return networks


def ip_in_known_network(ip_str: str, networks: list) -> bool:
    """Return True if ip_str falls within any of the given networks."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in net for net in networks)
    except ValueError:
        return False
