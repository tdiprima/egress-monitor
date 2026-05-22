"""
report.py — Render audit run results to the terminal.

All functions here accept pre-computed data dicts (from detection.py) and
write formatted output to stdout. No detection logic lives here.
"""

import re
import sys

from .dns import fmt_dst
from .log_parser import KNOWN_PORTS, NORMAL_OUTBOUND_PORTS


# =============================================================================
# Color helpers — disabled when stdout is not a TTY
# =============================================================================

class C:
    """ANSI color codes."""
    _enabled = sys.stdout.isatty()

    RESET   = "\033[0m"   if _enabled else ""
    BOLD    = "\033[1m"    if _enabled else ""
    DIM     = "\033[2m"    if _enabled else ""
    RED     = "\033[91m"   if _enabled else ""
    GREEN   = "\033[92m"   if _enabled else ""
    YELLOW  = "\033[93m"   if _enabled else ""
    BLUE    = "\033[94m"   if _enabled else ""
    MAGENTA = "\033[95m"   if _enabled else ""
    CYAN    = "\033[96m"   if _enabled else ""
    WHITE   = "\033[97m"   if _enabled else ""
    BG_RED  = "\033[41m"   if _enabled else ""


# =============================================================================
# Layout primitives
# =============================================================================

def print_header(title: str) -> None:
    width = 78
    print()
    print(f"{C.BOLD}{C.CYAN}{'═' * width}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}  {title}{C.RESET}")
    print(f"{C.BOLD}{C.CYAN}{'═' * width}{C.RESET}")


def print_section(title: str) -> None:
    print(f"\n{C.BOLD}{C.YELLOW}── {title} {'─' * (74 - len(title))}{C.RESET}")


def print_table(headers: list[str], rows: list[list], col_widths: list[int] = None) -> None:
    """Print a simple aligned table."""
    if not rows:
        print(f"  {C.DIM}(none){C.RESET}")
        return

    if col_widths is None:
        col_widths = []
        for i, h in enumerate(headers):
            max_w = len(h)
            for row in rows:
                if i < len(row):
                    clean = re.sub(r"\033\[[0-9;]*m", "", str(row[i]))
                    max_w = max(max_w, len(clean))
            col_widths.append(min(max_w, 60))

    header_line = "  "
    for i, h in enumerate(headers):
        header_line += f"{C.BOLD}{h:<{col_widths[i]}}{C.RESET}  "
    print(header_line)
    print(f"  {C.DIM}{'─' * (sum(col_widths) + 2 * len(col_widths))}{C.RESET}")

    for row in rows:
        line = "  "
        for i, cell in enumerate(row):
            clean = re.sub(r"\033\[[0-9;]*m", "", str(cell))
            padding = col_widths[i] - len(clean)
            line += f"{cell}{' ' * max(0, padding)}  "
        print(line)


def port_label(port: int) -> str:
    """Return 'port/SERVICE' or just 'port'."""
    name = KNOWN_PORTS.get(port, "")
    return f"{port}/{name}" if name else str(port)


# =============================================================================
# Report renderers — each takes a pre-computed data dict
# =============================================================================

