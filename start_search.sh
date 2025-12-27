#!/bin/bash
# Startup script for GPU farm deployment
# Usage: Set environment variables and run this script

# Required environment variables:
# - WEBHOOK_URL: Your Discord webhook URL
# - SEARCH_PREFIX: The vanity prefix you're looking for (e.g., "AAAAAAAA")

# Optional environment variables:
# - INSTANCE_NAME: Identifier for this instance (default: hostname)
# - OUTPUT_DIR: Where to save keypairs (default: /root/results)
# - ITERATION_BITS: Iteration bits for performance tuning (default: 24)

set -e  # Exit on error

# Default values
INSTANCE_NAME=${INSTANCE_NAME:-"GPU-$(hostname)"}
OUTPUT_DIR=${OUTPUT_DIR:-"/root/results"}
ITERATION_BITS=${ITERATION_BITS:-24}

# Validate required variables
if [ -z "$WEBHOOK_URL" ]; then
    echo "ERROR: WEBHOOK_URL environment variable is not set"
    echo "Example: export WEBHOOK_URL='https://discord.com/api/webhooks/...'"
    exit 1
fi

if [ -z "$SEARCH_PREFIX" ]; then
    echo "ERROR: SEARCH_PREFIX environment variable is not set"
    echo "Example: export SEARCH_PREFIX='AAAAAAAA'"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Log configuration
echo "========================================="
echo "Solana Vanity Address Search"
echo "========================================="
echo "Instance Name: $INSTANCE_NAME"
echo "Search Prefix: $SEARCH_PREFIX"
echo "Output Dir: $OUTPUT_DIR"
echo "Iteration Bits: $ITERATION_BITS"
echo "Webhook URL: ${WEBHOOK_URL:0:50}..."
echo "========================================="

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    echo "GPU Info:"
    nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
    echo "========================================="
fi

# Change to app directory
cd /app

# Show available OpenCL devices
echo "Available OpenCL devices:"
python3 main.py show-device
echo "========================================="

# Start search
echo "Starting search..."
export INSTANCE_NAME
python3 main.py search-pubkey \
    --starts-with "$SEARCH_PREFIX" \
    --webhook-url "$WEBHOOK_URL" \
    --output-dir "$OUTPUT_DIR" \
    --iteration-bits "$ITERATION_BITS"

echo "Search completed!"
