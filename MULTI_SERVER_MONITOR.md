# Multi-Server Monitoring Guide

Track total search speed across multiple servers in real-time!

## Setup

### 1. Start the Monitoring Server

Choose ONE server to run the monitoring dashboard (can be your local machine, a cheap VPS, or one of your vast.ai instances):

```bash
# Install dependencies
pip install flask

# Start monitoring server
python3 monitor_server.py
```

The dashboard will be available at `http://YOUR_SERVER_IP:5000`

**Port 5000 must be accessible** from all your search servers.

### 2. Run Searches on Multiple Servers

On each vast.ai server, run the search with monitoring enabled:

```bash
python3 main.py search-pubkey \
  --starts-with haqq \
  --ends-with qqqq \
  --monitor-url http://MONITOR_SERVER_IP:5000/report \
  --server-id vast-server-1
```

**Important:**
- Replace `MONITOR_SERVER_IP` with your monitoring server's IP
- Give each server a unique `--server-id` (e.g., vast-1, vast-2, vast-3)

## Dashboard Features

Visit `http://MONITOR_SERVER_IP:5000` to see:

- **Total Speed** across all servers
- **Active Servers** count
- **Total GPUs** across all servers
- **Per-server stats** with status (ACTIVE/OFFLINE)
- **Auto-refresh** every 5 seconds

### ETA Calculation

Add search pattern to URL for ETA:

```
http://MONITOR_SERVER_IP:5000/?prefix_len=4&suffix_len=4
```

This shows:
- ETA for 50% probability
- ETA for 90% probability

## Example Setup

**Monitoring Server (your local machine or VPS):**
```bash
python3 monitor_server.py
# Dashboard at http://192.168.1.100:5000
```

**Vast.ai Server 1 (8x RTX 4090):**
```bash
python3 main.py search-pubkey \
  --starts-with haqq \
  --ends-with qqqq \
  --monitor-url http://192.168.1.100:5000/report \
  --server-id vast-1
```

**Vast.ai Server 2 (8x RTX 4090):**
```bash
python3 main.py search-pubkey \
  --starts-with haqq \
  --ends-with qqqq \
  --monitor-url http://192.168.1.100:5000/report \
  --server-id vast-2
```

**Vast.ai Server 3 (8x RTX 4090):**
```bash
python3 main.py search-pubkey \
  --starts-with haqq \
  --ends-with qqqq \
  --monitor-url http://192.168.1.100:5000/report \
  --server-id vast-3
```

Dashboard will show:
```
Total Speed: 1,848 MH/s
Active Servers: 3
Total GPUs: 24
ETA 50%: 2d 1h
ETA 90%: 6d 18h
```

## API Endpoints

### POST /report
Report speed from a search server.

**Request:**
```json
{
  "server_id": "vast-1",
  "speed": 616.50,
  "gpu_count": 8
}
```

**Response:**
```json
{
  "status": "ok",
  "total_speed": 1848.25
}
```

### GET /stats
Get aggregated statistics.

**Response:**
```json
{
  "total_speed": 1848.25,
  "active_servers": 3,
  "total_gpus": 24,
  "servers": { ... }
}
```

## Troubleshooting

**Server shows as OFFLINE:**
- Check if search is still running
- Verify monitor-url is correct
- Check firewall/network connectivity
- Server auto-removed after 60s without updates

**Can't access dashboard:**
- Check monitoring server is running
- Verify port 5000 is open
- Try `http://0.0.0.0:5000` locally first

**Speeds not updating:**
- Check search servers have `--monitor-url` and `--server-id`
- Verify monitor server IP is correct
- Check logs for connection errors

## Notes

- Servers report speed every 10 seconds
- Offline servers removed after 60 seconds
- Dashboard auto-refreshes every 5 seconds
- No authentication required (add nginx proxy if needed)
- All servers search independently (no coordination needed)
