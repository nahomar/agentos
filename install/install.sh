#!/bin/bash
# AgentOS Installer — Installs AgentOS as a system daemon
set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}       AgentOS — System Daemon Installer       ${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo -e "${RED}✗ Python 3 not found. Install from https://python.org${NC}"
    exit 1
fi
PYTHON_VER=$(python3 --version 2>&1)
echo -e "${GREEN}✓ $PYTHON_VER${NC}"

# Create venv
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Install deps
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r "$PROJECT_DIR/backend/requirements.txt" -q 2>&1 | tail -1
pip install cryptography psutil -q 2>&1 | tail -1
echo -e "${GREEN}✓ Dependencies installed${NC}"

# Detect OS
OS=$(uname -s | tr '[:upper:]' '[:lower:]')
echo -e "${GREEN}✓ Platform: $OS${NC}"

# Find free port
PORT=8000
for p in 8000 8001 8002 8003 8004 8005; do
    if ! lsof -ti:$p &>/dev/null; then
        PORT=$p
        break
    fi
done
echo -e "${GREEN}✓ Using port: $PORT${NC}"

# Save port
mkdir -p "$PROJECT_DIR/data"
echo "$PORT" > "$PROJECT_DIR/data/port"

if [ "$OS" = "darwin" ]; then
    # macOS LaunchAgent
    PLIST_PATH="$HOME/Library/LaunchAgents/com.agentos.daemon.plist"
    VENV_PYTHON="$VENV_DIR/bin/python3"

    # Unload existing
    launchctl unload -w "$PLIST_PATH" 2>/dev/null || true

    cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.agentos.daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_PYTHON</string>
    <string>-m</string>
    <string>uvicorn</string>
    <string>backend.main:app</string>
    <string>--host</string>
    <string>0.0.0.0</string>
    <string>--port</string>
    <string>$PORT</string>
  </array>
  <key>WorkingDirectory</key>
  <string>$PROJECT_DIR</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/agentos.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/agentos-error.log</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONUNBUFFERED</key>
    <string>1</string>
    <key>PATH</key>
    <string>${VENV_DIR}/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict>
</plist>
PLIST

    launchctl load -w "$PLIST_PATH"
    echo -e "${GREEN}✓ LaunchAgent installed and started${NC}"
    echo -e "  Logs: tail -f /tmp/agentos.log"

elif [ "$OS" = "linux" ]; then
    # Linux systemd
    SERVICE_FILE="/tmp/agentos.service"
    VENV_PYTHON="$VENV_DIR/bin/python3"
    USER=$(whoami)

    cat > "$SERVICE_FILE" <<SERVICE
[Unit]
Description=AgentOS — Agentic Operating System
After=network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=$USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$VENV_PYTHON -m uvicorn backend.main:app --host 0.0.0.0 --port $PORT
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
SERVICE

    sudo cp "$SERVICE_FILE" /etc/systemd/system/agentos.service
    sudo systemctl daemon-reload
    sudo systemctl enable agentos
    sudo systemctl start agentos
    echo -e "${GREEN}✓ systemd service installed and started${NC}"
    echo -e "  Logs: journalctl -u agentos -f"
fi

# Get local IP
LOCAL_IP=$(python3 -c "
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
try:
    s.connect(('8.8.8.8', 80))
    print(s.getsockname()[0])
except: print('localhost')
finally: s.close()
")

echo ""
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo -e "${GREEN}  ✓ AgentOS daemon is running!                ${NC}"
echo -e "${GREEN}═══════════════════════════════════════════════${NC}"
echo ""
echo -e "  ${BLUE}Open on your phone:${NC}"
echo -e "  ${BLUE}http://${LOCAL_IP}:${PORT}${NC}"
echo ""
echo -e "  Manage:"
echo -e "    ./agentos status   — check health"
echo -e "    ./agentos logs     — view logs"
echo -e "    ./agentos stop     — stop daemon"
echo -e "    ./agentos restart  — restart daemon"
echo ""
