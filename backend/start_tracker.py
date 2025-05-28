import os
import socket
import subprocess
import argparse

def get_local_ip():
    """Get the local IP address that can be reached from outside"""
    try:
        # Always use localhost for local testing
        return "127.0.0.1"
    except Exception:
        # Fallback to localhost if we can't determine IP
        return "127.0.0.1"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start BitTorrent tracker on localhost")
    parser.add_argument("--tracker-only", action="store_true", help="Start only the tracker container")
    parser.add_argument("--local", action="store_true", help="Use localhost (127.0.0.1)", default=True)
    args = parser.parse_args()
    
    # Always use localhost for this scenario
    host_ip = "127.0.0.1"
    print(f"Using localhost: {host_ip}")
    
    # Set the HOST_IP environment variable
    os.environ["HOST_IP"] = host_ip
    
    # Start the tracker (and optionally other services)
    if args.tracker_only:
        print("Starting tracker container only...")
        subprocess.run(["docker-compose", "up", "-d", "tracker"])
    else:
        print("Starting all containers...")
        subprocess.run(["docker-compose", "up", "-d"])
    
    print(f"\nTracker is now running at: http://127.0.0.1:6969")
    print(f"Announce URL for your torrents: http://127.0.0.1:6969/announce")
    print("\nTo download a torrent that uses this tracker:")
    print(f"1. Visit http://127.0.0.1:5001/blockchain/chain/torrent/external")
    print("2. Open the downloaded .torrent file with your BitTorrent client")
    print("3. The client should automatically connect to your tracker")
