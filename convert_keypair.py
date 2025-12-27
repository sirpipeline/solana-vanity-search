#!/usr/bin/env python3
"""
Convert Solana keypair JSON to importable formats
"""
import json
import sys
import base58

def convert_keypair(keypair_file):
    """Convert keypair to various formats for wallet import."""

    # Read the keypair file
    with open(keypair_file, 'r') as f:
        keypair = json.load(f)

    if len(keypair) != 64:
        print(f"Error: Invalid keypair length. Expected 64 bytes, got {len(keypair)}")
        return

    # Extract private key (first 32 bytes) and public key (last 32 bytes)
    private_key_bytes = bytes(keypair[:32])
    public_key_bytes = bytes(keypair[32:])
    full_keypair_bytes = bytes(keypair)

    # Convert to base58
    private_key_base58 = base58.b58encode(private_key_bytes).decode('ascii')
    public_key_base58 = base58.b58encode(public_key_bytes).decode('ascii')
    full_keypair_base58 = base58.b58encode(full_keypair_bytes).decode('ascii')

    print("=" * 80)
    print("SOLANA KEYPAIR CONVERSION")
    print("=" * 80)
    print()

    print("PUBLIC KEY (Your wallet address):")
    print(public_key_base58)
    print()

    print("-" * 80)
    print("PRIVATE KEY (Base58) - For Phantom/Solflare:")
    print("-" * 80)
    print(private_key_base58)
    print()

    print("-" * 80)
    print("FULL KEYPAIR (Base58) - Alternative format:")
    print("-" * 80)
    print(full_keypair_base58)
    print()

    print("-" * 80)
    print("ARRAY FORMAT (Already have this - your .json file):")
    print("-" * 80)
    print(f"[{', '.join(map(str, keypair[:10]))}...] ({len(keypair)} bytes)")
    print()

    print("=" * 80)
    print("HOW TO IMPORT:")
    print("=" * 80)
    print()
    print("PHANTOM WALLET:")
    print("  1. Settings → Add/Connect Wallet → Import Private Key")
    print("  2. Paste the 'PRIVATE KEY (Base58)' from above")
    print()
    print("SOLFLARE WALLET:")
    print("  1. Import Wallet → Private Key")
    print("  2. Paste the 'PRIVATE KEY (Base58)' from above")
    print()
    print("SOLANA CLI:")
    print(f"  solana-keygen pubkey {keypair_file}")
    print()
    print("⚠️  KEEP YOUR PRIVATE KEY SECRET! Never share it!")
    print("=" * 80)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 convert_keypair.py <keypair.json>")
        print()
        print("Example:")
        print("  python3 convert_keypair.py haqq...qqqq.json")
        sys.exit(1)

    keypair_file = sys.argv[1]

    try:
        convert_keypair(keypair_file)
    except FileNotFoundError:
        print(f"Error: File '{keypair_file}' not found")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
