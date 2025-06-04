import os
import sys
import json
import requests
import logging
import subprocess
import time
import glob
from torrentool.torrent import Torrent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_environment():
    """Check environment variables and system state"""
    logger.info("Checking environment...")
    
    host_ip = os.getenv('HOST_IP')
    logger.info(f"HOST_IP: {host_ip}")
    
    if not host_ip:
        logger.error("HOST_IP environment variable is not set! This is required for the tracker.")
        logger.info("Please set it to 127.0.0.1 for local testing:")
        logger.info("  Windows: set HOST_IP=127.0.0.1")
        logger.info("  Linux/Mac: export HOST_IP=127.0.0.1")
        return False
    
    return True

def check_data_directory():
    """Check if the blockchain_data directory exists and is accessible"""
    logger.info("Checking data directory...")
    
    data_dir = os.path.join(os.getcwd(), "blockchain_data")
    
    if not os.path.exists(data_dir):
        logger.error(f"Data directory does not exist: {data_dir}")
        logger.info("Creating data directory...")
        try:
            os.makedirs(data_dir, exist_ok=True)
            logger.info(f"Created data directory: {data_dir}")
        except Exception as e:
            logger.error(f"Error creating data directory: {e}")
            return False
    
    # Check if directory is writable
    try:
        test_file = os.path.join(data_dir, "write_test.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        os.remove(test_file)
        logger.info(f"Data directory is writable: {data_dir}")
    except Exception as e:
        logger.error(f"Data directory is not writable: {e}")
        return False
    
    # List files in data directory
    logger.info(f"Files in data directory:")
    for file_path in glob.glob(os.path.join(data_dir, "*")):
        file_name = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        logger.info(f"- {file_name} ({file_size} bytes)")
    
    return data_dir

def check_tracker():
    """Check if the tracker is running and accessible"""
    logger.info("Checking tracker...")
    
    host_ip = os.getenv('HOST_IP', '127.0.0.1')
    tracker_url = f"http://{host_ip}:6969/stats"
    
    try:
        logger.info(f"Checking tracker at: {tracker_url}")
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
        logger.info("Make sure the tracker container is running:")
        logger.info("  docker-compose up -d tracker")
        return False

def verify_torrent_files(data_dir):
    """Verify that torrent files and their data files match"""
    logger.info("Verifying torrent files...")
    
    torrent_files = glob.glob(os.path.join(data_dir, "*.torrent"))
    logger.info(f"Found {len(torrent_files)} torrent files")
    
    valid_torrents = []
    invalid_torrents = []
    
    for torrent_path in torrent_files:
        torrent_name = os.path.basename(torrent_path)
        logger.info(f"Checking torrent: {torrent_name}")
        
        try:
            # Load the torrent file
            torrent = Torrent.from_file(torrent_path)
            
            # Get info
            info_hash = torrent.info_hash
            trackers = torrent.announce_urls
            name = torrent.name
            
            logger.info(f"  Info hash: {info_hash}")
            logger.info(f"  Name: {name}")
            logger.info(f"  Trackers: {trackers}")
            
            # Check if data file exists
            data_file = os.path.join(data_dir, name)
            if os.path.exists(data_file):
                file_size = os.path.getsize(data_file)
                logger.info(f"  ✅ Data file exists: {name} ({file_size} bytes)")
                valid_torrents.append(torrent_path)
            else:
                # Try with alternative name format (blockchain_1.json)
                base_name = os.path.basename(torrent_path).replace('.torrent', '.json')
                data_file = os.path.join(data_dir, base_name)
                
                if os.path.exists(data_file):
                    file_size = os.path.getsize(data_file)
                    logger.info(f"  ✅ Data file exists with alternative name: {base_name} ({file_size} bytes)")
                    
                    # Fix the torrent file by updating the name
                    logger.info(f"  Fixing torrent file to point to {base_name}...")
                    fixed_torrent = create_fixed_torrent(data_file, torrent_path, trackers)
                    if fixed_torrent:
                        logger.info(f"  ✅ Fixed torrent saved to: {fixed_torrent}")
                        valid_torrents.append(fixed_torrent)
                        invalid_torrents.append(torrent_path)
                else:
                    logger.error(f"  ❌ Data file not found: {name} or {base_name}")
                    invalid_torrents.append(torrent_path)
        except Exception as e:
            logger.error(f"  ❌ Error checking torrent: {e}")
            invalid_torrents.append(torrent_path)
    
    return valid_torrents, invalid_torrents

def create_fixed_torrent(data_file, original_torrent, trackers):
    """Create a fixed torrent file that points to the correct data file"""
    try:
        # Get file name without path
        data_file_name = os.path.basename(data_file)
        
        # Create new torrent with correct name
        fixed_torrent_path = original_torrent.replace('.torrent', '_fixed.torrent')
        
        # Create torrent
        torrent = Torrent.create_from(data_file)
        torrent.announce_urls = trackers
        torrent.comment = f"Fixed torrent for {data_file_name}"
        torrent.created_by = "Torrent Debug Tool"
        
        # Save torrent file
        torrent.to_file(fixed_torrent_path)
        
        return fixed_torrent_path
    except Exception as e:
        logger.error(f"Error creating fixed torrent: {e}")
        return None

def start_seeding_torrent(torrent_path, data_dir):
    """Start seeding a specific torrent"""
    logger.info(f"Starting to seed: {torrent_path}")
    
    cmd = [
        "aria2c",
        "--seed-time=0",  # Seed forever
        "--seed-ratio=0",  # Seed forever
        f"--dir={data_dir}",  # Download directory
        "--daemon=false",  # Run in foreground
        "--file-allocation=none",  # Fast file allocation
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
    return process

def main():
    logger.info("===== BLOCKCHAIN TORRENT DEBUG TOOL =====")
    
    # Check environment
    if not check_environment():
        logger.error("Environment check failed!")
        return
    
    # Check data directory
    data_dir = check_data_directory()
    if not data_dir:
        logger.error("Data directory check failed!")
        return
    
    # Check tracker
    if not check_tracker():
        logger.warning("Tracker check failed, but continuing...")
    
    # Verify torrent files
    valid_torrents, invalid_torrents = verify_torrent_files(data_dir)
    
    if invalid_torrents:
        logger.warning(f"Found {len(invalid_torrents)} invalid torrent files")
        for torrent in invalid_torrents:
            logger.warning(f"- {os.path.basename(torrent)}")
    
    if not valid_torrents:
        logger.error("No valid torrent files found!")
        
        # Create a test torrent
        logger.info("Creating a test torrent...")
        test_file = os.path.join(data_dir, "test_file.txt")
        with open(test_file, 'w') as f:
            f.write("This is a test file for torrent debugging.\n" * 100)
        
        # Create torrent
        host_ip = os.getenv('HOST_IP', '127.0.0.1')
        tracker_url = f"http://{host_ip}:6969/announce"
        
        torrent = Torrent.create_from(test_file)
        torrent.announce_urls = [tracker_url]
        torrent.comment = "Test torrent"
        torrent.created_by = "Torrent Debug Tool"
        
        # Save torrent file
        test_torrent = os.path.join(data_dir, "test_file.torrent")
        torrent.to_file(test_torrent)
        
        logger.info(f"Created test torrent: {test_torrent}")
        valid_torrents.append(test_torrent)
    
    # Start seeding valid torrents
    logger.info(f"Starting to seed {len(valid_torrents)} valid torrents...")
    
    processes = []
    for torrent in valid_torrents:
        process = start_seeding_torrent(torrent, data_dir)
        processes.append((torrent, process))
    
    # Wait for seeding to continue
    try:
        logger.info("Seeding started. Press Ctrl+C to stop.")
        
        while True:
            # Check processes
            for torrent, process in processes:
                torrent_name = os.path.basename(torrent)
                if process.poll() is not None:
                    logger.warning(f"Seeding process for {torrent_name} exited with code {process.poll()}")
                else:
                    logger.info(f"Still seeding {torrent_name}")
            
            # Check tracker
            check_tracker()
            
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("Stopping seeding...")
        for torrent, process in processes:
            if process.poll() is None:
                process.terminate()

if __name__ == "__main__":
    main()
