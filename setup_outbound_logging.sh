#!/bin/bash
# =============================================================================
# setup_outbound_logging.sh
# 
# Sets up comprehensive outbound connection logging on Rocky Linux (firewalld)
# Purpose: Audit all outbound connections (allowed AND blocked) from hoppers
#          to detect undocumented LLM network activity.
#
# What this script does:
#   1. Adds firewalld rich rules to LOG all new outbound connections
#   2. Configures rsyslog to route outbound logs to a dedicated file
#   3. Sets up logrotate so logs don't fill the disk
#   4. (Optional) Installs conntrack for structured connection tracking
#
# Usage:
#   sudo bash setup_outbound_logging.sh [--with-conntrack]
#
# Logs written to:
#   /var/log/outbound-connections.log   (firewalld logged connections)
#   /var/log/conntrack-outbound.log     (if conntrack enabled)
#
# To verify it's working:
#   tail -f /var/log/outbound-connections.log
#   curl -s https://example.com > /dev/null   # should generate a log entry
# =============================================================================

set -euo pipefail

# --- Configuration -----------------------------------------------------------
LOG_FILE="/var/log/outbound-connections.log"
CONNTRACK_LOG="/var/log/conntrack-outbound.log"
LOG_PREFIX="OUTBOUND_CONN"
BLOCKED_PREFIX="OUTBOUND_BLOCKED"
INSTALL_CONNTRACK=false
CONNTRACK_SERVICE_NAME="conntrack-logger"

# Ollama — skip logging local inference calls, but DO log Ollama's own outbound
OLLAMA_PORT=11434
OLLAMA_USER="ollama"   # user that the ollama service runs as (check: ps -o user= -p $(pgrep ollama))

# Parse args
for arg in "$@"; do
    case "$arg" in
        --with-conntrack) INSTALL_CONNTRACK=true ;;
        --help|-h)
            echo "Usage: sudo bash $0 [--with-conntrack]"
            echo ""
            echo "  --with-conntrack   Also install conntrack-tools and set up"
            echo "                     a systemd service for structured connection logging"
            exit 0
            ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# --- Preflight checks --------------------------------------------------------
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)."
    exit 1
fi

if ! systemctl is-active --quiet firewalld; then
    echo "ERROR: firewalld is not running. Start it first:"
    echo "  sudo systemctl enable --now firewalld"
    exit 1
fi

echo "============================================="
echo " Outbound Connection Logging Setup"
echo " Target: Rocky Linux with firewalld"
echo " Conntrack: $INSTALL_CONNTRACK"
echo "============================================="
echo ""

# --- Step 1: Get the active firewalld zone -----------------------------------
ACTIVE_ZONE=$(firewall-cmd --get-default-zone)
echo "[1/5] Active firewalld zone: $ACTIVE_ZONE"

# --- Step 2: Add rich rules for outbound logging -----------------------------
echo "[2/5] Adding firewalld rich rules for outbound logging..."

# Log ALL new outbound TCP connections (allowed ones)
# The "accept" log rule fires on permitted traffic
firewall-cmd --permanent --zone="$ACTIVE_ZONE" \
    --add-rich-rule='rule family="ipv4" source address="0.0.0.0/0" log prefix="'"$LOG_PREFIX"' " level="info" limit value="100/m"' \
    2>/dev/null || true

# These rules use direct rules to hook into the OUTPUT chain
# Rule priority (lower = evaluated first):
#   0 = skip local Ollama traffic (no log, just return)
#   1 = log Ollama process making outbound connections (important!)
#   2 = log all other outbound connections
echo "    Adding direct rules for OUTPUT chain logging..."

# --- Priority 0: SKIP local traffic TO Ollama (noisy inference calls) --------
# Anything hitting localhost:11434 is just apps calling the local LLM — not interesting
firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 0 \
    -p tcp -d 127.0.0.1 --dport "$OLLAMA_PORT" \
    -j RETURN \
    2>/dev/null || true

# Also skip loopback responses FROM Ollama back to local clients
firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 0 \
    -p tcp -s 127.0.0.1 --sport "$OLLAMA_PORT" \
    -j RETURN \
    2>/dev/null || true

