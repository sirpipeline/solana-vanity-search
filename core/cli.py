import logging
import multiprocessing
import sys
import time
from multiprocessing.pool import Pool
from typing import List, Optional, Tuple

import click
import pyopencl as cl

from core.config import DEFAULT_ITERATION_BITS, HostSetting
from core.opencl.manager import (
    get_all_gpu_devices,
    get_chosen_devices,
)
from core.searcher import multi_gpu_init, save_result
from core.utils.helpers import check_character, load_kernel_source

logging.basicConfig(level="INFO", format="[%(levelname)s %(asctime)s] %(message)s")


def format_duration(seconds: float) -> str:
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


@click.group()
def cli():
    pass


@cli.command(context_settings={"show_default": True})
@click.option(
    "--starts-with",
    type=str,
    default=[],
    help="Public key starts with the indicated prefix. Provide multiple arguments to search for multiple prefixes.",
    multiple=True,
)
@click.option(
    "--ends-with",
    type=str,
    default="",
    help="Public key ends with the indicated suffix.",
)
@click.option("--count", type=int, default=1, help="Count of pubkeys to generate.")
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, dir_okay=True, writable=True),
    default="./",
    help="Output directory.",
)
@click.option(
    "--select-device/--no-select-device",
    default=False,
    help="Select OpenCL device manually",
)
@click.option(
    "--iteration-bits",
    type=int,
    default=DEFAULT_ITERATION_BITS,
    help="Iteration bits (e.g., 24, 26, 28, etc.)",
)
@click.option(
    "--is-case-sensitive", type=bool, default=True, help="Case sensitive search flag."
)
@click.option(
    "--webhook-url",
    type=str,
    default="",
    help="Discord webhook URL for notifications when vanity address is found.",
)
@click.option(
    "--monitor-url",
    type=str,
    default="",
    help="Monitoring server URL (e.g., http://monitor-server:5000/report) to report speeds for multi-server tracking.",
)
@click.option(
    "--server-id",
    type=str,
    default="",
    help="Unique identifier for this server (e.g., vast-1, vast-2). Required if using --monitor-url.",
)
def search_pubkey(
    starts_with,
    ends_with,
    count,
    output_dir,
    select_device,
    iteration_bits,
    is_case_sensitive,
    webhook_url,
    monitor_url,
    server_id,
):
    """Search for Solana vanity pubkeys."""
    if not starts_with and not ends_with:
        click.echo("Please provide at least one of --starts-with or --ends-with.")
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        sys.exit(1)

    for prefix in starts_with:
        check_character("starts_with", prefix)
    check_character("ends_with", ends_with)

    chosen_devices: Optional[Tuple[int, List[int]]] = None
    if select_device:
        chosen_devices = get_chosen_devices()
        gpu_counts = len(chosen_devices[1])
    else:
        gpu_counts = len(get_all_gpu_devices())

    logging.info(
        "Searching Solana pubkey with starts_with=(%s), ends_with=%s, is_case_sensitive=%s",
        ", ".join(repr(s) for s in starts_with),
        repr(ends_with),
        is_case_sensitive,
    )
    logging.info(f"Using {gpu_counts} OpenCL device(s)")

    # Calculate expected attempts for ETA
    prefix_len = max(len(p) for p in starts_with) if starts_with else 0
    suffix_len = len(ends_with) if ends_with else 0
    total_chars = prefix_len + suffix_len

    # Base58 has 58 possible characters
    expected_attempts = 58 ** total_chars if total_chars > 0 else 0
    attempts_50_percent = expected_attempts * 0.693
    attempts_90_percent = expected_attempts * 2.303

    logging.info(f"Expected attempts: {expected_attempts:.2e}")
    logging.info(f"Attempts for 50%% probability: {attempts_50_percent:.2e}")
    logging.info(f"Attempts for 90%% probability: {attempts_90_percent:.2e}")

    result_count = 0
    with multiprocessing.Manager() as manager:
        with Pool(processes=gpu_counts) as pool:
            kernel_source = load_kernel_source(
                starts_with, ends_with, is_case_sensitive
            )
            lock = manager.Lock()
            speed_dict = manager.dict()
            start_time = manager.Value('d', time.time())
            total_attempts = manager.Value('d', 0.0)

            # Start ETA monitoring thread
            import threading
            import requests
            import socket

            # Gather GPU information
            gpu_names = []
            if chosen_devices is None:
                devices = get_all_gpu_devices()
            else:
                devices = get_selected_gpu_devices(*chosen_devices)
            gpu_names = [device.name for device in devices]

            # Get IP address
            try:
                hostname = socket.gethostname()
                ip_address = socket.gethostbyname(hostname)
            except:
                ip_address = "N/A"

            def monitor_eta():
                while result_count < count:
                    time.sleep(10)
                    if len(speed_dict) > 0:
                        total_speed = sum(speed_dict.values())
                        elapsed = time.time() - start_time.value
                        total_attempts_done = total_speed * 1e6 * elapsed

                        eta_50 = (attempts_50_percent - total_attempts_done) / (total_speed * 1e6) if total_speed > 0 and attempts_50_percent > total_attempts_done else 0
                        eta_90 = (attempts_90_percent - total_attempts_done) / (total_speed * 1e6) if total_speed > 0 and attempts_90_percent > total_attempts_done else 0

                        logging.info(
                            f"TOTAL Speed: {total_speed:.2f} MH/s | "
                            f"Total Attempts: {total_attempts_done:.2e} | "
                            f"ETA 50%%: {format_duration(eta_50)} | "
                            f"ETA 90%%: {format_duration(eta_90)}"
                        )

                        # Report to external monitoring server if configured
                        if monitor_url and server_id:
                            try:
                                requests.post(
                                    monitor_url,
                                    json={
                                        "server_id": server_id,
                                        "speed": total_speed,
                                        "gpu_count": gpu_counts,
                                        "gpu_names": gpu_names,
                                        "hostname": server_id,
                                        "ip_address": ip_address
                                    },
                                    timeout=5
                                )
                            except Exception as e:
                                logging.debug(f"Failed to report to monitor: {e}")

            eta_thread = threading.Thread(target=monitor_eta, daemon=True)
            eta_thread.start()

            while result_count < count:
                stop_flag = manager.Value("i", 0)
                results = pool.starmap(
                    multi_gpu_init,
                    [
                        (
                            x,
                            HostSetting(kernel_source, iteration_bits),
                            gpu_counts,
                            stop_flag,
                            lock,
                            chosen_devices,
                            speed_dict,
                            monitor_url,
                            server_id,
                            starts_with[0] if starts_with else "",
                            ends_with,
                        )
                        for x in range(gpu_counts)
                    ],
                )
                result_count += save_result(results, output_dir, webhook_url if webhook_url else None)


@cli.command(context_settings={"show_default": True})
def show_device():
    """Show available OpenCL devices."""
    platforms = cl.get_platforms()
    for p_index, platform in enumerate(platforms):
        click.echo(f"Platform {p_index}: {platform.name}")
        devices = platform.get_devices(device_type=cl.device_type.GPU)
        for d_index, device in enumerate(devices):
            click.echo(f"  - Device {d_index}: {device.name}")


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    cli()
