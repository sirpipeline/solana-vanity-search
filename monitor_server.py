#!/usr/bin/env python3
"""
Monitoring server to aggregate speeds from multiple vanity search servers.
Run this on a server accessible to all your vast.ai instances.
"""

from flask import Flask, request, jsonify, render_template_string
import time
from collections import defaultdict
import threading

app = Flask(__name__)

# Store speeds: {server_id: {"speed": MH/s, "timestamp": time, "gpu_count": N}}
server_speeds = {}
# Store matches: {server_id: {"timestamp": time, "prefix": str, "suffix": str}}
matches_found = {}
server_lock = threading.Lock()

# Clean up stale servers every 30 seconds
STALE_TIMEOUT = 60  # Consider server offline after 60s without update

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Vanity Address Search Monitor</title>
    <meta http-equiv="refresh" content="5">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #1e1e1e; color: #fff; }
        h1 { color: #4CAF50; }
        .total { font-size: 2em; color: #4CAF50; margin: 20px 0; }
        .stats { background: #2d2d2d; padding: 20px; border-radius: 10px; margin: 20px 0; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #4CAF50; color: white; }
        tr:hover { background: #3d3d3d; }
        .offline { opacity: 0.5; color: #f44336; }
        .eta { font-size: 1.2em; color: #2196F3; margin: 10px 0; }
    </style>
</head>
<body>
    <h1>🚀 Vanity Address Search Monitor</h1>
    <div class="stats">
        <div class="total">Total Speed: {{ "%.2f"|format(total_speed) }} MH/s</div>
        <div class="eta">Active Servers: {{ active_count }}</div>
        <div class="eta">Total GPUs: {{ total_gpus }}</div>
        {% if eta_50 %}
        <div class="eta">ETA 50%: {{ eta_50 }}</div>
        <div class="eta">ETA 90%: {{ eta_90 }}</div>
        {% endif %}
    </div>

    {% if matches|length > 0 %}
    <div style="background: #4CAF50; padding: 20px; border-radius: 10px; margin: 20px 0; font-size: 1.5em;">
        🎉 MATCH FOUND! 🎉
        {% for server_id, match in matches.items() %}
        <div style="margin: 10px 0;">
            <strong>Server:</strong> {{ server_id }} |
            <strong>Pattern:</strong> {{ match.prefix }}...{{ match.suffix }} |
            <strong>Time:</strong> {{ match.time_ago }}
        </div>
        {% endfor %}
        <div style="font-size: 0.8em; margin-top: 10px;">Check the server's directory for the keypair .json file</div>
    </div>
    {% endif %}

    <h2>Server Details</h2>
    <table>
        <tr>
            <th>Server ID</th>
            <th>Speed (MH/s)</th>
            <th>GPUs</th>
            <th>Last Update</th>
            <th>Status</th>
        </tr>
        {% for server_id, data in servers.items() %}
        <tr class="{{ 'offline' if data.is_stale else '' }}">
            <td>{{ server_id }}</td>
            <td>{{ "%.2f"|format(data.speed) }}</td>
            <td>{{ data.gpu_count }}</td>
            <td>{{ data.ago }}s ago</td>
            <td>{{ "OFFLINE" if data.is_stale else "ACTIVE" }}</td>
        </tr>
        {% endfor %}
    </table>

    <p style="color: #888; font-size: 0.9em;">Auto-refreshes every 5 seconds</p>
</body>
</html>
"""

def format_duration(seconds):
    """Format duration in seconds to human-readable string."""
    if seconds <= 0 or seconds == float('inf'):
        return "calculating..."

    seconds = int(seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 365:
        return f"{days / 365:.1f} years"
    elif days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"

def cleanup_stale_servers():
    """Remove servers that haven't reported in a while."""
    while True:
        time.sleep(30)
        now = time.time()
        with server_lock:
            stale = [sid for sid, data in server_speeds.items()
                    if now - data["timestamp"] > STALE_TIMEOUT]
            for sid in stale:
                del server_speeds[sid]

# Start cleanup thread
cleanup_thread = threading.Thread(target=cleanup_stale_servers, daemon=True)
cleanup_thread.start()

@app.route('/report', methods=['POST'])
def report_speed():
    """Endpoint for servers to report their speed."""
    data = request.json
    server_id = data.get('server_id')
    speed = data.get('speed')  # in MH/s
    gpu_count = data.get('gpu_count', 1)

    if not server_id or speed is None:
        return jsonify({"error": "Missing server_id or speed"}), 400

    with server_lock:
        server_speeds[server_id] = {
            "speed": speed,
            "timestamp": time.time(),
            "gpu_count": gpu_count
        }

    return jsonify({"status": "ok", "total_speed": sum(s["speed"] for s in server_speeds.values())})

@app.route('/match', methods=['POST'])
def report_match():
    """Endpoint for servers to report a match found."""
    data = request.json
    server_id = data.get('server_id')
    prefix = data.get('prefix', '')
    suffix = data.get('suffix', '')

    if not server_id:
        return jsonify({"error": "Missing server_id"}), 400

    with server_lock:
        matches_found[server_id] = {
            "timestamp": time.time(),
            "prefix": prefix,
            "suffix": suffix
        }

    return jsonify({"status": "ok", "message": "Match recorded!"})

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get aggregated statistics."""
    with server_lock:
        total_speed = sum(s["speed"] for s in server_speeds.values())
        active_count = len(server_speeds)
        total_gpus = sum(s["gpu_count"] for s in server_speeds.values())

    return jsonify({
        "total_speed": total_speed,
        "active_servers": active_count,
        "total_gpus": total_gpus,
        "servers": server_speeds
    })

@app.route('/')
def dashboard():
    """Web dashboard showing all servers."""
    now = time.time()

    # Get search pattern from query params (optional)
    prefix_len = int(request.args.get('prefix_len', 0))
    suffix_len = int(request.args.get('suffix_len', 0))

    with server_lock:
        total_speed = sum(s["speed"] for s in server_speeds.values())
        active_count = len(server_speeds)
        total_gpus = sum(s["gpu_count"] for s in server_speeds.values())

        # Prepare server data with status
        servers_data = {}
        for sid, data in server_speeds.items():
            age = int(now - data["timestamp"])
            servers_data[sid] = {
                "speed": data["speed"],
                "gpu_count": data["gpu_count"],
                "ago": age,
                "is_stale": age > STALE_TIMEOUT
            }

    # Calculate ETA if pattern provided
    eta_50 = None
    eta_90 = None
    if prefix_len > 0 or suffix_len > 0:
        total_chars = prefix_len + suffix_len
        expected_attempts = 58 ** total_chars
        attempts_50 = expected_attempts * 0.693
        attempts_90 = expected_attempts * 2.303

        if total_speed > 0:
            eta_50 = format_duration(attempts_50 / (total_speed * 1e6))
            eta_90 = format_duration(attempts_90 / (total_speed * 1e6))

    # Prepare matches data
    matches_data = {}
    for sid, match in matches_found.items():
        age = int(now - match["timestamp"])
        matches_data[sid] = {
            "prefix": match["prefix"],
            "suffix": match["suffix"],
            "time_ago": format_duration(age) + " ago"
        }

    return render_template_string(
        HTML_TEMPLATE,
        total_speed=total_speed,
        active_count=active_count,
        total_gpus=total_gpus,
        servers=servers_data,
        eta_50=eta_50,
        eta_90=eta_90,
        matches=matches_data
    )

if __name__ == '__main__':
    print("Starting monitoring server...")
    print("Dashboard: http://0.0.0.0:5000/")
    print("Add ?prefix_len=4&suffix_len=4 to URL for ETA calculation")
    app.run(host='0.0.0.0', port=5000, debug=False)
