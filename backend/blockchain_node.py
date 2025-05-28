import os
import random
from flask import Flask, jsonify, request
import hashlib
import time
import json
import requests
import zlib
import base64
from PIL import Image
import io
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from p2p_network import P2PNetwork
from blockchain_serializer import BlockchainSerializer
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Transaction:
    def __init__(self, data, transaction_type="generic"):
        self.data = data
        self.timestamp = time.time()
        self.type = transaction_type
        self.crc = self.calculate_crc()
        self.confirmations = set()
        self.node_id = os.getenv('NODE_ID', 'unknown')  # Add node_id to transaction
        # Log transaction creation with CRC
        logger.info(
            f"Created new transaction - Type: {transaction_type}, CRC: {self.crc}",
            extra={'node_id': self.node_id}
        )

    def calculate_crc(self):
        """Calculate CRC32 checksum for data verification"""
        if isinstance(self.data, bytes):
            crc = format(zlib.crc32(self.data) & 0xFFFFFFFF, '08x')
        else:
            crc = format(zlib.crc32(str(self.data).encode()) & 0xFFFFFFFF, '08x')
        logger.info(
            f"Calculated CRC: {crc} for data type: {type(self.data)}",
            extra={'node_id': os.getenv('NODE_ID', 'unknown')}
        )
        return crc

    def verify_crc(self):
        """Verify data integrity using CRC32 checksum"""
        current_crc = self.calculate_crc()
        is_valid = self.crc == current_crc
        logger.info(
            f"CRC Verification - Stored: {self.crc}, Calculated: {current_crc}, Valid: {is_valid}",
            extra={'node_id': os.getenv('NODE_ID', 'unknown')}
        )
        return is_valid

    def to_dict(self):
        """Convert transaction to dictionary with proper data type handling"""
        if self.type == "image":
            # Ensure data is in bytes format for images
            if not isinstance(self.data, bytes):
                # If corrupted to string, convert back to bytes
                data_bytes = self.data.encode('utf-8')
            else:
                data_bytes = self.data
            return {
                "type": self.type,
                "data": base64.b64encode(data_bytes).decode('utf-8'),
                "timestamp": self.timestamp,
                "crc": self.crc,
                "confirmations": list(self.confirmations),
                "node_id": self.node_id  # Include node_id
            }
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "crc": self.crc,
            "confirmations": list(self.confirmations),
            "node_id": self.node_id  # Include node_id
        }

    @staticmethod
    def from_dict(data_dict):
        """Create transaction from dictionary with proper data type handling"""
        if data_dict["type"] == "image":
            data = base64.b64decode(data_dict["data"])
        else:
            data = data_dict["data"]
        
        transaction = Transaction(data, data_dict["type"])
        transaction.timestamp = data_dict["timestamp"]
        transaction.crc = data_dict["crc"]
        transaction.confirmations = set(data_dict["confirmations"])
        transaction.node_id = data_dict.get("node_id", os.getenv('NODE_ID', 'unknown'))
        return transaction

class Block:
    def __init__(self, index, previous_hash, transactions, timestamp=None):
        self.node_id = os.getenv('NODE_ID', 'unknown')
        self.index = index
        self.previous_hash = previous_hash
        self.transactions = transactions
        self.timestamp = timestamp or time.time()
        self.nonce = 0
        self.hash = self.calculate_hash()
        logger.info(
            f"Created new block - Index: {index}, Previous Hash: {previous_hash}, Initial Hash: {self.hash}",
            extra={'node_id': self.node_id}
        )

    def calculate_hash(self):
        block_string = json.dumps({
            'index': self.index,
            'previous_hash': self.previous_hash,
            'transactions': [t.to_dict() for t in self.transactions],
            'timestamp': self.timestamp,
            'nonce': self.nonce
        }, sort_keys=True).encode()
        
        new_hash = hashlib.sha256(block_string).hexdigest()
        return new_hash

    def mine_block(self, difficulty):
        logger.info(f"czy tu jestem start minig") 
        target = '0' * difficulty
        logger.info(
            f"Starting mining block {self.index} - Target difficulty: {difficulty}",
            extra={'node_id': self.node_id}
        )
        iterations = 0
        while self.hash[:difficulty] != target:
            self.nonce += 1
            self.hash = self.calculate_hash()
            iterations += 1
            if iterations % 1000 == 0:  # Log progress every 1000 iterations
                logger.info(
                    f"Mining progress - Block: {self.index}, Nonce: {self.nonce}, Current Hash: {self.hash}",
                    extra={'node_id': self.node_id}
                )
        
        logger.info(
            f"Successfully mined block {self.index} - Final Hash: {self.hash}, Nonce: {self.nonce}",
            extra={'node_id': self.node_id}
        )
        logger.info(f"czy tu jestem end minig") 

