#!/bin/bash
# Helper script to retrieve keypair from GPU instance after Discord notification
# Usage: ./retrieve_keypair.sh <instance_ip> <ssh_port> <keypair_filename>

set -e

if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <instance_ip> <ssh_port> <keypair_filename>"
    echo ""
    echo "Example: $0 185.125.56.78 12345 haqqABCD1234xyz.json"
    echo ""
    echo "After Discord notifies you:"
    echo "1. Note the instance name and keypair filename"
    echo "2. Find the instance IP and SSH port from Vast.ai dashboard"
    echo "3. Run this script to securely copy the keypair"
    exit 1
fi

INSTANCE_IP=$1
SSH_PORT=$2
KEYPAIR_FILE=$3
LOCAL_DIR="./found_keypairs"

echo "========================================="
echo "Retrieving Keypair from GPU Instance"
echo "========================================="
echo "Instance IP: $INSTANCE_IP"
echo "SSH Port: $SSH_PORT"
echo "Keypair File: $KEYPAIR_FILE"
echo "========================================="

# Create local directory
mkdir -p "$LOCAL_DIR"

# Try common locations where the keypair might be saved
REMOTE_PATHS=(
    "/root/results/$KEYPAIR_FILE"
    "/app/results/$KEYPAIR_FILE"
    "/root/$KEYPAIR_FILE"
    "/app/$KEYPAIR_FILE"
    "~/$KEYPAIR_FILE"
)

echo "Attempting to copy keypair from instance..."

SUCCESS=false
for REMOTE_PATH in "${REMOTE_PATHS[@]}"; do
    echo "Trying: $REMOTE_PATH"
    if scp -P "$SSH_PORT" "root@$INSTANCE_IP:$REMOTE_PATH" "$LOCAL_DIR/" 2>/dev/null; then
        SUCCESS=true
        echo "✅ Successfully copied keypair!"
        break
    fi
done

if [ "$SUCCESS" = false ]; then
    echo ""
    echo "❌ Could not find keypair in common locations."
    echo "Manual retrieval:"
    echo "  ssh -p $SSH_PORT root@$INSTANCE_IP"
    echo "  find / -name '$KEYPAIR_FILE' 2>/dev/null"
    exit 1
fi

# Verify the keypair
LOCAL_FILE="$LOCAL_DIR/$KEYPAIR_FILE"
if [ -f "$LOCAL_FILE" ]; then
    echo ""
    echo "========================================="
    echo "✅ Keypair Retrieved Successfully!"
    echo "========================================="
    echo "Location: $LOCAL_FILE"
    echo ""

    # Extract public key from filename (it's the filename without .json)
    PUBKEY="${KEYPAIR_FILE%.json}"
    echo "Public Key: $PUBKEY"
    echo ""

    # Show file size as basic validation
    FILE_SIZE=$(wc -c < "$LOCAL_FILE")
    echo "File size: $FILE_SIZE bytes (should be ~200-300 bytes)"
    echo ""

    if command -v solana-keygen &> /dev/null; then
        echo "Verifying with solana-keygen..."
        solana-keygen pubkey "$LOCAL_FILE"
    else
        echo "To verify: solana-keygen pubkey $LOCAL_FILE"
    fi

    echo ""
    echo "⚠️  SECURITY REMINDERS:"
    echo "1. Destroy all GPU instances immediately"
    echo "2. Store this keypair in a secure, offline location"
    echo "3. Consider using a hardware wallet for large amounts"
    echo "4. Delete the keypair from the GPU instances if not auto-destroyed"
    echo ""
else
    echo "❌ Error: File not found after copy"
    exit 1
fi
