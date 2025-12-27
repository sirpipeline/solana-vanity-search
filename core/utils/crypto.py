import json
import logging
import os
from pathlib import Path
from typing import Optional

from base58 import b58encode
from nacl.signing import SigningKey

from core.utils.webhook import send_discord_webhook


def get_public_key_from_private_bytes(pv_bytes: bytes) -> str:
    """
    Private key -> Public key (base58 encode)
    """
    pv = SigningKey(pv_bytes)
    pb_bytes = bytes(pv.verify_key)
    return b58encode(pb_bytes).decode()


def save_keypair(pv_bytes: bytes, output_dir: str, webhook_url: Optional[str] = None) -> str:
    """
    Save private key to JSON file, return public key

    Args:
        pv_bytes: Private key bytes
        output_dir: Directory to save keypair JSON
        webhook_url: Optional Discord webhook URL for notifications
    """
    pv = SigningKey(pv_bytes)
    pb_bytes = bytes(pv.verify_key)
    pubkey = b58encode(pb_bytes).decode()

    # Save to file
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    file_path = Path(output_dir) / f"{pubkey}.json"
    keypair_list = list(pv_bytes + pb_bytes)
    keypair_json = json.dumps(keypair_list)
    file_path.write_text(keypair_json)

    logging.info(f"Found: {pubkey}")
    logging.info(f"Keypair saved to: {file_path}")

    # Send Discord webhook if URL provided (only public key + location for security)
    if webhook_url:
        instance_name = os.environ.get("INSTANCE_NAME", "Unknown GPU")
        send_discord_webhook(webhook_url, pubkey, str(file_path), instance_name)

    return pubkey
