#!/bin/bash
# AgentOS Uninstaller
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo ""
echo "AgentOS — Uninstalling system daemon..."
echo ""

OS=$(uname -s | tr '[:upper:]' '[:lower:]')

if [ "$OS" = "darwin" ]; then
    PLIST="$HOME/Library/LaunchAgents/com.agentos.daemon.plist"
    launchctl unload -w "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    echo -e "${GREEN}✓ LaunchAgent removed${NC}"

elif [ "$OS" = "linux" ]; then
    sudo systemctl stop agentos 2>/dev/null || true
    sudo systemctl disable agentos 2>/dev/null || true
    sudo rm -f /etc/systemd/system/agentos.service
    sudo systemctl daemon-reload
    echo -e "${GREEN}✓ systemd service removed${NC}"
fi

echo ""
read -p "Remove data directory? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
    rm -rf "$PROJECT_DIR/data"
    echo -e "${GREEN}✓ Data removed${NC}"
fi

echo ""
echo -e "${GREEN}AgentOS uninstalled.${NC}"
