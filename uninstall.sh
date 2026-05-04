#!/usr/bin/env bash
# =============================================================================
# uninstall.sh
#
# Fully removes the egress-monitor stack:
#   - Firewalld rich rules and direct rules
#   - rsyslog routing config
#   - logrotate configs
#   - Installed scripts and baseline
#   - Log files and audit reports
#   - conntrack-logger service (if present)
#   - Crontab entry
#
# Usage:
#   sudo bash uninstall.sh [--keep-logs] [--dry-run]
#
#   --keep-logs   Leave log files and reports in place
#   --dry-run     Show what would be removed without doing it
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
BOLD='\033[1m'
NC='\033[0m'

KEEP_LOGS=false
DRY_RUN=false

for arg in "$@"; do
    case "$arg" in
        --keep-logs) KEEP_LOGS=true ;;
        --dry-run)   DRY_RUN=true ;;
        --help|-h)
            echo "Usage: sudo bash $0 [--keep-logs] [--dry-run]"
            echo ""
            echo "  --keep-logs   Keep log files and audit reports"
            echo "  --dry-run     Show what would be removed without doing it"
            exit 0
            ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}ERROR:${NC} Must run as root (sudo)."
    exit 1
fi

echo ""
echo -e "${BOLD}=============================================${NC}"
echo -e "${BOLD} Egress Monitor — Uninstall${NC}"
echo -e "${BOLD}=============================================${NC}"
echo ""

if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW}DRY RUN — nothing will be changed.${NC}"
    echo ""
fi

