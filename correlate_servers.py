#!/usr/bin/env python3
"""
Correlate monitoring server IDs with vast.ai instance IDs
"""
import subprocess
import json
import sys
import requests
from tabulate import tabulate

def get_monitoring_servers(monitor_url):
    """Get all servers reporting to monitoring dashboard."""
    try:
        stats_url = monitor_url.replace('/report', '/stats')
        response = requests.get(stats_url, timeout=10)
        data = response.json()
        return data.get('servers', {})
    except Exception as e:
        print(f"Error getting monitoring data: {e}")
        return {}

def get_vastai_instances():
    """Get all vast.ai instances."""
    try:
        result = subprocess.run(
            ['vastai', 'show', 'instances', '--raw'],
            capture_output=True,
            text=True,
            check=True
        )
        instances = json.loads(result.stdout)
        return instances
    except subprocess.CalledProcessError as e:
        print(f"Error running vastai CLI: {e}")
        print("Make sure vastai CLI is installed and configured")
        return []
    except json.JSONDecodeError:
        print("Error parsing vastai output")
        return []

def ssh_get_hostname(instance_id, ssh_addr, ssh_port):
    """SSH into instance and get hostname."""
    try:
        cmd = [
            'ssh',
            '-o', 'StrictHostKeyChecking=no',
            '-o', 'UserKnownHostsFile=/dev/null',
            '-o', 'ConnectTimeout=5',
            '-p', str(ssh_port),
            f'root@{ssh_addr}',
            'hostname'
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except Exception as e:
        return None

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 correlate_servers.py <monitor_url>")
        print()
        print("Example:")
        print("  python3 correlate_servers.py https://your-ngrok-url.ngrok-free.app/report")
        sys.exit(1)

    monitor_url = sys.argv[1]

    print("=" * 100)
    print("CORRELATING VAST.AI INSTANCES WITH MONITORING SERVER IDS")
    print("=" * 100)
    print()

    # Get monitoring servers
    print("📊 Fetching monitoring data...")
    monitoring_servers = get_monitoring_servers(monitor_url)
    print(f"   Found {len(monitoring_servers)} servers reporting to monitor")
    print()

    # Get vast.ai instances
    print("🖥️  Fetching vast.ai instances...")
    vastai_instances = get_vastai_instances()
    print(f"   Found {len(vastai_instances)} vast.ai instances")
    print()

    if not vastai_instances:
        print("❌ No vast.ai instances found or vastai CLI not working")
        sys.exit(1)

    # Build correlation table
    print("🔍 Checking hostnames (this may take a moment)...")
    print()

    table_data = []

    for instance in vastai_instances:
        instance_id = instance.get('id')
        ssh_host = instance.get('ssh_host', 'N/A')
        ssh_port = instance.get('ssh_port', 'N/A')
        gpu_name = instance.get('gpu_name', 'N/A')
        num_gpus = instance.get('num_gpus', 'N/A')
        status = instance.get('actual_status', 'N/A')

        if status != 'running':
            continue

        # Try to get hostname
        hostname = ssh_get_hostname(instance_id, ssh_host, ssh_port)

        # Check if this hostname matches any monitoring server
        monitor_id = "❌ Not reporting"
        speed = "-"

        if hostname:
            # Check if hostname matches any monitoring server ID
            for mon_id, mon_data in monitoring_servers.items():
                if hostname in mon_id or mon_id in hostname:
                    monitor_id = f"✅ {mon_id}"
                    speed = f"{mon_data.get('speed', 0):.2f} MH/s"
                    break
        else:
            hostname = "⚠️ Can't SSH"

        table_data.append([
            instance_id,
            f"{num_gpus}x {gpu_name}",
            hostname,
            monitor_id,
            speed,
            f"{ssh_host}:{ssh_port}"
        ])

    # Print table
    headers = ["Vast.ai ID", "GPUs", "Hostname", "Monitor Server ID", "Speed", "SSH Address"]
    print(tabulate(table_data, headers=headers, tablefmt="grid"))
    print()

    # Summary
    print("=" * 100)
    print("SUMMARY")
    print("=" * 100)

    reporting_count = sum(1 for row in table_data if "✅" in row[3])
    total_instances = len(table_data)

    print(f"✅ Reporting to monitor: {reporting_count}/{total_instances}")
    print(f"❌ Not reporting: {total_instances - reporting_count}/{total_instances}")
    print()

    if reporting_count < total_instances:
        print("💡 TIP: For instances not reporting, check:")
        print("   1. Is the on-start script configured correctly?")
        print("   2. Is the monitoring URL still valid?")
        print("   3. SSH in and check: tail -f ~/search.log")
        print()

    print("=" * 100)

if __name__ == "__main__":
    main()
