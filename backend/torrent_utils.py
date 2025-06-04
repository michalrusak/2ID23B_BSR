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
        # Add counters for file naming
        self.blockchain_counter = self._get_next_counter("blockchain")
        self.transaction_counter = self._get_next_counter("transaction")
        logger.info(f"Initialized BlockchainTorrent for node {node_id}, using data dir: {self.temp_dir}")
    
    def _get_next_counter(self, prefix):
        """Get the next available counter for a given prefix by checking existing files"""
        max_counter = 0
        for filename in os.listdir(self.temp_dir):
            if filename.startswith(f"{prefix}_"):
                try:
                    # Extract counter from filename (between first and second underscore)
                    parts = filename.split('_')
                    if len(parts) >= 3:
                        counter = int(parts[1])
                        max_counter = max(max_counter, counter)
                except ValueError:
                    pass
        return max_counter + 1
    
    def blockchain_to_file(self, blockchain_data, file_path=None):
        """Convert blockchain data to a JSON file that can be used for torrents"""
        if file_path is None:
            counter = self.blockchain_counter
            self.blockchain_counter += 1
            file_path = os.path.join(self.temp_dir, f"blockchain_{counter}.json")
        
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
            
            # Use counter for torrent file name
            counter = self.blockchain_counter - 1  # Use the same counter as the data file
            torrent_path = os.path.join(self.temp_dir, f"blockchain_{counter}.torrent")
            
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
    
    def create_torrent_from_transaction(self, transaction_data, announce_urls=None, chunk_size=512*1024):
        """Create a torrent file from a transaction in the blockchain"""
        logger.info("Creating torrent file from transaction data")
        
        try:
            # Use counter for transaction ID instead of hash
            counter = self.transaction_counter
            self.transaction_counter += 1
            transaction_id = f"{counter}"
            file_name = f"transaction_{transaction_id}.json"
            
            # Process transaction data
            if transaction_data.get('type') == 'image':
                # For image data, it's already in base64 format in the transaction
                raw_data = base64.b64decode(transaction_data['data'])
                logger.info(f"Extracted image data: {len(raw_data)} bytes")
            else:
                # For other types, convert to JSON string
                raw_data = json.dumps(transaction_data).encode('utf-8')
                logger.info(f"Converted transaction to JSON: {len(raw_data)} bytes")
            
            # Calculate file size
            file_size = len(raw_data)
            logger.info(f"Transaction data size: {file_size} bytes")
            
            # Create data file for the torrent
            data_file_path = os.path.join(self.temp_dir, f"transaction_{transaction_id}.data")
            with open(data_file_path, 'wb') as f:
                f.write(raw_data)
            logger.info(f"Saved transaction data to: {data_file_path}")
            
            # Save metadata JSON for reference
            json_file_path = os.path.join(self.temp_dir, f"transaction_{transaction_id}.json")
            json_data = {
                'transaction_id': transaction_id,
                'file_name': file_name,
                'file_size': file_size,
                'chunk_size': chunk_size,
                'created_at': time.time(),
                'node_id': self.node_id,
                'type': transaction_data.get('type', 'generic')
            }
            
            with open(json_file_path, 'w') as f:
                json.dump(json_data, f, indent=2)
            logger.info(f"Saved transaction metadata to: {json_file_path}")
            
            # Create the torrent file using torrentool or bencode directly
            torrent_path = self.save_to_torrent_file(
                data_file_path, 
                transaction_id, 
                file_name, 
                announce_urls=announce_urls, 
                piece_length=chunk_size
            )
            
            if not torrent_path:
                raise Exception("Failed to create torrent file")
                
            # Get the info hash
            torrent = Torrent.from_file(torrent_path)
            info_hash = torrent.info_hash
            
            return {
                'transaction_id': transaction_id,
                'torrent_path': torrent_path,
                'data_file_path': data_file_path,
                'json_file_path': json_file_path,
                'info_hash': info_hash,
                'file_size': file_size
            }
            
        except Exception as e:
            logger.error(f"Error creating torrent from transaction: {e}")
            return None
    
    def save_to_torrent_file(self, file_path, file_id, file_name, announce_urls=None, piece_length=512*1024):
        """Create a .torrent file from a data file and return the path to the torrent file"""
        logger.info(f"Creating .torrent file for {file_path}")
        
        try:
            if announce_urls is None:
                # Default announce URLs
                host_ip = os.getenv('HOST_IP', '127.0.0.1')
                announce_urls = [
                    f"http://{host_ip}:6969/announce",
                    "udp://tracker.opentrackr.org:1337/announce",
                    "udp://tracker.openbittorrent.com:80/announce"
                ]
            
            # Generate torrent file path
            torrent_path = os.path.join(self.temp_dir, f"transaction_{file_id}.torrent")
            
            # Method 1: Using torrentool (easier API)
            try:
                logger.info("Creating torrent using torrentool")
                torrent = Torrent.create_from(file_path)
                torrent.announce_urls = announce_urls
                torrent.comment = f"Blockchain transaction {file_id}"
                torrent.created_by = f"Blockchain Node {self.node_id}"
                torrent.to_file(torrent_path)
            except Exception as e:
                logger.error(f"Torrentool method failed: {e}")
                
                # Method 2: Using bencode directly (as shown in the example code)
                logger.info("Falling back to manual bencode creation")
                # Calculate pieces (SHA-1 hashes of each piece)
                pieces = b''
                with open(file_path, 'rb') as f:
                    while True:
                        piece_data = f.read(piece_length)
                        if not piece_data:
                            break
                        piece_hash = hashlib.sha1(piece_data).digest()
                        pieces += piece_hash
                
                # Get file size
                file_size = os.path.getsize(file_path)
                
                # Create info dictionary
                info_dict = {
                    b'name': file_name.encode('utf-8'),
                    b'piece length': piece_length,
                    b'pieces': pieces,
                    b'length': file_size
                }
                
                # Create torrent dictionary
                torrent_dict = {
                    b'info': info_dict,
                    b'announce': announce_urls[0].encode('utf-8')
                }
                
                # Add announce-list if multiple trackers
                if len(announce_urls) > 1:
                    announce_list = [[url.encode('utf-8')] for url in announce_urls]
                    torrent_dict[b'announce-list'] = announce_list
                
                # Add creation date
                torrent_dict[b'creation date'] = int(time.time())
                
                # Add created by
                torrent_dict[b'created by'] = f"Blockchain Node {self.node_id}".encode('utf-8')
                
                # Encode and write to file
                with open(torrent_path, 'wb') as f:
                    f.write(bencode.encode(torrent_dict))
            
            logger.info(f"Successfully created torrent file: {torrent_path}")
            return torrent_path
            
        except Exception as e:
            logger.error(f"Error creating torrent file: {e}")
            return None
    
    def get_transaction_data_from_torrent(self, torrent_path):
        """Extract transaction data from a torrent file"""
        try:
            # Get the file ID from the torrent filename
            file_id = os.path.basename(torrent_path).replace('.torrent', '')
            
            # Check if we have the JSON metadata file
            json_file_path = os.path.join(self.temp_dir, f"{file_id}.json")
            if os.path.exists(json_file_path):
                with open(json_file_path, 'r') as f:
                    metadata = json.load(f)
                    logger.info(f"Found metadata for torrent: {metadata}")
            
            # Check if we have the data file
            data_file_path = os.path.join(self.temp_dir, f"{file_id}.data")
            if os.path.exists(data_file_path):
                with open(data_file_path, 'rb') as f:
                    data = f.read()
                    logger.info(f"Found data file: {len(data)} bytes")
                    
                    # Determine if this is an image or other type
                    if metadata.get('type') == 'image':
                        # Return base64 encoded data for images
                        return {
                            'transaction_id': file_id,
                            'type': 'image',
                            'data': base64.b64encode(data).decode('utf-8'),
                            'metadata': metadata
                        }
                    else:
                        # Try to parse JSON data for other types
                        try:
                            json_data = json.loads(data)
                            return {
                                'transaction_id': file_id,
                                'type': 'generic',
                                'data': json_data,
                                'metadata': metadata
                            }
                        except:
                            # Return raw data if not JSON
                            return {
                                'transaction_id': file_id,
                                'type': 'raw',
                                'data': data,
                                'metadata': metadata
                            }
            
            # If we can't find the data file, analyze the torrent itself
            torrent = Torrent.from_file(torrent_path)
            return {
                'transaction_id': file_id,
                'info_hash': torrent.info_hash,
                'name': torrent.name,
                'size': torrent.total_size,
                'created_by': torrent.created_by,
                'comment': torrent.comment,
                'announce_urls': torrent.announce_urls
            }
            
        except Exception as e:
            logger.error(f"Error extracting data from torrent: {e}")
            return None
