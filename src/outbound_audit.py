#!/usr/bin/env python3
"""
outbound_audit.py — Standalone entry point for the egress monitor audit engine.

Copy this file to /usr/local/bin/ alongside the egress_monitor/ package directory,
or install the whole package with:  pip install -e /path/to/egress-monitor

See egress_monitor/cli.py for the full CLI implementation.

Exit codes:
    0  Clean — no anomalies detected
    1  Anomalies detected
    2  Ollama outbound activity detected
"""

import os
import sys

# Allow running from src/ without a pip install
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from egress_monitor.cli import main

if __name__ == "__main__":
    main()
