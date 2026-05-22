"""
cli.py — Argument parsing and orchestration for the outbound-audit CLI.

This module is the package's public entry point. outbound_audit.py in src/
delegates here so the tool works both as a standalone copied script and as an
installed package command.

Exit codes (consumed by outbound_audit_cron.sh):
    0  Clean — no anomalies detected
    1  Anomalies detected (new destinations, unusual ports, blocked attempts)
    2  Ollama outbound activity detected (always also implies anomalies)
"""

import argparse
import sys
from datetime import datetime

from .baseline import load_baseline, save_baseline
from .detection import (
    compute_ollama_detail,
    compute_summary,
    detect_anomalies,
)
from .dns import warm_dns_cache
from .log_parser import read_log_file
from .report import (
    render_anomaly_report,
    render_ollama_report,
    render_summary_report,
)

EXIT_CLEAN = 0
EXIT_ANOMALIES = 1
EXIT_OLLAMA_OUTBOUND = 2


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze outbound connection logs from firewalld for suspicious activity.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo outbound-audit                                    # Analyze default log
  sudo outbound-audit --ollama-only                      # Just Ollama activity
  sudo outbound-audit --save-baseline base.json          # Snapshot current traffic
  sudo outbound-audit --baseline base.json               # Compare against baseline
  sudo outbound-audit --after "2025-03-20 08:00" --before "2025-03-20 17:00"

Exit codes: 0=clean  1=anomalies  2=ollama-outbound
        """,
    )
    parser.add_argument("-f", "--file", default="/var/log/outbound-connections.log",
                        help="Log file to analyze (default: /var/log/outbound-connections.log)")
    parser.add_argument("-n", "--top", type=int, default=10,
                        help="Number of top items to show (default: 10)")
    parser.add_argument("--ollama-only", action="store_true",
                        help="Only show Ollama outbound activity")
    parser.add_argument("--no-resolve", action="store_true",
                        help="Skip reverse DNS lookups (faster)")
    parser.add_argument("--baseline", metavar="FILE",
                        help="Compare against a known-good baseline JSON file")
    parser.add_argument("--save-baseline", metavar="FILE",
                        help="Save current traffic patterns as a baseline and exit")
    parser.add_argument("--after", metavar="DATETIME",
                        help="Only include entries after this time (YYYY-MM-DD HH:MM)")
    parser.add_argument("--before", metavar="DATETIME",
                        help="Only include entries before this time (YYYY-MM-DD HH:MM)")
    return parser.parse_args()


def _apply_time_filters(entries: list, after_str: str | None, before_str: str | None) -> list:
    """Filter entries to the requested time window. Exits on bad datetime format."""
    fmt = "%Y-%m-%d %H:%M"
    if after_str:
        try:
            after_dt = datetime.strptime(after_str, fmt)
            entries = [e for e in entries if e["timestamp"] >= after_dt]
        except ValueError:
            print("ERROR: Invalid --after format. Use 'YYYY-MM-DD HH:MM'", file=sys.stderr)
            sys.exit(1)

    if before_str:
        try:
            before_dt = datetime.strptime(before_str, fmt)
            entries = [e for e in entries if e["timestamp"] <= before_dt]
        except ValueError:
            print("ERROR: Invalid --before format. Use 'YYYY-MM-DD HH:MM'", file=sys.stderr)
            sys.exit(1)

    return entries


def main() -> None:
    args = _parse_args()
    resolve = not args.no_resolve

    print(f"Reading {args.file}...", file=sys.stderr)
    entries = read_log_file(args.file)
    print(f"Parsed {len(entries):,} log entries.", file=sys.stderr)

    entries = _apply_time_filters(entries, args.after, args.before)

    if not entries:
        print("\nNo entries found in the specified range.")
        sys.exit(EXIT_CLEAN)

    print(f"Analyzing {len(entries):,} entries after filters...", file=sys.stderr)

    if args.save_baseline:
        save_baseline(entries, args.save_baseline)
        sys.exit(EXIT_CLEAN)

    baseline = load_baseline(args.baseline) if args.baseline else None

    if resolve:
        print("Resolving unique IPs (cached)...", file=sys.stderr)
        warm_dns_cache(entries)

    # Compute all results before rendering anything
    summary = compute_summary(entries)
    ollama_detail = compute_ollama_detail(entries)
    anomalies = detect_anomalies(entries, baseline)

    # Render reports
    if args.ollama_only:
        render_ollama_report(ollama_detail, resolve)
    else:
        render_summary_report(summary, args.top, resolve)
        render_ollama_report(ollama_detail, resolve)
        render_anomaly_report(anomalies, baseline is not None, resolve)

    # Footer
    print(f"\n{'─' * 78}")
    print(f"Log file: {args.file}")
    if baseline:
        print(f"Baseline: {args.baseline}")
    print()

    # Exit code contract: consumed by outbound_audit_cron.sh
    if ollama_detail["found"]:
        sys.exit(EXIT_OLLAMA_OUTBOUND)
    if anomalies:
        sys.exit(EXIT_ANOMALIES)
    sys.exit(EXIT_CLEAN)
