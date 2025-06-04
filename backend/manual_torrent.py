import os
import sys
import json
import logging
import argparse
import subprocess
import time
from torrentool.torrent import Torrent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_test_file(data_dir, size_kb=100):
    """Create a test file for seeding"""
    file_path = os.path.join(data_dir, f"test_file_{size_kb}kb.txt")
    with open(file_path, 'w') as f:
        # Create a file with specified size in KB
        f.write('X' * (size_kb * 1024))
    logger.info(f"Created test file: {file_path} ({size_kb} KB)")
    return file_path

def create_torrent(file_path, tracker_url="http://127.0.0.1:6969/announce"):
    """Create a torrent file from the given file"""
    torrent_path = f"{file_path}.torrent"
    
    logger.info(f"Creating torrent: {torrent_path}")
    logger.info(f"Using tracker: {tracker_url}")
    
    # Create torrent
    torrent = Torrent.create_from(file_path)
    torrent.announce_urls = [tracker_url]
    torrent.comment = "Test torrent"
    torrent.created_by = "Manual Torrent Tool"
    
    # Save torrent file
    torrent.to_file(torrent_path)
    
    logger.info(f"Created torrent file: {torrent_path}")
    logger.info(f"Info hash: {torrent.info_hash}")
    
    return torrent_path

def start_seeding(torrent_path, data_dir):
    """Start seeding a torrent file using aria2c"""
    logger.info(f"Starting to seed: {torrent_path}")
    
    cmd = [
        "aria2c",
        "--seed-time=0",  # Seed forever
        "--seed-ratio=0",  # Seed forever
        f"--dir={data_dir}",  # Download directory
        "--file-allocation=none",  # Fast file allocation
        "--daemon=false",  # Run in foreground
        "--enable-dht=true",
        "--bt-enable-lpd=true",  # Enable Local Peer Discovery
        "--bt-force-encryption=false",  # Allow unencrypted connections
        "--bt-require-crypto=false",  # Don't require encryption
        torrent_path
    ]
    
    logger.info(f"Command: {' '.join(cmd)}")
    
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    
    logger.info(f"Started seeding process (PID: {process.pid})")
    
    # Log output
    for line in process.stdout:
        logger.info(f"aria2c: {line.strip()}")
    
    return process

def check_tracker(tracker_url="http://127.0.0.1:6969/stats"):
    """Check if the tracker is accessible"""
    import requests
    
    logger.info(f"Checking tracker at: {tracker_url}")
    
    try:
        response = requests.get(tracker_url, timeout=5)
        if response.status_code == 200:
            logger.info(f"Tracker is accessible!")
            logger.info(f"Stats: {response.json()}")
            return True
        else:
            logger.error(f"Tracker returned status code {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error connecting to tracker: {e}")
        return False

def list_files(data_dir):
    """List all files in the data directory"""
    logger.info(f"Listing files in: {data_dir}")
    
    for file_name in os.listdir(data_dir):
        file_path = os.path.join(data_dir, file_name)
        file_size = os.path.getsize(file_path)
        logger.info(f"- {file_name} ({file_size} bytes)")

def main():
    parser = argparse.ArgumentParser(description="Manual torrent management tool")
    
    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Create test file command
    create_parser = subparsers.add_parser("create", help="Create a test file and torrent")
    create_parser.add_argument("--size", type=int, default=100, help="Size of test file in KB")
    
    # Check tracker command
    check_parser = subparsers.add_parser("check", help="Check if tracker is accessible")
    
    # List files command
    list_parser = subparsers.add_parser("list", help="List files in data directory")
    
    # Parse arguments
    args = parser.parse_args()
    
    # Get data directory
    data_dir = os.path.join(os.getcwd(), "blockchain_data")
    os.makedirs(data_dir, exist_ok=True)
    
    # Print environment info
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"Current directory: {os.getcwd()}")
    
    # Process commands
    if args.command == "create":
        # Create test file
        file_path = create_test_file(data_dir, args.size)
        
        # Create torrent
        tracker_url = f"http://{os.getenv('HOST_IP', '127.0.0.1')}:6969/announce"
        torrent_path = create_torrent(file_path, tracker_url)
        
        # Start seeding
        process = start_seeding(torrent_path, data_dir)
        
        # Wait for seeding to start
        try:
            logger.info("Seeding started. Press Ctrl+C to stop.")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping seeding...")
            process.terminate()
    
    elif args.command == "check":
        # Check tracker
        tracker_url = f"http://{os.getenv('HOST_IP', '127.0.0.1')}:6969/stats"
        check_tracker(tracker_url)
    
    elif args.command == "list":
        # List files
        list_files(data_dir)
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
