import json
import logging
from typing import Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    logging.warning("requests library not found. Discord webhooks disabled.")


def send_discord_webhook(webhook_url: Optional[str], pubkey: str, keypair_path: str, instance_name: str = "GPU Instance") -> None:
    """
    Send Discord webhook notification when a vanity address is found.
    SECURITY: Only sends the public key and file location, NOT the private key.

    Args:
        webhook_url: Discord webhook URL (optional)
        pubkey: The found public key (base58)
        keypair_path: File path where the keypair is saved
        instance_name: Identifier for this instance (e.g., GPU ID, hostname)
    """
    if not webhook_url:
        return

    if not REQUESTS_AVAILABLE:
        logging.error("Cannot send webhook: requests library not installed")
        return

    try:
        embed = {
            "title": "🎉 Vanity Address Found!",
            "color": 0x00FF00,  # Green
            "fields": [
                {
                    "name": "Public Key",
                    "value": f"```{pubkey}```",
                    "inline": False
                },
                {
                    "name": "Instance",
                    "value": instance_name,
                    "inline": True
                },
                {
                    "name": "Keypair File Location",
                    "value": f"`{keypair_path}`",
                    "inline": False
                },
                {
                    "name": "⚠️ Next Steps",
                    "value": "1. SSH into the instance\n2. Copy the keypair file to your local machine\n3. Destroy all GPU instances\n4. Store the keypair securely offline",
                    "inline": False
                }
            ],
            "footer": {
                "text": "🔒 Private key NOT sent for security. SSH into instance to retrieve."
            }
        }

        payload = {
            "embeds": [embed],
            "content": f"@everyone Vanity address found: **{pubkey}**"
        }

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=10
        )

        if response.status_code == 204:
            logging.info(f"Discord webhook sent successfully for {pubkey}")
        else:
            logging.error(f"Discord webhook failed: {response.status_code} - {response.text}")

    except Exception as e:
        logging.error(f"Failed to send Discord webhook: {e}")
