# GPU Farm Deployment Guide with Discord Webhooks

This guide will help you deploy the Solana vanity address generator to multiple GPU instances with Discord webhook notifications.

## Prerequisites

1. **Discord Webhook URL**
   - Go to your Discord server
   - Server Settings → Integrations → Webhooks → New Webhook
   - Copy the webhook URL (looks like: `https://discord.com/api/webhooks/...`)

2. **GPU Provider Account**
   - Sign up for [Vast.ai](https://vast.ai) or [RunPod](https://runpod.io)

## Quick Start (Vast.ai)

### Option 1: Using Pre-built Docker Image (Easiest)

1. **Build and Push Docker Image** (one time setup):
   ```bash
   cd new/SolVanityCL-master
   docker build -t your-dockerhub-username/solvanitycl-webhook:latest .
   docker push your-dockerhub-username/solvanitycl-webhook:latest
   ```

2. **Create a startup script** on your local machine:
   ```bash
   # Save this as run_search.sh
   #!/bin/bash
   export WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_HERE"
   export SEARCH_PREFIX="YOUR_PREFIX_HERE"  # e.g., "AAAAAAAA"
   export INSTANCE_NAME="GPU-$(hostname)"

   cd /app
   python3 main.py search-pubkey \
     --starts-with "$SEARCH_PREFIX" \
     --webhook-url "$WEBHOOK_URL" \
     --output-dir ~/results
   ```

3. **Launch GPU instances on Vast.ai**:
   - Go to https://vast.ai
   - Click "Search" → Filter by GPU type and price
   - Select 50-100 instances
   - In the "Docker Image" field: `your-dockerhub-username/solvanitycl-webhook:latest`
   - In "On-Start Script" field, paste:
     ```bash
     export WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_HERE"
     export SEARCH_PREFIX="AAAAAAAA"
     export INSTANCE_NAME="GPU-$(hostname)"
     cd /app && python3 main.py search-pubkey --starts-with "$SEARCH_PREFIX" --webhook-url "$WEBHOOK_URL" --output-dir ~/results
     ```
   - Click "Rent" on each instance

4. **Monitor Discord** - Wait for notifications! 🎉

### Option 2: Using Vast.ai CLI (Automated)

1. **Install Vast.ai CLI**:
   ```bash
   pip install vastai
   vastai set api-key YOUR_API_KEY
   ```

2. **Search for available GPUs**:
   ```bash
   # Find 100 cheapest RTX 3090s
   vastai search offers 'gpu_name=RTX_3090 num_gpus=1' --order 'dph+'
   ```

3. **Create a deployment script** (`deploy.sh`):
   ```bash
   #!/bin/bash

   WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_HERE"
   SEARCH_PREFIX="AAAAAAAA"
   DOCKER_IMAGE="your-dockerhub-username/solvanitycl-webhook:latest"
   NUM_INSTANCES=50

   # Find best offers
   vastai search offers 'gpu_name=RTX_3090 num_gpus=1 reliability>0.95' \
     --order 'dph+' --limit $NUM_INSTANCES --raw > offers.json

   # Rent each instance
   cat offers.json | jq -r '.[] | .id' | while read offer_id; do
     vastai create instance $offer_id \
       --image $DOCKER_IMAGE \
       --disk 10 \
       --onstart-cmd "export WEBHOOK_URL='$WEBHOOK_URL' SEARCH_PREFIX='$SEARCH_PREFIX' INSTANCE_NAME='GPU-\$(hostname)' && cd /app && python3 main.py search-pubkey --starts-with \$SEARCH_PREFIX --webhook-url \$WEBHOOK_URL --output-dir ~/results"
     echo "Launched instance with offer $offer_id"
     sleep 1
   done
   ```

4. **Run deployment**:
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

5. **Monitor and stop**:
   ```bash
   # List your instances
   vastai show instances

   # Stop all instances when you find your address
   vastai destroy instance $(vastai show instances --raw | jq -r '.[].id')
   ```

## Manual Deployment (SSH into each instance)

If you prefer manual control:

1. **Rent a GPU instance** on Vast.ai with image `loerfy/sol_vanity_cl:latest`

2. **SSH into the instance**:
   ```bash
   ssh -p PORT root@IP_ADDRESS
   ```

3. **Update the code** (if using modified version):
   ```bash
   cd /app
   # Copy your modified files here or pull from git
   ```

4. **Install requests library** (if not in Docker image):
   ```bash
   pip3 install requests
   ```

5. **Run the search**:
   ```bash
   export WEBHOOK_URL="YOUR_DISCORD_WEBHOOK_URL_HERE"
   export INSTANCE_NAME="GPU-$(hostname)"

   python3 main.py search-pubkey \
     --starts-with "AAAAAAAA" \
     --webhook-url "$WEBHOOK_URL" \
     --output-dir ~/results
   ```

## Discord Notification Format (Secure!)

**IMPORTANT:** For security, only the PUBLIC key is sent to Discord, NOT the private key!

When a match is found, you'll receive a Discord message with:
- 🎉 Title: "Vanity Address Found!"
- Public key (base58) - safe to share
- Instance identifier (hostname/GPU ID)
- Keypair file location on the instance
- Instructions to SSH in and retrieve it

### Retrieving Your Keypair Securely

**Option 1: Automated Script (Easiest)**
```bash
./retrieve_keypair.sh <instance_ip> <ssh_port> <keypair_filename.json>
```

**Option 2: Manual SSH**
```bash
# SSH into the instance from Discord notification
ssh -p <port> root@<ip>

# Find and display the keypair
cat /root/results/<pubkey>.json

# Copy to your local machine
scp -P <port> root@<ip>:/root/results/<pubkey>.json ./
```

**Option 3: Vast.ai File Browser**
- Go to your Vast.ai instance
- Click "Files"
- Navigate to `/root/results/`
- Download the `.json` file

## 🔒 Security Best Practices

1. **Never share your webhook URL publicly** - anyone with it can spam your Discord
2. **Private keys never leave the GPU instance via Discord** - only sent via secure SSH
3. **Immediately destroy all GPU instances** after retrieving your keypair
4. **Store keypairs offline** in an encrypted location
5. **Use a hardware wallet** for storing significant amounts
6. **Delete Discord messages** containing public keys if you prefer privacy
7. **Rotate webhook URLs** if you suspect they've been compromised

### Why This Is Secure

✅ Private key stays on the GPU instance (not in Discord logs)
✅ You retrieve it via encrypted SSH connection
✅ Discord only sees the public key (which is safe to share)
✅ Instance is destroyed after retrieval (no data remnants)

## Cost Optimization Tips

1. **Use RTX 3090s** - Best price/performance (~$0.13/hr)
2. **Set max price** - Use Vast.ai filters to stay under budget
3. **Kill all instances immediately** when you get the Discord notification
4. **Search for multiple patterns** - No performance penalty, increases your chances

## Troubleshooting

### No Discord notifications?
- Check webhook URL is correct
- Verify `requests` library is installed: `pip3 list | grep requests`
- Check logs: Discord webhook errors will appear in the instance logs

### Performance lower than expected?
- Check GPU utilization: `nvidia-smi`
- Ensure CUDA version ≥ 12.0
- Try different `--iteration-bits` values (24, 26, 28, 30, 32)

### Instance keeps crashing?
- Check OpenCL is working: `python3 main.py show-device`
- Verify GPU drivers: `nvidia-smi`
- Check Docker logs for errors

## Example: Finding an 8-character vanity address

With 100× RTX 3090s at $0.13/hr each:
- Cost: $13/hr
- Estimated time: ~9 hours
- Total cost: ~$117

Happy hunting! 🚀
