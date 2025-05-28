import os
import json
import logging
import tempfile
import hashlib
import time
from torrentool.torrent import Torrent
import bencode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlockchainTorrent:
    """Class to handle blockchain torrent operations"""
    
    def __init__(self, node_id="unknown"):
        self.node_id = node_id
        self.temp_dir = tempfile.mkdtemp(prefix="blockchain_torrent_")
        logger.info(f"Initialized BlockchainTorrent for node {node_id}, using temp dir: {self.temp_dir}")
        
    def blockchain_to_file(self, blockchain_data, file_path=None):
        """Convert blockchain data to a JSON file that can be used for torrents"""
        if file_path is None:
            timestamp = int(time.time())
            file_path = os.path.join(self.temp_dir, f"blockchain_{self.node_id}_{timestamp}.json")
        
        logger.info(f"Creating blockchain file at: {file_path}")
        
        try:
            with open(file_path, 'w') as f:
                json.dump(blockchain_data, f, indent=2)
            
            logger.info(f"Blockchain file created successfully: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error creating blockchain file: {e}")
            return None
    
    def create_torrent_file(self, blockchain_data, announce_urls=None, comment="Blockchain Data Torrent"):
        """Create a torrent file from blockchain data"""
        logger.info("Creating torrent file from blockchain data")
        
        if announce_urls is None:
            # Default tracker list - add more trackers as needed
            announce_urls = [
                "udp://tracker.opentrackr.org:1337/announce",
                "udp://tracker.openbittorrent.com:80/announce",
                "udp://tracker.torrent.eu.org:451/announce"
            ]
        
        try:
            # Create the blockchain data file
            blockchain_file = self.blockchain_to_file(blockchain_data)
            if not blockchain_file:
                raise Exception("Failed to create blockchain file")
            
            # Calculate a unique name for the torrent file
            file_hash = hashlib.md5(json.dumps(blockchain_data).encode()).hexdigest()
            torrent_path = os.path.join(self.temp_dir, f"blockchain_{self.node_id}_{file_hash}.torrent")
            
            # Create the torrent
            torrent = Torrent.create_from(blockchain_file)
            torrent.announce_urls = announce_urls
            torrent.comment = comment
            torrent.created_by = f"Blockchain Node {self.node_id}"
            
            # Save the torrent file
            torrent.to_file(torrent_path)
            
            logger.info(f"Torrent file created successfully: {torrent_path}")
            return {
                "torrent_path": torrent_path,
                "blockchain_file": blockchain_file,
                "info_hash": torrent.info_hash
            }
        except Exception as e:
            logger.error(f"Error creating torrent file: {e}")
            return None
    
    def get_torrent_info(self, torrent_path):
        """Get information about a torrent file"""
        try:
            torrent = Torrent.from_file(torrent_path)
            return {
                "info_hash": torrent.info_hash,
                "name": torrent.name,
                "size": torrent.total_size,
                "created_by": torrent.created_by,
                "comment": torrent.comment,
                "announce_urls": torrent.announce_urls
            }
        except Exception as e:
            logger.error(f"Error getting torrent info: {e}")
            return None
    
    def cleanup(self):
        """Clean up temporary files"""
        import shutil
        try:
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
        except Exception as e:
            logger.error(f"Error cleaning up: {e}")
