import os
import json
import logging
import tempfile
import hashlib
import time
import base64
from torrentool.torrent import Torrent
import bencode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BlockchainTorrent:
    """Class to handle blockchain torrent operations"""
    
    def __init__(self, node_id="unknown"):
        self.node_id = node_id
        # Use a persistent directory instead of a temp directory
        self.temp_dir = os.path.join(os.getcwd(), "blockchain_data")
        # Create the directory if it doesn't exist
        os.makedirs(self.temp_dir, exist_ok=True)
        logger.info(f"Initialized BlockchainTorrent for node {node_id}, using data dir: {self.temp_dir}")
        
    def blockchain_to_file(self, blockchain_data, file_path=None):
        """Convert blockchain data to a JSON file that can be used for torrents"""
        if file_path is None:
            timestamp = int(time.time())
            file_path = os.path.join(self.temp_dir, f"blockchain_{self.node_id}_{timestamp}.json")
        
        logger.info(f"Creating blockchain file at: {file_path}")
        
        try:
            # Process blockchain data to decode base64 image data
            processed_data = self.process_blockchain_data(blockchain_data)
            
            with open(file_path, 'w') as f:
                json.dump(processed_data, f, indent=2)
            
            logger.info(f"Blockchain file created successfully: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error creating blockchain file: {e}")
            return None
    
    def process_blockchain_data(self, blockchain_data):
        """Process blockchain data to decode base64 image data"""
        processed_data = blockchain_data.copy()
        
        if 'chain' in processed_data:
            for block in processed_data['chain']:
                if 'transactions' in block:
                    for tx in block['transactions']:
                        # If this is an image transaction, decode the base64 data
                        if tx.get('type') == 'image' and isinstance(tx.get('data'), str):
                            try:
                                # Store the actual image data instead of base64
                                image_data = base64.b64decode(tx['data'])
                                tx['data'] = image_data.decode('latin1')  # Use latin1 to preserve binary data as string
                                logger.info(f"Decoded image data for transaction with CRC: {tx.get('crc')}")
                            except Exception as e:
                                logger.error(f"Error decoding image data: {e}")
        
        return processed_data
    
    def create_torrent_file(self, blockchain_data, announce_urls=None, comment="Blockchain Data Torrent"):
        """Create a torrent file from blockchain data"""
        logger.info("Creating torrent file from blockchain data")
        
        if announce_urls is None:
            # Use localhost for the tracker
            host_ip = os.getenv('HOST_IP', '127.0.0.1')
            
            # Add our custom tracker as the first in the list (highest priority)
            announce_urls = [
                f"http://{host_ip}:6969/announce",  # Our custom tracker with localhost
                # Default tracker list - add more trackers as needed
                "udp://tracker.opentrackr.org:1337/announce",
                "udp://tracker.openbittorrent.com:80/announce",
                "udp://tracker.torrent.eu.org:451/announce",
                "udp://exodus.desync.com:6969/announce",
                "udp://tracker.moeking.me:6969/announce",
                "udp://open.stealth.si:80/announce",
                "udp://tracker.dler.org:6969/announce",
                "udp://explodie.org:6969/announce",
                "udp://bt1.archive.org:6969/announce",
                "udp://bt2.archive.org:6969/announce"
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
            logger.info(f"Data file: {blockchain_file}")
            logger.info(f"Torrent uses tracker: {announce_urls}")
            
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
    
    def list_data_files(self):
        """List all data files in the data directory"""
        try:
            files = []
            for filename in os.listdir(self.temp_dir):
                if filename.endswith('.json'):
                    file_path = os.path.join(self.temp_dir, filename)
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'created': os.path.getctime(file_path)
                    })
            return files
        except Exception as e:
            logger.error(f"Error listing data files: {e}")
            return []
    
    def list_torrent_files(self):
        """List all torrent files in the data directory"""
        try:
            files = []
            for filename in os.listdir(self.temp_dir):
                if filename.endswith('.torrent'):
                    file_path = os.path.join(self.temp_dir, filename)
                    files.append({
                        'name': filename,
                        'path': file_path,
                        'size': os.path.getsize(file_path),
                        'created': os.path.getctime(file_path)
                    })
            return files
        except Exception as e:
            logger.error(f"Error listing torrent files: {e}")
            return []