def render_summary_report(summary: dict, top_n: int, resolve: bool) -> None:
    """Render the summary report from a compute_summary() result."""
    print_header("OUTBOUND CONNECTION SUMMARY REPORT")

    if summary.get("empty"):
        print(f"\n  {C.DIM}No log entries found in the specified range.{C.RESET}")
        return

    ts_min = summary["ts_min"]
    ts_max = summary["ts_max"]
    total = summary["total"]

    print(f"\n  {C.BOLD}Time range:{C.RESET}  "
          f"{ts_min.strftime('%Y-%m-%d %H:%M')} → {ts_max.strftime('%Y-%m-%d %H:%M')}")
    print(f"  {C.BOLD}Total connections:{C.RESET}  {total:,}")
    print(f"  {C.BOLD}Allowed:{C.RESET}  {C.GREEN}{summary['allowed_count']:,}{C.RESET}    "
          f"{C.BOLD}Blocked:{C.RESET}  {C.RED}{summary['blocked_count']:,}{C.RESET}    "
          f"{C.BOLD}Ollama-originated:{C.RESET}  {C.MAGENTA}{summary['ollama_count']:,}{C.RESET}")

    # Top destinations
    print_section(f"Top {top_n} Destinations")
    ollama_dsts = summary["ollama_dsts"]
    rows = []
    for ip, count in summary["top_destinations"][:top_n]:
        pct = count / total * 100
        bar_len = int(pct / 2)
        bar = f"{C.BLUE}{'█' * bar_len}{C.DIM}{'░' * (25 - bar_len)}{C.RESET}"
        flag = f"  {C.BG_RED}{C.WHITE} OLLAMA {C.RESET}" if ip in ollama_dsts else ""
        rows.append([fmt_dst(ip, resolve), str(count), f"{pct:5.1f}%", bar + flag])
    print_table(["Destination", "Count", "Pct", ""], rows)

    # Top ports
    print_section(f"Top {top_n} Destination Ports")
    rows = []
    for port, count in summary["top_ports"][:top_n]:
        pct = count / total * 100
        port_str = port_label(port)
        if port not in NORMAL_OUTBOUND_PORTS:
            port_str = f"{C.YELLOW}{port_str}{C.RESET}"
        rows.append([port_str, str(count), f"{pct:5.1f}%"])
    print_table(["Port", "Count", "Pct"], rows)

    # Top source IPs (useful if multiple servers log to same file)
    top_sources = summary["top_sources"]
    if len(top_sources) > 1:
        print_section(f"Top {top_n} Source Hosts")
        rows = [[fmt_dst(ip, resolve), str(count)] for ip, count in top_sources[:top_n]]
        print_table(["Source", "Count"], rows)

    # Hourly distribution (last 24h)
    print_section("Hourly Distribution (last 24h)")
    if summary["has_recent"]:
        hourly = summary["hourly"]
        max_count = max(hourly.values()) if hourly else 1
        for hour in range(24):
            count = hourly.get(hour, 0)
            bar_len = int(count / max_count * 40) if max_count > 0 else 0
            bar = f"{C.BLUE}{'█' * bar_len}{C.RESET}"
            print(f"  {hour:02d}:00  {bar} {count}")
    else:
        print(f"  {C.DIM}No entries in the last 24 hours.{C.RESET}")

    # Protocol breakdown
    print_section("Protocol Breakdown")
    rows = [[proto, str(count)] for proto, count in summary["protocols"]]
    print_table(["Protocol", "Count"], rows)


def render_ollama_report(ollama_detail: dict, resolve: bool) -> None:
    """Render the Ollama outbound activity section from a compute_ollama_detail() result."""
    print_header("OLLAMA OUTBOUND ACTIVITY")

    if not ollama_detail["found"]:
        print(f"\n  {C.GREEN}{C.BOLD}✓ No outbound connections from Ollama detected.{C.RESET}")
        print(f"  {C.DIM}This is the expected result if Ollama is behaving.{C.RESET}")
        return

    # This is the interesting case — Ollama is phoning home
    total = ollama_detail["total"]
    print(f"\n  {C.BG_RED}{C.WHITE}{C.BOLD} ⚠  OLLAMA MADE {total:,} OUTBOUND CONNECTION(S) {C.RESET}")
    print()

    rows = []
    for item in ollama_detail["by_dst_port"]:
        rows.append([
            fmt_dst(item["dst"], resolve),
            port_label(item["port"]),
            str(item["count"]),
            item["first_seen"].strftime("%m-%d %H:%M"),
            item["last_seen"].strftime("%m-%d %H:%M"),
        ])
    print_table(["Destination", "Port", "Count", "First Seen", "Last Seen"], rows)

    print(f"\n  {C.YELLOW}Action items:{C.RESET}")
    print("  • Investigate what Ollama is reaching out to")
    print("  • Check if OLLAMA_HOST or model pull configs are set")
    print("  • Consider blocking with: firewall-cmd --direct --add-rule ipv4 filter OUTPUT 0 \\")
    print("      -m owner --uid-owner ollama -j REJECT")


def render_anomaly_report(anomalies: list[dict], has_baseline: bool, resolve: bool) -> None:
    """Render the anomaly detection section from a detect_anomalies() result."""
    print_header("ANOMALY DETECTION")

    if not anomalies:
        if has_baseline:
            print(f"\n  {C.GREEN}{C.BOLD}✓ No anomalies detected vs. baseline.{C.RESET}")
        else:
            print(f"\n  {C.GREEN}{C.BOLD}✓ No obvious anomalies detected.{C.RESET}")
            print(f"  {C.DIM}Tip: Create a baseline with --save-baseline for better detection.{C.RESET}")
        return

    severity_colors = {
        "CRITICAL": C.BG_RED + C.WHITE,
        "HIGH": C.RED,
        "MEDIUM": C.YELLOW,
        "LOW": C.DIM,
    }

    print(f"\n  Found {C.BOLD}{len(anomalies)}{C.RESET} anomalies:\n")

    rows = []
    for a in anomalies:
        sev = a["severity"]
        sev_str = f"{severity_colors.get(sev, '')}{sev:<8}{C.RESET}"
        dst_str = fmt_dst(a["dst"], resolve)
        port_str = port_label(a["port"]) if a["port"] > 0 else "—"
        rows.append([sev_str, a["type"], dst_str, port_str, str(a["count"]), a["detail"]])
    print_table(["Severity", "Type", "Destination", "Port", "Count", "Detail"], rows)
