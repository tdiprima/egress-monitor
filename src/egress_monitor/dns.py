"""
dns.py — Cached reverse-DNS resolution for connection log entry addresses.
"""

import socket
from functools import lru_cache


@lru_cache(maxsize=4096)
def resolve_ip(ip: str) -> str:
    """Reverse-DNS lookup with caching. Returns hostname or original IP."""
    try:
        hostname, _, _ = socket.gethostbyaddr(ip)
        return hostname
    except (socket.herror, socket.gaierror, OSError):
        return ip


def fmt_dst(ip: str, resolve: bool = True) -> str:
    """Format a destination as 'hostname (IP)' or just 'IP'."""
    if not resolve:
        return ip
    hostname = resolve_ip(ip)
    if hostname != ip:
        return f"{hostname} ({ip})"
    return ip


def warm_dns_cache(entries: list[dict]) -> None:
    """Pre-resolve all unique IPs in a batch to populate the cache."""
    unique_ips = set(e["dst"] for e in entries) | set(e["src"] for e in entries)
    for ip in unique_ips:
        resolve_ip(ip)
