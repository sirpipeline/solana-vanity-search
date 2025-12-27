#!/bin/bash
set -e

# Configuration
REPO_URL="https://github.com/sirpipeline/solana-vanity-search"
STARTS_WITH="haqq"
ENDS_WITH="qqqq"
MONITOR_URL="https://gaylene-platiest-punctually.ngrok-free.dev/report"

# Install dependencies
apt update -y
apt install -y python3 python3-pip python3-venv git curl jq

# Create workspace
mkdir -p /workspace
cd /workspace
rm -rf solana-vanity-search || true
git clone "$REPO_URL"
cd solana-vanity-search

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Get vast.ai metadata from environment variables
# Vast.ai provides these in the template/instance settings
# You can pass these as environment variables when creating the instance:
# -e VAST_INSTANCE_ID=12345 -e VAST_HOST_ID=67890 -e VAST_MACHINE_ID=11111

export VAST_INSTANCE_ID="${VAST_INSTANCE_ID:-N/A}"
export VAST_HOST_ID="${VAST_HOST_ID:-N/A}"
export VAST_MACHINE_ID="${VAST_MACHINE_ID:-N/A}"

# Set server ID
SERVER_ID="${VAST_CONTAINER_ID:-${VAST_INSTANCE_ID:-$(hostname)}}"

echo "=========================================="
echo "Starting Solana Vanity Search"
echo "=========================================="
echo "Instance ID: $VAST_INSTANCE_ID"
echo "Host ID: $VAST_HOST_ID"
echo "Machine ID: $VAST_MACHINE_ID"
echo "Server ID: $SERVER_ID"
echo "Monitor URL: $MONITOR_URL"
echo "=========================================="

# Start the search
nohup python3 main.py search-pubkey \
  --starts-with "$STARTS_WITH" \
  --ends-with "$ENDS_WITH" \
  --monitor-url "$MONITOR_URL" \
  --server-id "$SERVER_ID" \
  > /workspace/search.log 2>&1 &

echo "Search started! Check logs: tail -f /workspace/search.log"