# --- Priority 1: LOG Ollama's own outbound connections (the important ones) --
# If the ollama process itself reaches out to the internet, we DEFINITELY want to know
# Detect the ollama user; fall back if not found
if id "$OLLAMA_USER" &>/dev/null; then
    echo "    Detected ollama user: $OLLAMA_USER (UID $(id -u "$OLLAMA_USER"))"

    firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 1 \
        -p tcp --tcp-flags SYN,ACK,FIN,RST SYN \
        -m state --state NEW \
        -m owner --uid-owner "$OLLAMA_USER" \
        -j LOG --log-prefix "OLLAMA_OUTBOUND_TCP: " --log-level 4 \
        2>/dev/null || true

    firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 1 \
        -p udp \
        -m state --state NEW \
        -m owner --uid-owner "$OLLAMA_USER" \
        -j LOG --log-prefix "OLLAMA_OUTBOUND_UDP: " --log-level 4 \
        2>/dev/null || true

    firewall-cmd --permanent --direct --add-rule ipv6 filter OUTPUT 1 \
        -p tcp --tcp-flags SYN,ACK,FIN,RST SYN \
        -m state --state NEW \
        -m owner --uid-owner "$OLLAMA_USER" \
        -j LOG --log-prefix "OLLAMA_OUTBOUND_TCP6: " --log-level 4 \
        2>/dev/null || true
else
    echo "    WARNING: User '$OLLAMA_USER' not found. Ollama-specific rules skipped."
    echo "    Check who runs Ollama:  ps -o user= -p \$(pgrep ollama)"
    echo "    Then update OLLAMA_USER at the top of this script and re-run."
fi

# --- Priority 2: LOG all other new outbound connections ----------------------
# TCP (SYN = new connection initiation)
firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 2 \
    -p tcp --tcp-flags SYN,ACK,FIN,RST SYN \
    -m state --state NEW \
    -j LOG --log-prefix "${LOG_PREFIX}_TCP: " --log-level 4 \
    2>/dev/null || true

# UDP
firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 2 \
    -p udp \
    -m state --state NEW \
    -j LOG --log-prefix "${LOG_PREFIX}_UDP: " --log-level 4 \
    2>/dev/null || true

# IPv6 equivalents
firewall-cmd --permanent --direct --add-rule ipv6 filter OUTPUT 2 \
    -p tcp --tcp-flags SYN,ACK,FIN,RST SYN \
    -m state --state NEW \
    -j LOG --log-prefix "${LOG_PREFIX}_TCP6: " --log-level 4 \
    2>/dev/null || true

firewall-cmd --permanent --direct --add-rule ipv6 filter OUTPUT 2 \
    -p udp \
    -m state --state NEW \
    -j LOG --log-prefix "${LOG_PREFIX}_UDP6: " --log-level 4 \
    2>/dev/null || true

# --- Priority 999: LOG blocked outbound attempts ----------------------------
firewall-cmd --permanent --direct --add-rule ipv4 filter OUTPUT 999 \
    -m state --state NEW \
    -j LOG --log-prefix "${BLOCKED_PREFIX}: " --log-level 4 \
    2>/dev/null || true

# Reload to apply
firewall-cmd --reload
echo "    Done. Rules applied and firewalld reloaded."

# --- Step 3: Configure rsyslog to route to dedicated log file ----------------
echo "[3/5] Configuring rsyslog to route outbound logs to $LOG_FILE..."

cat > /etc/rsyslog.d/10-outbound-connections.conf << 'RSYSLOG_EOF'
# Route outbound connection logs to a dedicated file
# Matches allowed (OUTBOUND_CONN), blocked (OUTBOUND_BLOCKED),
# and Ollama-specific (OLLAMA_OUTBOUND) entries
:msg, contains, "OUTBOUND_CONN"    -/var/log/outbound-connections.log
:msg, contains, "OUTBOUND_BLOCKED" -/var/log/outbound-connections.log
:msg, contains, "OLLAMA_OUTBOUND"  -/var/log/outbound-connections.log

# Optional: stop processing these messages so they don't also flood /var/log/messages
# Uncomment the lines below if you want ONLY the dedicated file:
# :msg, contains, "OUTBOUND_CONN"    stop
# :msg, contains, "OUTBOUND_BLOCKED" stop
# :msg, contains, "OLLAMA_OUTBOUND"  stop
RSYSLOG_EOF

# Create the log file with proper permissions
touch "$LOG_FILE"
chmod 640 "$LOG_FILE"
chown root:root "$LOG_FILE"

# Restart rsyslog
systemctl restart rsyslog
echo "    Done. Logs will be written to $LOG_FILE"

# --- Step 4: Set up logrotate ------------------------------------------------
echo "[4/5] Configuring logrotate..."

