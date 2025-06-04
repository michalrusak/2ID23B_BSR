import os
import sys
import time
import logging
import subprocess
import signal
import glob
import requests
import random
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class TorrentWatcher(FileSystemEventHandler):
    """Watch for new torrent files and start seeding them"""
    
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.active_torrents = {}
        self.next_port = 6801  # Start from 6801 for RPC ports, leave 6800 free
        logger.info(f"Torrent watcher initialized, watching directory: {data_dir}")
        
        # Make sure tracker is accessible before starting
        self.check_tracker_connection()
        
        # Start seeding existing torrent files
        self.seed_existing_torrents()
        
        # Start a status checking thread
        self.start_status_checker()
    
    def check_tracker_connection(self):
        """Check if the tracker is accessible"""
        host_ip = os.getenv('HOST_IP', '127.0.0.1')
        # Try both the HOST_IP and "tracker" service name
        tracker_urls = [
            f"http://{host_ip}:6969/stats",
            "http://tracker:6969/stats"
        ]
        
        max_retries = 5
        retry_count = 0
        
        while retry_count < max_retries:
            for tracker_url in tracker_urls:
                try:
                    logger.info(f"Checking tracker connection at {tracker_url}...")
                    response = requests.get(tracker_url, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"Tracker is accessible! Response: {response.json()}")
                        return True
                except Exception as e:
                    logger.warning(f"Error connecting to tracker at {tracker_url}: {e}")
            
            retry_count += 1
            logger.info(f"Retrying tracker connection in 5 seconds... (attempt {retry_count}/{max_retries})")
            time.sleep(5)
        
        logger.warning("Could not connect to tracker after multiple attempts. Will continue anyway...")
        return False
    
    def start_status_checker(self):
        """Start a thread to periodically check seeding status"""
        import threading
        
        def check_status():
            while True:
                try:
                    # Print the status of all seeding torrents
                    logger.info("===== CURRENT SEEDING STATUS =====")
                    
                    if not self.active_torrents:
                        logger.info("No active torrents being seeded!")
                    else:
                        logger.info(f"Currently seeding {len(self.active_torrents)} torrents")
                        
                        for torrent_path, info in list(self.active_torrents.items()):
                            process = info["process"]
                            if process.poll() is None:
                                # Process is still running
                                logger.info(f"✅ ACTIVE: {os.path.basename(torrent_path)} (running for {int(time.time() - info['started_at'])}s)")
                            else:
                                # Process has ended
                                exit_code = process.poll()
                                logger.warning(f"❌ STOPPED: {os.path.basename(torrent_path)} (exit code: {exit_code})")
                                
                                # Only restart if it's a port conflict (exit code 1) and not a file-related issue
                                if exit_code == 1 and "Address already in use" in self.active_torrents[torrent_path].get("error_log", ""):
                                    # Get a new port for this torrent
                                    self.next_port = self.get_free_port()
                                    logger.info(f"Port conflict detected, restarting with new port {self.next_port}")
                                    self.start_seeding(torrent_path)
                                elif exit_code != 0:
                                    # Use --allow-overwrite=true to handle existing files
                                    logger.info(f"Restarting with allow-overwrite for {os.path.basename(torrent_path)}")
                                    self.start_seeding(torrent_path, allow_overwrite=True)
                    
                    # Also check the tracker status
                    try:
                        host_ip = os.getenv('HOST_IP', '127.0.0.1')
                        # Try both the HOST_IP and "tracker" service name
                        for tracker_url in [f"http://{host_ip}:6969/stats", "http://tracker:6969/stats"]:
                            try:
                                response = requests.get(tracker_url, timeout=2)
                                if response.status_code == 200:
                                    tracker_stats = response.json()
                                    logger.info(f"Tracker stats from {tracker_url}: {tracker_stats}")
                                    break
                            except:
                                continue
                    except Exception as e:
                        logger.error(f"Error checking tracker: {e}")
                    
                    # Check what files we have
                    logger.info("Files in data directory:")
                    for file_path in glob.glob(os.path.join(self.data_dir, "*")):
                        file_name = os.path.basename(file_path)
                        try:
                            file_size = os.path.getsize(file_path)
                            logger.info(f"- {file_name} ({file_size} bytes)")
                        except:
                            logger.info(f"- {file_name} (unknown size)")
                    
                    logger.info("===== END STATUS CHECK =====")
                except Exception as e:
                    logger.error(f"Error in status checker: {e}")
                
                time.sleep(30)  # Check every 30 seconds
        
        status_thread = threading.Thread(target=check_status, daemon=True)
        status_thread.start()
        logger.info("Started periodic status checker")
    
    def get_free_port(self):
        """Get a free port for RPC by incrementing or choosing random port"""
        # Increment from the last used port, or use a random port in higher range
        port = self.next_port
        self.next_port += 1
        
        # If we've used too many ports, reset to a random high port
        if self.next_port > 6900:
            self.next_port = random.randint(7000, 8000)
            
        return port
    
    def seed_existing_torrents(self):
        """Start seeding any existing torrent files in the data directory"""
        logger.info("Checking for existing torrent files to seed...")
        try:
            # List all files in the directory
            all_files = os.listdir(self.data_dir)
            logger.info(f"All files in {self.data_dir}: {all_files}")
            
            # Find torrent files
            torrent_files = [f for f in all_files if f.endswith('.torrent')]
            logger.info(f"Found {len(torrent_files)} torrent files: {torrent_files}")
            
            if not torrent_files:
                logger.warning("No torrent files found to seed!")
                return
            
            # Start seeding each torrent
            for torrent_file in torrent_files:
                torrent_path = os.path.join(self.data_dir, torrent_file)
                logger.info(f"Found existing torrent: {torrent_path}")
                
                # Extract the base name (without extension) to find matching data file
                base_name = os.path.splitext(torrent_file)[0]  # e.g., "blockchain_1"
                
                # Look for data file with same base name but .json extension
                data_file = f"{base_name}.json"
                data_path = os.path.join(self.data_dir, data_file)
                
                if os.path.exists(data_path):
                    logger.info(f"✅ Data file exists: {data_path} ({os.path.getsize(data_path)} bytes)")
                    logger.info(f"===== SENDING EXISTING TORRENT FOR SEEDING: {torrent_file} =====")
                    self.start_seeding(torrent_path, allow_overwrite=True)
                else:
                    logger.warning(f"❌ Data file not found: {data_path}")
                    logger.warning(f"Looking for alternative data files for {base_name}...")
                    
                    # Search for any file that might match this torrent
                    possible_data_files = [f for f in all_files if f.startswith(base_name) and f.endswith('.json')]
                    if possible_data_files:
                        logger.info(f"Found possible matching data files: {possible_data_files}")
                        for possible_file in possible_data_files:
                            logger.info(f"Trying to seed torrent with data file: {possible_file}")
                            self.start_seeding(torrent_path, allow_overwrite=True)
                            break
                    else:
                        logger.error(f"No matching data file found for torrent: {torrent_file}")
        except Exception as e:
            logger.error(f"Error seeding existing torrents: {e}")
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and event.src_path.endswith('.torrent'):
            logger.info(f"New torrent file detected: {event.src_path}")
            logger.info(f"===== SENDING NEW TORRENT FOR SEEDING: {os.path.basename(event.src_path)} =====")
            self.start_seeding(event.src_path, allow_overwrite=True)
    
    def start_seeding(self, torrent_path, allow_overwrite=False):
        """Start seeding a torrent file using aria2c"""
        try:
            # Check if we're already seeding this torrent
            if torrent_path in self.active_torrents and self.active_torrents[torrent_path]["process"].poll() is None:
                logger.info(f"Already seeding {torrent_path}")
                return
            
            logger.info(f"===== PREPARING TO SEED TORRENT: {os.path.basename(torrent_path)} =====")
            
            # Get RPC port for this torrent
            rpc_port = self.get_free_port()
            
            # Enhanced aria2c configuration for better peer connections
            cmd = [
                "aria2c",
                "--seed-time=0",  # Seed forever
                "--seed-ratio=0",  # Seed forever
                f"--dir={self.data_dir}",  # Download directory
                "--file-allocation=none",  # Fast file allocation
                "--enable-dht=true",
                "--dht-listen-port=6881",
                f"--listen-port=6881",
                "--always-resume=true",
                "--daemon=false",  # Run in foreground
                "--enable-peer-exchange=true",  # Enable PEX
                "--enable-dht6=true",  # Enable IPv6 DHT
                "--bt-enable-lpd=true",  # Enable Local Peer Discovery
                "--bt-max-peers=100",  # Increase max peers
                "--bt-request-peer-speed-limit=500K",  # Min speed per peer
                f"--enable-rpc=true",  # Enable RPC for monitoring
                f"--rpc-listen-port={rpc_port}",  # Use a unique RPC port
                "--rpc-listen-all=true",  # Listen on all interfaces
                "--bt-detach-seed-only=false",  # Don't detach seed-only peers
                "--min-split-size=1M",  # Min split size
                "--bt-tracker-connect-timeout=10",  # Tracker connect timeout
                "--bt-tracker-timeout=10",  # Tracker timeout
                "--user-agent=Transmission/2.94",  # Spoof a common client for better compatibility
                "--bt-force-encryption=false",  # Allow unencrypted connections
                "--bt-require-crypto=false",  # Don't require encryption
                "--max-overall-upload-limit=0",  # No upload limit
                "--seed-time=0",  # Seed forever (again, to be sure)
                "--bt-enable-hook-after-hash-check=true",  # Allow hooks
                "--bt-stop-timeout=180",  # Wait longer before stopping
                "--follow-torrent=true",  # Follow the torrent
            ]
            
            # Add allow overwrite if needed
            if allow_overwrite:
                cmd.append("--allow-overwrite=true")
                
            # Add the torrent file as the last argument
            cmd.append(torrent_path)
            
            logger.info(f"Starting aria2c with command: {' '.join(cmd)}")
            logger.info(f"===== EXECUTING SEED COMMAND FOR TORRENT: {os.path.basename(torrent_path)} =====")
            
            # Start the process with pipe for stderr to capture errors
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store the process with more detailed info
            self.active_torrents[torrent_path] = {
                "process": process,
                "started_at": time.time(),
                "torrent_path": torrent_path,
                "rpc_port": rpc_port,
                "error_log": "",
                "output_log": []
            }
            
            logger.info(f"===== SUCCESSFULLY STARTED SEEDING TORRENT: {os.path.basename(torrent_path)} =====")
            
            # Start a thread to log output and capture errors
            def log_output():
                for line in process.stdout:
                    self.active_torrents[torrent_path]["output_log"].append(line.strip())
                    if "BitTorrent" in line or "tracker" in line or "peer" in line:
                        logger.info(f"===== TORRENT ACTIVITY: {os.path.basename(torrent_path)} - {line.strip()} =====")
                    else:
                        logger.info(f"aria2c: {line.strip()}")
                
                # Also capture stderr for error detection
                for line in process.stderr:
                    self.active_torrents[torrent_path]["error_log"] += line
                    logger.error(f"aria2c error: {line.strip()}")
            
            import threading
            threading.Thread(target=log_output, daemon=True).start()
            
        except Exception as e:
            logger.error(f"Error starting to seed {torrent_path}: {e}")

