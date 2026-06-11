#!/bin/bash
# Phone Agents - Start Script
# Runs the backend server which serves both API and frontend

set -e

cd "$(dirname "$0")"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}        📱 Phone Agents - Starting Up           ${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check for virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r backend/requirements.txt -q

echo ""
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Get local IP for phone access
LOCAL_IP=$(ipconfig getifaddr en0 2>/dev/null || echo "localhost")

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  🌐 Open on your iPhone:${NC}"
echo -e "${GREEN}  http://${LOCAL_IP}:8000${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}  Agents are waking up...${NC}"
echo ""

# Start the server
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