cat > /etc/logrotate.d/outbound-connections << LOGROTATE_EOF
$LOG_FILE {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    postrotate
        /usr/bin/systemctl restart rsyslog > /dev/null 2>&1 || true
    endscript
}
LOGROTATE_EOF

if [[ "$INSTALL_CONNTRACK" == true ]]; then
    cat > /etc/logrotate.d/conntrack-outbound << LOGROTATE2_EOF
$CONNTRACK_LOG {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 0640 root root
    postrotate
        /usr/bin/systemctl restart $CONNTRACK_SERVICE_NAME > /dev/null 2>&1 || true
    endscript
}
LOGROTATE2_EOF
fi

echo "    Done. Logs rotate daily, kept for 30 days."

# --- Step 5: Optional conntrack setup ----------------------------------------
if [[ "$INSTALL_CONNTRACK" == true ]]; then
    echo "[5/5] Installing conntrack-tools and setting up structured logging..."

    dnf install -y conntrack-tools > /dev/null 2>&1

    # Create a systemd service that streams new outbound connections to a log
    cat > /etc/systemd/system/${CONNTRACK_SERVICE_NAME}.service << SERVICE_EOF
[Unit]
Description=Log outbound connections via conntrack
After=network.target firewalld.service

[Service]
Type=simple
# Log only NEW connections, output timestamps, filter to non-loopback
ExecStart=/bin/bash -c '/usr/sbin/conntrack -E -e NEW -o timestamp 2>&1 | grep --line-buffered -v "src=127.0.0.1" >> $CONNTRACK_LOG'
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
SERVICE_EOF

    touch "$CONNTRACK_LOG"
    chmod 640 "$CONNTRACK_LOG"

    systemctl daemon-reload
    systemctl enable --now "$CONNTRACK_SERVICE_NAME"
    echo "    Done. conntrack service started."
    echo "    Structured logs: $CONNTRACK_LOG"
else
    echo "[5/5] Skipping conntrack (use --with-conntrack to enable)."
fi

# --- Summary ------------------------------------------------------------------
echo ""
echo "============================================="
echo " Setup Complete!"
echo "============================================="
echo ""
echo " Firewalld logs:   $LOG_FILE"
if [[ "$INSTALL_CONNTRACK" == true ]]; then
echo " Conntrack logs:   $CONNTRACK_LOG"
fi
echo ""
echo " Verify it's working:"
echo "   tail -f $LOG_FILE"
echo "   curl -s https://example.com > /dev/null"
echo "   # You should see a log entry appear"
echo ""
echo " View current direct rules:"
echo "   firewall-cmd --direct --get-all-rules"
echo ""
echo " To remove all outbound logging later:"
echo "   firewall-cmd --permanent --direct --remove-rules ipv4 filter OUTPUT"
echo "   firewall-cmd --permanent --direct --remove-rules ipv6 filter OUTPUT"
echo "   firewall-cmd --reload"
echo "   rm -f /etc/rsyslog.d/10-outbound-connections.conf"
echo "   systemctl restart rsyslog"
if [[ "$INSTALL_CONNTRACK" == true ]]; then
echo "   systemctl disable --now $CONNTRACK_SERVICE_NAME"
echo "   rm -f /etc/systemd/system/${CONNTRACK_SERVICE_NAME}.service"
fi
echo ""
echo " Log format (firewalld):"
echo '   OUTBOUND_CONN_TCP: ... SRC=10.0.0.5 DST=104.18.32.7 DPT=443 ...'
echo '   OLLAMA_OUTBOUND_TCP: ... DST=<ip> DPT=<port> ...  <-- Ollama phoning home!'
echo ""
echo " What to grep for when auditing LLM activity:"
echo '   # === THE IMPORTANT ONE: Is Ollama calling out? ==='
echo '   grep "OLLAMA_OUTBOUND" /var/log/outbound-connections.log'
echo ""
echo '   # General outbound auditing'
echo '   grep "DPT=443" /var/log/outbound-connections.log   # HTTPS calls'
echo '   grep "DPT=80"  /var/log/outbound-connections.log   # HTTP calls'
echo '   # Look for unexpected DST IPs or unusual ports'
echo ""
echo " NOTE: Local traffic to Ollama (localhost:$OLLAMA_PORT) is excluded"
echo "       from logging to reduce noise. Only Ollama's OWN outbound"
echo "       connections to external hosts are logged."
echo ""
