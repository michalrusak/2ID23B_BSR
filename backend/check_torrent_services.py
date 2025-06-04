import os
import requests
import logging
import time
import socket
import argparse
import json
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_tracker_status():
    """Check if the tracker is accessible and running"""
    logger.info("Checking tracker status...")
    
    # Try various possible addresses for the tracker
    tracker_addresses = [
        "http://127.0.0.1:6969/stats",
        "http://localhost:6969/stats",
        "http://localhost:6969/stats"
    ]
    
    host_ip = os.getenv('HOST_IP')
    if host_ip:
        tracker_addresses.append(f"http://{host_ip}:6969/stats")
    
    for address in tracker_addresses:
        try:
            logger.info(f"Trying tracker at {address}...")
            response = requests.get(address, timeout=5)
            if response.status_code == 200:
                logger.info(f"✅ Tracker is running at {address}")
                logger.info(f"Tracker stats: {response.json()}")
                return True, address, response.json()
            else:
                logger.warning(f"❌ Tracker responded with status code {response.status_code}")
        except Exception as e:
            logger.warning(f"❌ Failed to connect to tracker at {address}: {e}")
    
    logger.error("❌ Could not connect to tracker at any address")
    return False, None, None

def check_seeder_status():
    """Check if the seeder is running and accessible"""
    logger.info("Checking seeder status...")
    
    # Try to connect to the seeder's RPC port
    seeder_addresses = [
        "http://127.0.0.1:6800/jsonrpc",
        "http://localhost:6800/jsonrpc",
        "http://seeder:6800/jsonrpc"
    ]
    
    for address in seeder_addresses:
        try:
            logger.info(f"Trying seeder at {address}...")
            response = requests.post(
                address, 
                json={
                    "jsonrpc": "2.0",
                    "method": "aria2.getGlobalStat",
                    "id": "check"
                },
                timeout=5
            )
            if response.status_code == 200:
                logger.info(f"✅ Seeder is running at {address}")
                logger.info(f"Seeder stats: {response.json()}")
                return True, address, response.json()
            else:
                logger.warning(f"❌ Seeder responded with status code {response.status_code}")
        except Exception as e:
            logger.warning(f"❌ Failed to connect to seeder at {address}: {e}")
    
    logger.warning("❌ Could not connect to seeder's RPC interface")
    
    # Try to check if the process is running
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, text=True)
        if "seeder" in result.stdout:
            logger.info("✅ Seeder container is running")
            return True, None, {"status": "running", "rpc": "not accessible"}
    except Exception as e:
        logger.warning(f"❌ Failed to check Docker containers: {e}")
    
    return False, None, None

def check_data_directory():
    """Check the contents of the data directory"""
    logger.info("Checking data directory...")
    
    # Try various possible locations
    data_dirs = [
        os.path.join(os.getcwd(), "blockchain_data"),
        "/app/blockchain_data"
    ]
    
    for data_dir in data_dirs:
        try:
            if os.path.exists(data_dir):
                logger.info(f"✅ Data directory exists: {data_dir}")
                
                # Check what files are in the directory
                files = os.listdir(data_dir)
                logger.info(f"Found {len(files)} files in data directory")
                
                torrent_files = [f for f in files if f.endswith('.torrent')]
                data_files = [f for f in files if f.endswith('.json')]
                
                logger.info(f"✅ Torrent files: {len(torrent_files)}")
                for tf in torrent_files:
                    try:
                        size = os.path.getsize(os.path.join(data_dir, tf))
                        logger.info(f"  - {tf} ({size} bytes)")
                    except:
                        logger.info(f"  - {tf}")
                
                logger.info(f"✅ Data files: {len(data_files)}")
                for df in data_files:
                    try:
                        size = os.path.getsize(os.path.join(data_dir, df))
                        logger.info(f"  - {df} ({size} bytes)")
                    except:
                        logger.info(f"  - {df}")
                
                # Check if torrent and data files match
                matched_pairs = 0
                for tf in torrent_files:
                    base_name = os.path.splitext(tf)[0]
                    matching_data = f"{base_name}.json"
                    
                    if matching_data in data_files:
                        matched_pairs += 1
                        logger.info(f"✅ Matched pair: {tf} -> {matching_data}")
                    else:
                        logger.warning(f"❌ No matching data file for torrent: {tf}")
                
                logger.info(f"Found {matched_pairs} matched torrent-data pairs out of {len(torrent_files)} torrents")
                
                return True, data_dir, {
                    "total_files": len(files),
                    "torrent_files": len(torrent_files),
                    "data_files": len(data_files),
                    "matched_pairs": matched_pairs
                }
            
        except Exception as e:
            logger.warning(f"❌ Error checking data directory {data_dir}: {e}")
    
    logger.error("❌ Could not find or access data directory")
    return False, None, None

