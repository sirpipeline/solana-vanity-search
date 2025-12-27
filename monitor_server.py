#!/usr/bin/env python3
"""
Monitoring server to aggregate speeds from multiple vanity search servers.
Run this on a server accessible to all your vast.ai instances.
"""

from flask import Flask, request, jsonify, render_template_string
import time
from collections import defaultdict
import threading
import json
import os

app = Flask(__name__)

# Persistence file
STATE_FILE = "monitor_state.json"

# Store speeds: {server_id: {"speed": MH/s, "timestamp": time, "gpu_count": N, "first_seen": time, "total_iterations": int}}
server_speeds = {}
# Store matches: {server_id: {"timestamp": time, "prefix": str, "suffix": str}}
matches_found = {}
server_lock = threading.Lock()
start_time = time.time()

def save_state():
    """Save current state to disk."""
    with server_lock:
        state = {
            "server_speeds": server_speeds,
            "matches_found": matches_found,
            "start_time": start_time
        }
        try:
            with open(STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

def load_state():
    """Load state from disk if exists."""
    global server_speeds, matches_found, start_time

    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                server_speeds = state.get("server_speeds", {})
                matches_found = state.get("matches_found", {})
                start_time = state.get("start_time", time.time())
                print(f"Loaded state: {len(server_speeds)} servers, {len(matches_found)} matches")
                print(f"Uptime restored: {format_duration(time.time() - start_time)}")
        except Exception as e:
            print(f"Error loading state: {e}")
            print("Starting with fresh state")

# Clean up stale servers every 30 seconds
OFFLINE_TIMEOUT = 60  # Show server as OFFLINE after 60s without update
REMOVE_TIMEOUT = 300  # Remove server completely after 5 minutes (300s) without update

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Vanity Address Search Monitor</title>
    <style>
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 20px; background: #1e1e1e; color: #fff; }
        h1 { color: #4CAF50; text-align: center; margin-bottom: 10px; }
        .subtitle { text-align: center; color: #888; margin-bottom: 30px; }
        .total { font-size: 3em; color: #4CAF50; margin: 10px 0; font-weight: bold; text-align: center; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 20px 0; }
        .stat-card { background: #2d2d2d; padding: 20px; border-radius: 10px; text-align: center; border: 2px solid #444; }
        .stat-card h3 { margin: 0 0 10px 0; color: #888; font-size: 0.9em; text-transform: uppercase; }
        .stat-card .value { font-size: 2em; font-weight: bold; color: #4CAF50; }
        .stat-card.warning .value { color: #ff9800; }
        .stat-card.danger .value { color: #f44336; }
        .countdown { font-size: 2.5em; font-weight: bold; color: #2196F3; font-family: 'Courier New', monospace; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; background: #2d2d2d; border-radius: 10px; overflow: hidden; }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid #444; }
        th { background: #4CAF50; color: white; font-weight: bold; text-transform: uppercase; font-size: 0.9em; }
        tr:hover { background: #3d3d3d; }
        .offline { opacity: 0.5; color: #f44336; }
        .hostname-cell { cursor: help; position: relative; }
        .hostname-cell:hover { text-decoration: underline; }
        .status-badge { padding: 5px 10px; border-radius: 5px; font-size: 0.8em; font-weight: bold; }
        .status-active { background: #4CAF50; color: white; }
        .status-offline { background: #f44336; color: white; }
        .progress-bar { width: 100%; height: 30px; background: #444; border-radius: 5px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #4CAF50, #8BC34A); transition: width 0.3s; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; }
    </style>
</head>
<body>
    <h1>🚀 Vanity Address Search Monitor</h1>
    <div class="subtitle">Real-time Multi-Server Performance Tracking</div>

    <div class="total">{{ "%.2f"|format(total_speed) }} MH/s</div>

    <div class="stats-grid">
        <div class="stat-card">
            <h3>Active Servers</h3>
            <div class="value">{{ active_count }}</div>
        </div>
        <div class="stat-card">
            <h3>Total GPUs</h3>
            <div class="value">{{ total_gpus }}</div>
        </div>
        <div class="stat-card">
            <h3>Total Iterations</h3>
            <div class="value">{{ total_iterations }}</div>
        </div>
        <div class="stat-card">
            <h3>Uptime</h3>
            <div class="value">{{ uptime }}</div>
        </div>
    </div>

    {% if eta_50_seconds %}
    <div class="stat-card" style="margin: 20px 0;">
        <h3>⏱️ Countdown to 50% Probability</h3>
        <div class="countdown" id="countdown50">{{ eta_50 }}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {{ progress_50 }}%">{{ "%.1f"|format(progress_50) }}%</div>
        </div>
    </div>

    <div class="stat-card warning" style="margin: 20px 0;">
        <h3>⏱️ Countdown to 90% Probability</h3>
        <div class="countdown" id="countdown90">{{ eta_90 }}</div>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {{ progress_90 }}%; background: linear-gradient(90deg, #ff9800, #ffb74d);">{{ "%.1f"|format(progress_90) }}%</div>
        </div>
    </div>
    {% endif %}

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

    <h2 style="text-align: center; margin-top: 40px;">📊 Server Details</h2>
    <table>
        <tr>
            <th>Hostname</th>
            <th>IP Address</th>
            <th>GPU Model</th>
            <th>GPUs</th>
            <th>Speed</th>
            <th>Iterations</th>
            <th>Runtime</th>
            <th>Last Update</th>
            <th>Status</th>
        </tr>
        {% for server_id, data in servers.items() %}
        <tr class="{{ 'offline' if data.is_stale else '' }}">
            <td class="hostname-cell" title="Instance ID: {{ data.vast_instance_id }}&#10;Host: {{ data.vast_host_id }}&#10;Machine ID: {{ data.vast_machine_id }}"><strong>{{ data.hostname[:20] }}</strong></td>
            <td>{{ data.ip_address }}</td>
            <td style="font-size: 0.85em;">{{ data.gpu_names }}</td>
            <td>{{ data.gpu_count }}</td>
            <td><strong>{{ "%.2f"|format(data.speed) }} MH/s</strong></td>
            <td>{{ data.iterations }}</td>
            <td>{{ data.runtime }}</td>
            <td>{{ data.ago }}s ago</td>
            <td><span class="status-badge {{ 'status-offline' if data.is_stale else 'status-active' }}">{{ "OFFLINE" if data.is_stale else "ACTIVE" }}</span></td>
        </tr>
        {% endfor %}
    </table>

    <p style="color: #888; font-size: 0.9em;">Auto-refreshes every 2 seconds</p>

    <script>
        // Live countdown timers
        let eta50Seconds = {{ eta_50_seconds }};
        let lastUpdate = Date.now();

        function formatSeconds(totalSeconds) {
            if (totalSeconds <= 0) return "COMPLETE!";

            const days = Math.floor(totalSeconds / 86400);
            const hours = Math.floor((totalSeconds % 86400) / 3600);
            const minutes = Math.floor((totalSeconds % 3600) / 60);
            const seconds = totalSeconds % 60;

            if (days > 365) {
                return `${(days / 365).toFixed(1)} years`;
            } else if (days > 0) {
                return `${days}d ${hours}h ${minutes}m ${seconds}s`;
            } else if (hours > 0) {
                return `${hours}h ${minutes}m ${seconds}s`;
            } else if (minutes > 0) {
                return `${minutes}m ${seconds}s`;
            } else {
                return `${seconds}s`;
            }
        }

        function updateCountdowns() {
            const now = Date.now();
            const elapsed = Math.floor((now - lastUpdate) / 1000);

            const remaining50 = Math.max(0, eta50Seconds - elapsed);
            const remaining90 = Math.floor(remaining50 / 0.693 * 2.303);

            const countdown50El = document.getElementById('countdown50');
            const countdown90El = document.getElementById('countdown90');

            if (countdown50El) {
                countdown50El.textContent = formatSeconds(remaining50);
            }
            if (countdown90El) {
                countdown90El.textContent = formatSeconds(remaining90);
            }
        }

        // Update countdown every second
        if (eta50Seconds > 0) {
            setInterval(updateCountdowns, 1000);
        }
    </script>
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

def format_number(num):
    """Format large numbers with K/M/B/T suffixes."""
    if num < 1000:
        return str(int(num))
    elif num < 1_000_000:
        return f"{num / 1_000:.1f}K"
    elif num < 1_000_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num < 1_000_000_000_000:
        return f"{num / 1_000_000_000:.1f}B"
    else:
        return f"{num / 1_000_000_000_000:.1f}T"

def cleanup_stale_servers():
    """Remove servers that haven't reported in a while."""
    while True:
        time.sleep(30)
        now = time.time()
        with server_lock:
            stale = [sid for sid, data in server_speeds.items()
                    if now - data["timestamp"] > REMOVE_TIMEOUT]
            for sid in stale:
                del server_speeds[sid]
            if stale:
                print(f"Removed {len(stale)} stale servers (offline > 5 minutes)")

        # Save state periodically
        save_state()

# Load saved state on startup
load_state()

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
    gpu_names = data.get('gpu_names', [])  # List of GPU model names
    hostname = data.get('hostname', server_id)
    ip_address = data.get('ip_address', 'N/A')
    vast_instance_id = data.get('vast_instance_id', 'N/A')
    vast_host_id = data.get('vast_host_id', 'N/A')
    vast_machine_id = data.get('vast_machine_id', 'N/A')

    if not server_id or speed is None:
        return jsonify({"error": "Missing server_id or speed"}), 400

    with server_lock:
        now = time.time()
        if server_id in server_speeds:
            # Update existing server
            old_data = server_speeds[server_id]
            elapsed = now - old_data["timestamp"]
            iterations = speed * 1e6 * elapsed  # Convert MH/s to iterations
            server_speeds[server_id] = {
                "speed": speed,
                "timestamp": now,
                "gpu_count": gpu_count,
                "gpu_names": gpu_names or old_data.get("gpu_names", []),
                "hostname": hostname or old_data.get("hostname", server_id),
                "ip_address": ip_address or old_data.get("ip_address", "N/A"),
                "vast_instance_id": vast_instance_id or old_data.get("vast_instance_id", "N/A"),
                "vast_host_id": vast_host_id or old_data.get("vast_host_id", "N/A"),
                "vast_machine_id": vast_machine_id or old_data.get("vast_machine_id", "N/A"),
                "first_seen": old_data.get("first_seen", now),
                "total_iterations": old_data.get("total_iterations", 0) + iterations
            }
        else:
            # New server
            server_speeds[server_id] = {
                "speed": speed,
                "timestamp": now,
                "gpu_count": gpu_count,
                "gpu_names": gpu_names,
                "hostname": hostname,
                "ip_address": ip_address,
                "vast_instance_id": vast_instance_id,
                "vast_host_id": vast_host_id,
                "vast_machine_id": vast_machine_id,
                "first_seen": now,
                "total_iterations": 0
            }

    # Save state after update
    save_state()

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

    # Save state after match found
    save_state()

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

        # Calculate total iterations across all servers
        total_iterations = sum(s.get("total_iterations", 0) for s in server_speeds.values())

        # Format total iterations with K/M/B/T suffixes
        total_iterations_str = format_number(total_iterations)

        # Prepare server data with status
        servers_data = {}
        for sid, data in server_speeds.items():
            age = int(now - data["timestamp"])
            runtime = int(now - data.get("first_seen", now))
            iterations = data.get("total_iterations", 0)

            # Format GPU names
            gpu_names = data.get("gpu_names", [])
            if gpu_names:
                gpu_display = ", ".join(set(gpu_names))  # Unique GPU names
            else:
                gpu_display = "N/A"

            servers_data[sid] = {
                "speed": data["speed"],
                "gpu_count": data["gpu_count"],
                "gpu_names": gpu_display,
                "hostname": data.get("hostname", sid),
                "ip_address": data.get("ip_address", "N/A"),
                "vast_instance_id": data.get("vast_instance_id", "N/A"),
                "vast_host_id": data.get("vast_host_id", "N/A"),
                "vast_machine_id": data.get("vast_machine_id", "N/A"),
                "ago": age,
                "is_stale": age > OFFLINE_TIMEOUT,
                "runtime": format_duration(runtime),
                "iterations": format_number(iterations)
            }

    # Calculate uptime (time since first server started reporting)
    uptime_seconds = 0
    if server_speeds:
        first_seen_times = [s.get("first_seen", now) for s in server_speeds.values()]
        earliest = min(first_seen_times)
        uptime_seconds = int(now - earliest)
    uptime = format_duration(uptime_seconds)

    # Calculate ETA if pattern provided
    eta_50 = None
    eta_90 = None
    eta_50_seconds = 0
    progress_50 = 0
    progress_90 = 0

    if prefix_len > 0 or suffix_len > 0:
        total_chars = prefix_len + suffix_len
        expected_attempts = 58 ** total_chars
        attempts_50 = expected_attempts * 0.693
        attempts_90 = expected_attempts * 2.303

        if total_speed > 0:
            # Calculate remaining time in seconds
            remaining_50 = max(0, (attempts_50 - total_iterations) / (total_speed * 1e6))
            remaining_90 = max(0, (attempts_90 - total_iterations) / (total_speed * 1e6))

            eta_50 = format_duration(remaining_50)
            eta_90 = format_duration(remaining_90)
            eta_50_seconds = int(remaining_50)

            # Calculate progress percentages
            progress_50 = min(100, (total_iterations / attempts_50) * 100)
            progress_90 = min(100, (total_iterations / attempts_90) * 100)

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
        total_iterations=total_iterations_str,
        uptime=uptime,
        servers=servers_data,
        eta_50=eta_50,
        eta_90=eta_90,
        eta_50_seconds=eta_50_seconds,
        progress_50=progress_50,
        progress_90=progress_90,
        matches=matches_data
    )

if __name__ == '__main__':
    print("Starting monitoring server...")
    print("Dashboard: http://0.0.0.0:5000/")
    print("Add ?prefix_len=4&suffix_len=4 to URL for ETA calculation")
    app.run(host='0.0.0.0', port=5000, debug=False)