# Helper: remove a file if it exists
remove_file() {
    local path="$1"
    if [[ -e "$path" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo -e "  ${DIM}would remove${NC} $path"
        else
            rm -f "$path"
            echo -e "  ${GREEN}removed${NC} $path"
        fi
    else
        echo -e "  ${DIM}not found${NC} $path"
    fi
}

# Helper: remove a directory if it exists
remove_dir() {
    local path="$1"
    if [[ -d "$path" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo -e "  ${DIM}would remove${NC} $path/"
        else
            rm -rf "$path"
            echo -e "  ${GREEN}removed${NC} $path/"
        fi
    else
        echo -e "  ${DIM}not found${NC} $path/"
    fi
}

# --- 1. Firewalld rules ------------------------------------------------------
echo -e "${BOLD}[1/6] Firewalld rules${NC}"

if systemctl is-active --quiet firewalld 2>/dev/null; then
    ACTIVE_ZONE=$(firewall-cmd --get-default-zone 2>/dev/null || echo "public")

    # Remove rich rule for OUTBOUND_CONN logging
    RICH_RULE='rule family="ipv4" source address="0.0.0.0/0" log prefix="OUTBOUND_CONN " level="info" limit value="100/m"'
    if firewall-cmd --permanent --zone="$ACTIVE_ZONE" --query-rich-rule="$RICH_RULE" 2>/dev/null; then
        if [[ "$DRY_RUN" == true ]]; then
            echo -e "  ${DIM}would remove rich rule from zone ${ACTIVE_ZONE}${NC}"
        else
            firewall-cmd --permanent --zone="$ACTIVE_ZONE" --remove-rich-rule="$RICH_RULE" 2>/dev/null || true
            echo -e "  ${GREEN}removed${NC} rich rule from zone ${ACTIVE_ZONE}"
        fi
    else
        echo -e "  ${DIM}no rich rule found${NC}"
    fi

    # Remove all direct rules on OUTPUT chain
    has_ipv4=$(firewall-cmd --permanent --direct --get-all-rules 2>/dev/null | grep -c "ipv4 filter OUTPUT" || true)
    has_ipv6=$(firewall-cmd --permanent --direct --get-all-rules 2>/dev/null | grep -c "ipv6 filter OUTPUT" || true)

    if [[ "$has_ipv4" -gt 0 || "$has_ipv6" -gt 0 ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            echo -e "  ${DIM}would remove ${has_ipv4} ipv4 + ${has_ipv6} ipv6 direct OUTPUT rules${NC}"
        else
            firewall-cmd --permanent --direct --remove-rules ipv4 filter OUTPUT 2>/dev/null || true
            firewall-cmd --permanent --direct --remove-rules ipv6 filter OUTPUT 2>/dev/null || true
            echo -e "  ${GREEN}removed${NC} direct OUTPUT rules (ipv4 + ipv6)"
        fi
    else
        echo -e "  ${DIM}no direct OUTPUT rules found${NC}"
    fi

    # Reload firewalld
    if [[ "$DRY_RUN" != true ]]; then
        firewall-cmd --reload 2>/dev/null
        echo -e "  ${GREEN}firewalld reloaded${NC}"
    fi
else
    echo -e "  ${DIM}firewalld not running — skipping${NC}"
fi

# --- 2. Conntrack service (if present) ----------------------------------------
echo -e "${BOLD}[2/6] Conntrack logger service${NC}"

CONNTRACK_SERVICE="conntrack-logger"
CONNTRACK_UNIT="/etc/systemd/system/${CONNTRACK_SERVICE}.service"

if [[ -f "$CONNTRACK_UNIT" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "  ${DIM}would stop and remove ${CONNTRACK_SERVICE}${NC}"
    else
        systemctl disable --now "$CONNTRACK_SERVICE" 2>/dev/null || true
        rm -f "$CONNTRACK_UNIT"
        systemctl daemon-reload
        echo -e "  ${GREEN}removed${NC} ${CONNTRACK_SERVICE} service"
    fi
else
    echo -e "  ${DIM}not installed${NC}"
fi

# --- 3. rsyslog config -------------------------------------------------------
echo -e "${BOLD}[3/6] rsyslog config${NC}"

RSYSLOG_CONF="/etc/rsyslog.d/10-outbound-connections.conf"
if [[ -f "$RSYSLOG_CONF" ]]; then
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "  ${DIM}would remove${NC} ${RSYSLOG_CONF}"
    else
        rm -f "$RSYSLOG_CONF"
        systemctl restart rsyslog 2>/dev/null || true
        echo -e "  ${GREEN}removed${NC} ${RSYSLOG_CONF}"
        echo -e "  ${GREEN}rsyslog restarted${NC}"
    fi
else
    echo -e "  ${DIM}not found${NC}"
fi

# --- 4. Logrotate configs ----------------------------------------------------
echo -e "${BOLD}[4/6] Logrotate configs${NC}"

remove_file /etc/logrotate.d/outbound-connections
remove_file /etc/logrotate.d/conntrack-outbound

# --- 5. Installed scripts and baseline ----------------------------------------
echo -e "${BOLD}[5/6] Installed scripts and baseline${NC}"

remove_file /usr/local/bin/outbound_audit.py
remove_file /usr/local/bin/outbound_audit_cron.sh
remove_file /etc/outbound-baseline.json

# --- 6. Log files and reports -------------------------------------------------
echo -e "${BOLD}[6/6] Log files and reports${NC}"

if [[ "$KEEP_LOGS" == true ]]; then
    echo -e "  ${YELLOW}--keep-logs set — skipping log removal${NC}"
else
    remove_file /var/log/outbound-connections.log
    remove_file /var/log/conntrack-outbound.log
    remove_dir /var/log/outbound-audit-reports
fi

# --- Crontab entry ------------------------------------------------------------
echo ""
echo -e "${BOLD}Crontab check${NC}"

if crontab -l 2>/dev/null | grep -q "outbound_audit_cron.sh"; then
    if [[ "$DRY_RUN" == true ]]; then
        echo -e "  ${DIM}would remove crontab entry for outbound_audit_cron.sh${NC}"
    else
        crontab -l 2>/dev/null | grep -v "outbound_audit_cron.sh" | crontab -
        echo -e "  ${GREEN}removed${NC} crontab entry"
    fi
else
    echo -e "  ${DIM}no crontab entry found${NC}"
fi

# --- Summary ------------------------------------------------------------------
echo ""
echo -e "${BOLD}=============================================${NC}"
if [[ "$DRY_RUN" == true ]]; then
    echo -e "${YELLOW} Dry run complete. Re-run without --dry-run to apply.${NC}"
else
    echo -e "${GREEN} Uninstall complete.${NC}"
fi
echo -e "${BOLD}=============================================${NC}"
echo ""