def start_seeding_service(data_dir):
    """Start the seeding service"""
    logger.info(f"Starting torrent seeding service in directory: {data_dir}")
    
    # Create event handler and observer
    event_handler = TorrentWatcher(data_dir)
    observer = Observer()
    observer.schedule(event_handler, data_dir, recursive=False)
    observer.start()
    
    try:
        logger.info("Torrent seeding service is running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping torrent seeding service...")
        observer.stop()
        
        # Stop all aria2c processes
        for torrent_path, info in event_handler.active_torrents.items():
            try:
                if info["process"].poll() is None:  # Process is still running
                    logger.info(f"===== STOPPING SEEDING OF TORRENT: {os.path.basename(torrent_path)} =====")
                    info["process"].terminate()
                    info["process"].wait(timeout=5)
            except Exception as e:
                logger.error(f"Error stopping process for {torrent_path}: {e}")
        
    observer.join()

if __name__ == "__main__":
    # Use the blockchain_data directory in the current working directory
    data_dir = os.path.join(os.getcwd(), "blockchain_data")
    
    # Create the data directory if it doesn't exist
    os.makedirs(data_dir, exist_ok=True)
    
    # Print environment information for debugging
    logger.info("===== ENVIRONMENT INFORMATION =====")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Data directory: {data_dir}")
    logger.info(f"HOST_IP: {os.getenv('HOST_IP', 'Not set')}")
    logger.info(f"Existing files: {os.listdir(data_dir) if os.path.exists(data_dir) else 'Directory does not exist'}")
    logger.info("===================================")
    
    # Start the seeding service
    start_seeding_service(data_dir)