def fix_torrent_naming(data_dir):
    """Try to fix torrent naming issues automatically"""
    import shutil
    import re
    
    logger.info(f"Attempting to fix torrent naming in {data_dir}...")
    
    try:
        files = os.listdir(data_dir)
        torrent_files = [f for f in files if f.endswith('.torrent')]
        data_files = [f for f in files if f.endswith('.json')]
        
        # Extract blockchain index pattern (e.g., "blockchain_1", "blockchain_2", etc.)
        blockchain_pattern = re.compile(r'(blockchain|manual_data)_(\d+)')
        
        # Group files by index
        torrent_by_index = {}
        data_by_index = {}
        
        # Map torrent files by index
        for torrent_file in torrent_files:
            match = blockchain_pattern.search(torrent_file)
            if match:
                prefix = match.group(1)
                index = int(match.group(2))
                key = f"{prefix}_{index}"
                torrent_by_index[key] = torrent_file
        
        # Map data files by index
        for data_file in data_files:
            match = blockchain_pattern.search(data_file)
            if match:
                prefix = match.group(1)
                index = int(match.group(2))
                key = f"{prefix}_{index}"
                data_by_index[key] = data_file
        
        logger.info(f"Mapped {len(torrent_by_index)} torrent files by index")
        logger.info(f"Mapped {len(data_by_index)} data files by index")
        
        # Find keys that exist in both dictionaries (matched pairs)
        matched_keys = set(torrent_by_index.keys()) & set(data_by_index.keys())
        logger.info(f"Found {len(matched_keys)} matched pairs by index")
        
        # Find orphaned torrent files (no matching data file)
        orphaned_torrents = set(torrent_by_index.keys()) - set(data_by_index.keys())
        logger.info(f"Found {len(orphaned_torrents)} orphaned torrent files")
        
        # Find orphaned data files (no matching torrent file)
        orphaned_data = set(data_by_index.keys()) - set(torrent_by_index.keys())
        logger.info(f"Found {len(orphaned_data)} orphaned data files")
        
        # Create new torrent files for orphaned data files
        from torrentool.torrent import Torrent
        
        host_ip = os.getenv('HOST_IP', '127.0.0.1')
        tracker_url = f"http://{host_ip}:6969/announce"
        
        for key in orphaned_data:
            data_file = data_by_index[key]
            data_path = os.path.join(data_dir, data_file)
            
            logger.info(f"Creating new torrent for orphaned data file: {data_file}")
            
            try:
                new_torrent = Torrent.create_from(data_path)
                new_torrent.announce_urls = [tracker_url]
                new_torrent.comment = f"Fixed torrent for {data_file}"
                new_torrent.created_by = "Torrent Fix Tool"
                
                # Save with matching name
                new_torrent_name = f"{key}.torrent"
                new_torrent_path = os.path.join(data_dir, new_torrent_name)
                new_torrent.to_file(new_torrent_path)
                
                logger.info(f"✅ Created new torrent: {new_torrent_name}")
            except Exception as e:
                logger.error(f"❌ Failed to create torrent for {data_file}: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"❌ Error fixing torrent naming: {e}")
        return False

def restart_services():
    """Try to restart the tracker and seeder services"""
    logger.info("Attempting to restart tracker and seeder...")
    
    try:
        # Try to restart tracker
        logger.info("Restarting tracker...")
        subprocess.run(["docker-compose", "restart", "tracker"], check=True)
        logger.info("✅ Tracker restarted successfully")
        
        # Wait a moment for tracker to start up
        time.sleep(5)
        
        # Try to restart seeder
        logger.info("Restarting seeder...")
        subprocess.run(["docker-compose", "restart", "seeder"], check=True)
        logger.info("✅ Seeder restarted successfully")
        
        return True
    except Exception as e:
        logger.error(f"❌ Error restarting services: {e}")
        return False

def check_and_fix():
    """Check and fix torrent-related issues"""
    # Check tracker
    tracker_ok, tracker_addr, tracker_stats = check_tracker_status()
    
    # Check seeder
    seeder_ok, seeder_addr, seeder_stats = check_seeder_status()
    
    # Check data directory
    data_ok, data_dir, data_stats = check_data_directory()
    
    # If data directory exists, try to fix torrent naming
    if data_ok:
        fix_torrent_naming(data_dir)
    
    # If tracker or seeder is not running, try to restart them
    if not tracker_ok or not seeder_ok:
        restart_services()
    
    # Print summary
    logger.info("===== SUMMARY =====")
    logger.info(f"Tracker: {'✅ Running' if tracker_ok else '❌ Not running'}")
    logger.info(f"Seeder: {'✅ Running' if seeder_ok else '❌ Not running'}")
    logger.info(f"Data directory: {'✅ Found' if data_ok else '❌ Not found'}")
    logger.info("==================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and fix torrent services")
    parser.add_argument("--fix", action="store_true", help="Try to fix issues automatically")
    parser.add_argument("--restart", action="store_true", help="Restart tracker and seeder services")
    
    args = parser.parse_args()
    
    if args.restart:
        restart_services()
    elif args.fix:
        check_and_fix()
    else:
        # Just check status
        check_tracker_status()
        check_seeder_status()
        check_data_directory()
