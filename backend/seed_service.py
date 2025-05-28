import os
import sys
import time
import logging
import subprocess
import signal
import glob
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
        logger.info(f"Torrent watcher initialized, watching directory: {data_dir}")
        
        # Start seeding existing torrent files
        self.seed_existing_torrents()
    
    def seed_existing_torrents(self):
        """Start seeding any existing torrent files in the data directory"""
        logger.info("Checking for existing torrent files to seed...")
        try:
            for torrent_path in glob.glob(os.path.join(self.data_dir, "*.torrent")):
                logger.info(f"Found existing torrent: {torrent_path}")
                self.start_seeding(torrent_path)
        except Exception as e:
            logger.error(f"Error seeding existing torrents: {e}")
    
    def on_created(self, event):
        """Handle file creation events"""
        if not event.is_directory and event.src_path.endswith('.torrent'):
            logger.info(f"New torrent file detected: {event.src_path}")
            self.start_seeding(event.src_path)
    
    def start_seeding(self, torrent_path):
        """Start seeding a torrent file using aria2c"""
        try:
            # Check if we're already seeding this torrent
            if torrent_path in self.active_torrents:
                logger.info(f"Already seeding {torrent_path}")
                return
            
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
                "--enable-rpc=true",  # Enable RPC for monitoring
                "--rpc-listen-port=6800",  # RPC port
                "--rpc-listen-all=true",  # Listen on all interfaces
                "--bt-detach-seed-only=false",  # Don't detach seed-only peers
                "--min-split-size=1M",  # Min split size
                "--bt-tracker-connect-timeout=10",  # Tracker connect timeout
                "--bt-tracker-timeout=10",  # Tracker timeout
                "--user-agent=Transmission/2.94",  # Spoof a common client for better compatibility
                torrent_path
            ]
            
            logger.info(f"Starting aria2c with command: {' '.join(cmd)}")
            
            # Start the process
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Store the process
            self.active_torrents[torrent_path] = {
                "process": process,
                "started_at": time.time(),
                "torrent_path": torrent_path
            }
            
            logger.info(f"Started seeding {torrent_path}")
            
            # Start a thread to log output
            def log_output():
                for line in process.stdout:
                    logger.info(f"aria2c: {line.strip()}")
                for line in process.stderr:
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
                    logger.info(f"Stopping seeding of {torrent_path}")
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
    
    # Start the seeding service
    start_seeding_service(data_dir)