def generate_node_addresses(start_port, num_nodes):
    return [f"http://node{i}:{5000 + i}" for i in range(1, num_nodes + 1)]

class BlockchainNode:
    def __init__(self, node_id, start_port=5001, num_nodes=6, difficulty=2):
        self.node_id = node_id
        self.difficulty = difficulty  # Set difficulty first
        self.chain = [self.create_genesis_block()]  # Then create genesis block
        self.pending_transactions = []
        self.nodes = self.generate_docker_node_addresses(num_nodes)
        self.lock = threading.Lock()
        self.mining_status = {"is_mining": False, "progress": 0}
        self.health_check_interval = 30
        self.failed_nodes = {}
        
        # Initialize P2P network
        self.p2p = P2PNetwork(node_id, port=int(os.getenv('PORT', 5001)))
        
        # Register P2P message handlers
        self.p2p.register_handler("blockchain_request", self.handle_blockchain_request)
        self.p2p.register_handler("transaction_broadcast", self.handle_transaction_broadcast)
        self.p2p.register_handler("block_broadcast", self.handle_block_broadcast)
        
        # Start P2P network
        self.p2p.start_server()
        
        # Start health check and initial sync
        self.start_health_check()
        self.initial_sync()
        self.start_hash_verification()
        self.start_data_verification()
        
        # Export and share blockchain via P2P network
        self.export_and_share_blockchain()

    def start_data_verification(self):
        """Start periodic data verification"""
        def verify_data_periodically():
            while True:
                self.verify_and_correct_data()
                time.sleep(30)  # Check every 30 seconds
            
        thread = threading.Thread(target=verify_data_periodially, daemon=True)
        thread.start()

    def verify_and_correct_hashes(self):
        """Verify block hashes across nodes and correct any corrupted ones"""
        logger.info("Starting hash verification across nodes")
        
        for block_index in range(len(self.chain)):
            current_block = self.chain[block_index]
            hash_counts = {} 
            correct_hash = None
            
            # Collect hashes from other nodes
            for node in self.nodes:
                try:
                    response = requests.get(f'{node}/blockchain/block/{block_index}', timeout=5)
                    if response.status_code == 200:
                        block_data = response.json()
                        remote_hash = block_data['hash']
                        hash_counts[remote_hash] = hash_counts.get(remote_hash, 0) + 1
                        
                        if hash_counts[remote_hash] > len(self.nodes) / 2:
                            correct_hash = remote_hash
                            break
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error getting block from node {node}: {e}")
                    continue
            
            # If we found a consensus hash and it's different from our current hash
            if correct_hash and current_block.hash != correct_hash:
                logger.warning(f"Hash mismatch detected in block {block_index}")
                logger.warning(f"Local hash: {current_block.hash}")
                logger.warning(f"Consensus hash: {correct_hash}")
                
                # Verify the consensus hash meets difficulty requirement
                if correct_hash[:self.difficulty] == "0" * self.difficulty:
                    # Update the corrupted hash
                    self.chain[block_index].hash = correct_hash
                    logger.info(f"Corrected hash for block {block_index}")
                else:
                    logger.error(f"Consensus hash does not meet difficulty requirement for block {block_index}")

    # Add periodic hash verification
    def start_hash_verification(self):
        """Start periodic hash verification"""
        def verify_hashes_periodically():
            while True:
                self.verify_and_correct_hashes()
                time.sleep(30)  # Check every 30 seconds
            
        thread = threading.Thread(target=verify_hashes_periodically, daemon=True)
        thread.start()

    def generate_docker_node_addresses(self, num_nodes):
        """Generate node addresses for docker environment"""
        return [f"http://node{i}:500{i}" for i in range(1, num_nodes + 1)]
        
    def create_genesis_block(self):
        """Create the first block in the chain (genesis block)"""
        genesis_transaction = Transaction("Genesis Block - Created by " + self.node_id, "system")
        logger.info(
            f"Creating genesis block for node {self.node_id}",
            extra={'node_id': self.node_id}
        )
        # Create block with index 0, no previous hash, and genesis transaction
        genesis_block = Block(0, "0" * 64, [genesis_transaction])
        
        # Mine the genesis block with reduced difficulty for faster startup
        initial_difficulty = max(1, self.difficulty - 1)
        genesis_block.mine_block(initial_difficulty)
        
        logger.info(
            f"Genesis block created - Hash: {genesis_block.hash}",
            extra={'node_id': self.node_id}
        )
        return genesis_block

    def handle_blockchain_request(self, message):
        """Handle request for blockchain data"""
        try:
            serialized_chain = BlockchainSerializer.serialize_to_binary(self)
            return {
                "type": "blockchain_response",
                "data": base64.b64encode(serialized_chain).decode('utf-8'),
                "node_id": self.node_id
            }
        except Exception as e:
            logger.error(f"Error handling blockchain request: {e}")
            return None

    def handle_transaction_broadcast(self, message):
        """Handle received transaction broadcast"""
        if 'transaction' in message:
            try:
                transaction_data = message['transaction']
                transaction = Transaction.from_dict(transaction_data)
                
                # Add to pending transactions if not already present
                with self.lock:
                    transaction_exists = any(
                        t.crc == transaction.crc for t in self.pending_transactions
                    )
                    if not transaction_exists:
                        self.pending_transactions.append(transaction)
                        logger.info(f"Added broadcasted transaction to pending pool")
                
                return {
                    "type": "transaction_ack",
                    "node_id": self.node_id,
                    "transaction_crc": transaction.crc
                }
            except Exception as e:
                logger.error(f"Error processing transaction broadcast: {e}")
        return None

    def handle_block_broadcast(self, message):
        """Handle received block broadcast"""
        if 'block' in message:
            # Implementation will depend on how blocks are serialized
            # This is a simple placeholder
            return {
                "type": "block_ack",
                "node_id": self.node_id
            }
        return None
        
    def verify_and_correct_data(self):
        """Verify data integrity across the blockchain and correct corrupted data"""
        logger.info("Starting data verification across nodes")
        
        for block in self.chain:
            for transaction in block.transactions:
                # Verify transaction CRC
                if not transaction.verify_crc():
                    logger.warning(f"Transaction CRC verification failed in block {block.index}")
                    # Try to correct from other nodes
                    self.correct_transaction_data(block.index, transaction)
    
    def correct_transaction_data(self, block_index, corrupted_transaction):
        """Attempt to correct corrupted transaction data by querying other nodes"""
        logger.info(f"Attempting to correct transaction in block {block_index}")
        
        for node in self.nodes:
            try:
                response = requests.get(f'{node}/blockchain/block/{block_index}', timeout=5)
                if response.status_code == 200:
                    block_data = response.json()
                    # Find matching transaction
                    for tx_data in block_data['transactions']:
                        if tx_data['crc'] == corrupted_transaction.crc:
                            # Create corrected transaction
                            corrected_transaction = Transaction.from_dict(tx_data)
                            # Verify the corrected transaction
                            if corrected_transaction.verify_crc():
                                # Replace corrupted transaction
                                idx = self.chain[block_index].transactions.index(corrupted_transaction)
                                self.chain[block_index].transactions[idx] = corrected_transaction
                                logger.info(f"Successfully corrected transaction in block {block_index}")
                                return True
            except Exception as e:
                logger.error(f"Error getting block from node {node}: {e}")
                continue
        
        logger.error(f"Failed to correct transaction in block {block_index}")
        return False

    def start_health_check(self):
        """Start periodic health check of other nodes in the network"""
        def health_check_periodically():
            while True:
                self.check_node_health()
                time.sleep(self.health_check_interval)
                
        thread = threading.Thread(target=health_check_periodically, daemon=True)
        thread.start()
        logger.info(f"Started periodic health check with interval {self.health_check_interval}s")
    
    def check_node_health(self):
        """Check if other nodes in the network are alive"""
        logger.info("Performing health check of network nodes")
        
        # Parse current node ID to check for self connections
        current_node_path = f"node{self.node_id[-1]}:500{self.node_id[-1]}"
        
        for node in self.nodes:
            # Skip checking self
            if current_node_path in node:
                logger.debug(f"Skipping health check for self node: {node}")
                continue
                
            # Skip recently failed nodes to avoid unnecessary requests
            if node in self.failed_nodes and time.time() - self.failed_nodes[node] < 300:
                logger.debug(f"Skipping recently failed node: {node}")
                continue
                
            try:
                # Fix the health endpoint path
                response = requests.get(f"{node}/health", timeout=10)
                
                if response.status_code == 200:
                    if node in self.failed_nodes:
                        logger.info(f"Node {node} is back online")
                        del self.failed_nodes[node]
                else:
                    logger.warning(f"Node {node} returned non-200 status code: {response.status_code}")
                    self.failed_nodes[node] = time.time()
            except requests.exceptions.RequestException as e:
                # More detailed logging for different types of connection errors
                if "NewConnectionError" in str(e) or "ConnectionError" in str(e):
                    logger.debug(f"Node {node} is not yet available: {e}")
                elif "ReadTimeout" in str(e):
                    logger.warning(f"Read timeout while connecting to node {node}")
                else:
                    logger.warning(f"Failed to connect to node {node}: {e}")
                    
                self.failed_nodes[node] = time.time()
    
    def initial_sync(self):
        """Synchronize blockchain with other nodes when starting up"""
        logger.info(f"Starting initial blockchain synchronization for node {self.node_id}")
        
        # Add longer initial delay to ensure other nodes have time to start up
        # Extract node number from node_id for staggered startup
        try:
            node_num = int(self.node_id.replace('node', ''))
            initial_delay = 10 + (node_num * 3)  # Staggered delay based on node number
        except ValueError:
            initial_delay = 15  # Default delay if node_id doesn't contain a number
            
        logger.info(f"Node {self.node_id} waiting {initial_delay}s before initial sync...")
        time.sleep(initial_delay)
        
        max_length = len(self.chain)
        new_chain = None
        
        # Track number of successful connections
        successful_connections = 0
        max_retries = 3
        
        # First try to sync with just one or two nodes before trying all
        # This progressive approach is more reliable in a starting network
        if len(self.nodes) > 1:
            # Try specific nodes first (e.g., node1 is often started first)
            priority_nodes = [node for node in self.nodes if "node1:" in node or "node2:" in node]
            if priority_nodes:
                logger.info(f"Attempting to sync with priority nodes first: {priority_nodes}")
                for node in priority_nodes:
                    if self._sync_with_node(node, max_retries):
                        logger.info(f"Successfully synced with priority node {node}")
                        return  # Early return if successful with a priority node
        
        # Find the longest valid chain from all nodes
        # Shuffle nodes to avoid all nodes hitting the same target simultaneously
        all_nodes = list(self.nodes)
        random.shuffle(all_nodes)
        
        for node in all_nodes:
            # Skip self node
            if f"node{self.node_id[-1]}:500{self.node_id[-1]}" in node:
                logger.info(f"Skipping self node: {node}")
                continue
            
            if self._sync_with_node(node, max_retries):
                successful_connections += 1
                # Once we've successfully connected to a few nodes, we can stop
                # This prevents overloading the network with sync requests
                if successful_connections >= 2:  # Just need a couple successful connections
                    break
        
        logger.info(f"Sync process completed. Successful connections: {successful_connections}/{len(self.nodes)-1}")
    
    def _sync_with_node(self, node, max_retries=3):
        """Sync with a specific node with retry logic"""
        # Start with short retry delay and implement exponential backoff with jitter
        retry_delay = 2
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                logger.info(f"Attempting to sync with node {node} (attempt {retry_count + 1})")
                
                # Add connection timeout and longer read timeout
                response = requests.get(
                    f"{node}/chain", 
                    timeout=(5, 20)  # 5s connect timeout, 20s read timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    chain_length = data['length']
                    chain = data['chain']
                    
                    logger.info(f"Received chain from {node} with length {chain_length}")
                    
                    # Check if chain is longer and valid
                    if chain_length > len(self.chain) and self.is_chain_valid(chain):
                        self.replace_chain(chain)
                        logger.info(f"Replaced chain with longer valid chain from {node} (length: {chain_length})")
                    
                    return True  # Successfully synced
                else:
                    logger.warning(f"Node {node} returned status code {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                logger.warning(f"Error syncing with node {node}: {e} (attempt {retry_count + 1})")
                
            # Increment retry count and apply exponential backoff with jitter
            retry_count += 1
            if retry_count < max_retries:
                # Add jitter to avoid thundering herd problem
                jitter = random.uniform(0, 0.1 * retry_delay)
                retry_delay = (retry_delay * 2) + jitter  # Exponential backoff with jitter
                logger.info(f"Retrying in {retry_delay:.2f} seconds...")
                time.sleep(retry_delay)
        
        return False  # Failed to sync with this node
    
    def is_chain_valid(self, chain):
        """Check if a blockchain is valid"""
        # Basic validation logic
        for i in range(1, len(chain)):
            block = chain[i]
            prev_block = chain[i-1]
            
            # Check block index continuity
            if block['index'] != prev_block['index'] + 1:
                return False
                
            # Check block links to previous block
            if block['previous_hash'] != prev_block['hash']:
                return False
                
            # Verify block hash meets difficulty
            if block['hash'][:self.difficulty] != '0' * self.difficulty:
                return False
        
        return True
    
    def replace_chain(self, new_chain):
        """Replace current chain with a new valid chain"""
        # Convert dictionary chain to Block objects
        self.chain = []
        for block_data in new_chain:
            transactions = []
            for tx_data in block_data['transactions']:
                transactions.append(Transaction.from_dict(tx_data))
                
            block = Block(
                block_data['index'],
                block_data['previous_hash'],
                transactions,
                block_data['timestamp']
            )
            block.hash = block_data['hash']
            block.nonce = block_data['nonce']
            self.chain.append(block)
            
        logger.info(f"Chain replaced with new chain of length {len(self.chain)}")
        
    def export_and_share_blockchain(self):
        """Export and share blockchain with other nodes via P2P network"""
        logger.info("Exporting and sharing blockchain data via P2P")
        # This implementation will depend on the P2P network capabilities
        # For now, we'll make it a placeholder
        try:
            # In a real implementation, this would serialize and share the blockchain
            # through the P2P network rather than direct HTTP requests
            logger.info("Blockchain ready for P2P sharing")
        except Exception as e:
            logger.error(f"Error exporting blockchain for P2P sharing: {e}")

def create_blockchain_app():
    """Create and configure the blockchain Flask application"""
    # Create Flask app
    app = Flask(__name__)
    
    # Initialize blockchain node with node_id from environment variable
    node_id = os.getenv('NODE_ID', 'node1')
    blockchain = BlockchainNode(node_id)
    
    # Apply CORS to the app
    CORS(app, origins=["*"], supports_credentials=True, allow_headers=["*"])
    
    # Import P2P Blueprint module
    from flask_p2p_endpoints import create_p2p_blueprint
    
    # Register P2P blueprint
    p2p_blueprint = create_p2p_blueprint(blockchain)
    app.register_blueprint(p2p_blueprint, url_prefix='/p2p')
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        response = jsonify({"status": "healthy", "node_id": node_id})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
    
    @app.route('/chain', methods=['GET'])
    def get_chain():
        """Get the full blockchain"""
        chain_data = []
        for block in blockchain.chain:
            chain_data.append({
                'index': block.index,
                'previous_hash': block.previous_hash,
                'timestamp': block.timestamp,
                'transactions': [t.to_dict() for t in block.transactions],
                'hash': block.hash,
                'nonce': block.nonce
            })
        
        return jsonify({
            'chain': chain_data,
            'length': len(chain_data),
            'node_id': node_id
        }), 200
    
    @app.route('/transaction/new', methods=['POST'])
    def new_transaction():
        """Add a new transaction to the blockchain"""
        values = request.get_json()
        
        required = ['data', 'type']
        if not all(k in values for k in required):
            return jsonify({'message': 'Missing required fields'}), 400
        
        # Handle image type data
        if values['type'] == 'image' and isinstance(values['data'], str):
            try:
                # If data is base64, decode it
                if ';base64,' in values['data']:
                    base64_data = values['data'].split(';base64,')[1]
                else:
                    base64_data = values['data']
                
                data = base64.b64decode(base64_data)
            except Exception as e:
                logger.error(f"Error decoding image data: {e}")
                return jsonify({'message': 'Invalid image data'}), 400
        else:
            data = values['data']
        
        # Create and add transaction
        transaction = Transaction(data, values['type'])
        blockchain.pending_transactions.append(transaction)
        
        # Broadcast transaction to peers
        blockchain.broadcast_transaction(transaction)
        
        return jsonify({'message': f'Transaction will be added to Block {len(blockchain.chain)}'}), 201
    
    @app.route('/mine', methods=['GET'])
    def mine():
        """Mine a new block"""
        with blockchain.lock:
            if blockchain.mining_status["is_mining"]:
                return jsonify({
                    'message': 'Mining already in progress',
                    'progress': blockchain.mining_status["progress"]
                }), 202
            
            # Start mining
            blockchain.mining_status["is_mining"] = True
            blockchain.mining_status["progress"] = 0
        
        # Start mining in a separate thread
        def mine_thread():
            try:
                block = blockchain.mine_block()
                response = {
                    'message': 'New Block Forged',
                    'index': block.index,
                    'transactions': [t.to_dict() for t in block.transactions],
                    'hash': block.hash
                }
                # Reset mining status
                with blockchain.lock:
                    blockchain.mining_status["is_mining"] = False
                    blockchain.mining_status["progress"] = 100
                
                # Broadcast new block
                blockchain.broadcast_block(block)
                
                logger.info(f"Block #{block.index} mined successfully")
            except Exception as e:
                logger.error(f"Error mining block: {e}")
                with blockchain.lock:
                    blockchain.mining_status["is_mining"] = False
                    blockchain.mining_status["progress"] = 0
        
        threading.Thread(target=mine_thread).start()
        
        return jsonify({
            'message': 'Mining started',
            'status': 'processing'
        }), 202
    
    @app.route('/block/<int:index>', methods=['GET'])
    def get_block(index):
        """Get a specific block by index"""
        if index < 0 or index >= len(blockchain.chain):
            return jsonify({'message': 'Block not found'}), 404
            
        block = blockchain.chain[index]
        return jsonify({
            'index': block.index,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp,
            'transactions': [t.to_dict() for t in block.transactions],
            'hash': block.hash,
            'nonce': block.nonce
        }), 200
        
    @app.route('/p2p/peers', methods=['GET'])
    def get_peers():
        """Get list of peers in the P2P network"""
        return jsonify({
            'peers': list(blockchain.p2p.peers),
            'node_id': node_id
        }), 200
    
    @app.route('/p2p/torrent/<string:infohash>', methods=['GET'])
    def get_torrent(infohash):
        """Get torrent metadata by infohash"""
        if infohash in blockchain.p2p.torrent_files:
            return jsonify({
                'metadata': blockchain.p2p.torrent_files[infohash]['metadata'],
                'node_id': node_id
            }), 200
        return jsonify({'message': 'Torrent not found'}), 404
    
    @app.route('/p2p/piece/<string:infohash>/<int:piece_index>', methods=['GET'])
    def get_piece(infohash, piece_index):
        """Get a specific piece of a torrent file"""
        if infohash in blockchain.p2p.torrent_files:
            metadata = blockchain.p2p.torrent_files[infohash]['metadata']
            piece_length = metadata['info']['piece length']
            
            piece_data = blockchain.p2p.get_torrent_piece(infohash, piece_index, piece_length)
            
            if piece_data:
                return jsonify({
                    'data': base64.b64encode(piece_data).decode('utf-8'),
                    'piece_index': piece_index,
                    'infohash': infohash,
                }), 200
                
        return jsonify({'message': 'Piece not found'}), 404
    
    @app.after_request
    def after_request(response):
        """Add CORS headers to every response"""
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response
    
    logger.info(f"Blockchain app created for node {node_id}")
    return app