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
        # Log transaction creation with CRC
        logger.info(
            f"Created new transaction - Type: {transaction_type}, CRC: {self.crc}",
            extra={'node_id': os.getenv('NODE_ID', 'unknown')}
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
                "confirmations": list(self.confirmations)
            }
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp,
            "crc": self.crc,
            "confirmations": list(self.confirmations)
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
        self.chain = [self.create_genesis_block()]
        self.difficulty = difficulty
        self.pending_transactions = []
        self.nodes = self.generate_docker_node_addresses(num_nodes)
        self.lock = threading.Lock()
        self.mining_status = {"is_mining": False, "progress": 0}
        self.health_check_interval = 30
        self.failed_nodes = {}
        self.start_health_check()
        # Initial synchronization with network
        self.initial_sync()
        self.start_hash_verification()
        self.start_data_verification()

    def start_data_verification(self):
        """Start periodic data verification"""
        def verify_data_periodically():
            while True:
                self.verify_and_correct_data()
                time.sleep(30)  # Check every 30 seconds
            
        thread = threading.Thread(target=verify_data_periodically, daemon=True)
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

    def initial_sync(self):
        """Perform initial synchronization when node starts"""
        logger.info(f"Node {self.node_id} performing initial synchronization")
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Get chains from all available nodes
                longest_chain = None
                max_length = len(self.chain)
                
                for node in self.nodes:
                    try:
                        response = requests.get(f'{node}/blockchain/chain', timeout=10)
                        if response.status_code == 200:
                            chain_data = response.json()
                            chain_length = chain_data['length']
                            
                            if chain_length > max_length:
                                # Validate the chain before accepting it
                                chain = self.reconstruct_chain(chain_data['chain'])
                                if chain and self.is_chain_valid(chain):
                                    longest_chain = chain
                                    max_length = chain_length
                    except requests.exceptions.RequestException as e:
                        logger.warning(f"Could not connect to node {node} during initial sync: {e}")
                        continue
                
                if longest_chain:
                    self.chain = longest_chain
                    logger.info(f"Initial sync successful - Chain length: {len(self.chain)}")
                    self.verify_chain_integrity()  # Verify chain integrity after sync
                    return True
                else:
                    logger.info("No longer valid chain found, keeping genesis block")
                    return True
                    
            except Exception as e:
                logger.error(f"Error during initial sync (attempt {retry_count + 1}): {e}")
                retry_count += 1
                time.sleep(5)  # Wait before retry
                
        logger.warning("Initial sync failed after maximum retries")
        return False

    def reconstruct_chain(self, chain_data):
        """
        Simply reconstructs chain from JSON data
        """
        try:
            reconstructed_chain = []
            
            for block_data in chain_data:
                # Reconstruct transactions
                transactions = []
                for tx_data in block_data['transactions']:
                    transaction = Transaction.from_dict(tx_data)
                    transactions.append(transaction)

                block = Block(
                    block_data['index'],
                    block_data['previous_hash'],
                    transactions,
                    block_data['timestamp'],
                )
                
                block.hash = block_data['hash']
                block.nonce = block_data.get('nonce', 0)
                
                reconstructed_chain.append(block)
                
            return reconstructed_chain
                
        except Exception as e:
            logger.error(f"Error during chain reconstruction: {str(e)}")
            return None

    def synchronize_node(self, node):
        """Synchronizes with another node with improved error handling"""
        logger.info(f"Starting synchronization with node {node}")
        try:
            # Get the remote chain
            chain_response = requests.get(f'{node}/blockchain/chain', timeout=10)
            if chain_response.status_code != 200:
                logger.error(f"Failed to get chain from node {node}: {chain_response.status_code}")
                return False
                
            remote_chain_data = chain_response.json()
            logger.info(f"Received chain data from {node}, length: {remote_chain_data['length']}")
            
            # Reconstruct and validate the chain
            remote_chain = self.reconstruct_chain(remote_chain_data['chain'])
            if not remote_chain:
                logger.error(f"Failed to reconstruct chain from {node}")
                return False
            
            # If the remote chain is valid and longer, replace our chain
            if len(remote_chain) > len(self.chain):
                with self.lock:
                    self.chain = remote_chain
                    self.verify_chain_integrity()
                    logger.info(f"Successfully synchronized with {node}. New chain length: {len(self.chain)}")
                    return True
            else:
                logger.info(f"Remote chain from {node} is not longer than current chain")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Network error during synchronization with {node}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during synchronization with {node}: {str(e)}")
            return False

    def check_nodes_health(self):
        """Enhanced health check with better synchronization handling"""
        logger.info("Starting nodes health check")
        for node in self.nodes:
            try:
                # Check node health
                response = requests.get(f'{node}/blockchain/health', timeout=5)
                if response.status_code == 200:
                    if node in self.failed_nodes:
                        logger.info(f"Node {node} recovered - initiating sync")
                        if self.synchronize_node(node):
                            del self.failed_nodes[node]
                            logger.info(f"Successfully synchronized with recovered node {node}")
                        else:
                            logger.warning(f"Failed to synchronize with recovered node {node}")
                    else:
                        # Periodic sync check even for healthy nodes
                        self.synchronize_node(node)
                else:
                    self.handle_node_failure(node)
            except requests.exceptions.RequestException:
                self.handle_node_failure(node)

    def handle_node_failure(self, node):
        """Handle node failure by marking it as failed and initiating recovery"""
        logger.warning(f"Node {node} is down - marking as failed")
        if node not in self.failed_nodes:
            logger.error(f"Node {node} is down - marking as failed")
            self.failed_nodes[node] = time.time()
            self.synchronize_node(node)

    def start_health_check(self):
        logger.info("Starting periodic health check for nodes")
        """Rozpoczyna okresowe sprawdzanie stanu węzłów"""
        def health_check():
            while True:
                self.check_nodes_health()
                time.sleep(self.health_check_interval)
                
        thread = threading.Thread(target=health_check, daemon=True)
        thread.start()

    def verify_chain_integrity(self):
            """Weryfikuje integralność blockchain i naprawia uszkodzenia"""
            logger.info("Verifying chain integrity")
            corrupted_blocks = []
            
            for i in range(1, len(self.chain)):
                block = self.chain[i]
                prev_block = self.chain[i-1]
                
                if block.previous_hash != prev_block.hash:
                    corrupted_blocks.append(i)
                    continue
                    
                if block.hash != block.calculate_hash():
                    corrupted_blocks.append(i)
                    continue
                    
                for tx in block.transactions:
                    if not tx.verify_crc():
                        corrupted_blocks.append(i)
                        break

            if corrupted_blocks:
                logger.error(f"Found corrupted blocks: {corrupted_blocks}")
                self.verify_and_correct_data()  # First try to repair corrupted data
                self.repair_corrupted_blocks(corrupted_blocks)  # Then repair blocks if needed

    def repair_corrupted_blocks(self, corrupted_indices):
        """Naprawia uszkodzone bloki poprzez pobranie poprawnych kopii od innych węzłów"""
        logger.info(f"Repairing corrupted blocks: {corrupted_indices}")
        
        for index in corrupted_indices:
            consensus_data = None
            consensus_count = 0
            
            for node in self.nodes:
                try:
                    response = requests.get(
                        f'{node}/blockchain/block/{index}',
                        timeout=5
                    )
                    
                    if response.status_code == 200:
                        block_data = response.json()
                        
                        # Reconstruct and verify block
                        transactions = [Transaction.from_dict(t) for t in block_data['transactions']]
                        if all(tx.verify_crc() for tx in transactions):  # Verify all transactions
                            if not consensus_data:
                                consensus_data = block_data
                                consensus_count = 1
                            elif block_data == consensus_data:
                                consensus_count += 1
                                
                            if consensus_count > 5:
                                # Reconstruct the block
                                block = Block(
                                    consensus_data['index'],
                                    consensus_data['previous_hash'],
                                    transactions,
                                    consensus_data['timestamp']
                                )
                                block.hash = consensus_data['hash']
                                block.nonce = consensus_data['nonce']
                                
                                if self.verify_block(block):
                                    self.chain[index] = block
                                    logger.info(f"Successfully repaired block {index}")
                                    break
                                
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error getting block from node {node}: {e}")
                    continue

    def verify_and_correct_data(self):
        """Verify and correct data in transactions across nodes"""
        logger.info("Starting data verification across nodes")
        
        for block_index, block in enumerate(self.chain):
            for tx_index, transaction in enumerate(block.transactions):
                data_counts = {}
                correct_data = None
                
                # Collect data from other nodes
                for node in self.nodes:
                    try:
                        response = requests.get(
                            f'{node}/blockchain/block/{block_index}',
                            timeout=5
                        )
                        if response.status_code == 200:
                            block_data = response.json()
                            if len(block_data['transactions']) > tx_index:
                                remote_tx = block_data['transactions'][tx_index]
                                remote_data = remote_tx['data']
                                
                                # Handle base64 encoded image data
                                if transaction.type == "image":
                                    try:
                                        # Ensure data is properly base64 encoded
                                        if isinstance(remote_data, str):
                                            remote_data = base64.b64decode(remote_data)
                                    except:
                                        logger.error(f"Invalid base64 data from node {node}")
                                        continue
                                
                                data_key = remote_data if isinstance(remote_data, str) else base64.b64encode(remote_data).decode('utf-8')
                                data_counts[data_key] = data_counts.get(data_key, 0) + 1
                                
                                if data_counts[data_key] > len(self.nodes) / 2:
                                    correct_data = remote_data
                                    break
                                    
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Error getting block from node {node}: {e}")
                        continue
                
                # If we found consensus data and it's different from our current data
                current_tx_dict = transaction.to_dict()
                current_data = current_tx_dict['data']
                
                if correct_data and (
                    (isinstance(correct_data, str) and current_data != correct_data) or
                    (isinstance(correct_data, bytes) and base64.b64decode(current_data) != correct_data)
                ):
                    logger.warning(f"Data mismatch detected in block {block_index}, transaction {tx_index}")
                    
                    # Create consensus transaction
                    consensus_tx = Transaction(
                        correct_data,
                        transaction.type
                    )
                    
                    if consensus_tx.verify_crc():
                        # Update the corrupted data
                        transaction.data = correct_data
                        transaction.crc = consensus_tx.crc
                        logger.info(f"Corrected data for block {block_index}, transaction {tx_index}")
                    else:
                        logger.error(f"Consensus data CRC verification failed for block {block_index}, transaction {tx_index}")

    def verify_transaction(self, transaction_data):
        """Verify a transaction received from another node"""
        logger.info(
            f"Verifying transaction - CRC: {transaction_data.get('crc')}",
            extra={'node_id': self.node_id}
        )
        try:
            transaction = Transaction.from_dict(transaction_data)
            verification_result = transaction.verify_crc()
            logger.info(
                f"Transaction verification result - Valid: {verification_result}, "
                f"CRC: {transaction.crc}",
                extra={'node_id': self.node_id}
            )
            if verification_result:
                transaction.confirmations.add(f"http://{self.node_id}:5001")
                self.add_transaction(transaction)
                return True
            return False
        except Exception as e:
            logger.error(
                f"Transaction verification failed: {e}",
                extra={'node_id': self.node_id}
            )
            return False

    def generate_docker_node_addresses(self, num_nodes):
        """Generuje adresy węzłów używając nazw serwisów Docker"""
        node_addresses = []
        for i in range(1, num_nodes + 1):
            if f"node{i}" != self.node_id:
                node_addresses.append(f"http://node{i}:500{i}")
        return node_addresses

    def broadcast_transaction(self, transaction):
        """Broadcast transaction to other nodes and collect confirmations"""
        logger.info("Broadcasting transaction")
        logger.info(f"Current node: {self.node_id}")
        logger.info(f"Broadcasting to nodes: {self.nodes}")

        def confirm_with_node(node_address):
            try:
                logger.info(f"Contacting node: {node_address}")
                response = requests.post(
                    f"{node_address}/blockchain/verify_transaction",
                    json=transaction.to_dict(),
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info(f"Node {node_address} confirmed transaction")
                    # Dodaj potwierdzenie do transakcji
                    transaction.confirmations.add(node_address)
                    return node_address
                else:
                    logger.warning(f"Node {node_address} rejected transaction with status {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Error contacting node {node_address}: {e}")
            return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(confirm_with_node, node) for node in self.nodes]
            confirmations = set()
            for future in as_completed(futures):
                result = future.result()
                if result:
                    confirmations.add(result)

        node_num = int(self.node_id.replace('node', ''))
        port = f"500{node_num}"
        transaction.confirmations.add(f"http://{self.node_id}:{port}")
        
        # required_confirmations = (len(self.nodes) + 1) // 2  # +1 aby uwzględnić bieżący węzeł
        required_confirmations = 6
        logger.info(f"Confirmations: {len(transaction.confirmations)} / {len(self.nodes) + 1} required: {required_confirmations}")
        return len(transaction.confirmations) >= required_confirmations


    def broadcast_mined_block(self, block):
        """Broadcast mined block to other nodes for verification and consensus"""
        logger.info(f"Broadcasting mined block {block.index} to network")
        
        confirmations = set()
        block_data = {
            'index': block.index,
            'previous_hash': block.previous_hash,
            'timestamp': block.timestamp,
            'transactions': [t.to_dict() for t in block.transactions],
            'hash': block.hash,
            'nonce': block.nonce
        }

        def get_node_confirmation(node):
            try:
                response = requests.post(
                    f'{node}/blockchain/verify_mined_block',
                    json=block_data,
                    timeout=5
                )
                if response.status_code == 200:
                    logger.info(f"Node {node} confirmed mined block")
                    return node
            except Exception as e:
                logger.error(f"Error getting confirmation from {node}: {e}")
            return None

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_node = {executor.submit(get_node_confirmation, node): node 
                            for node in self.nodes}
            for future in as_completed(future_to_node):
                if future.result():
                    confirmations.add(future.result())

        required_confirmations = (len(self.nodes) + 1) // 2
        return len(confirmations) >= required_confirmations

    def is_chain_valid(self, chain):
        """Verify if a given chain is valid"""
        logger.info("Verifying chain")
        for i in range(1, len(chain)):
            current_block = chain[i]
            previous_block = chain[i-1]

            # Verify current block hash
            if current_block.hash != current_block.calculate_hash():
                logger.error(f"Block {current_block.index} hash mismatch")
                logger.error(f"Calculated: {current_block.calculate_hash()}")
                logger.error(f"Stored: {current_block.hash}")
                return False

            # Verify chain continuity
            if current_block.previous_hash != previous_block.hash:
                logger.error(f"Block {current_block.index} previous hash mismatch")
                logger.error(f"Expected: {previous_block.hash}")
                logger.error(f"Received: {current_block.previous_hash}")
                return False

            # Verify block mining difficulty
            if current_block.hash[:self.difficulty] != "0" * self.difficulty:
                logger.error(f"Block {current_block.index} does not meet difficulty requirement 1")   
                logger.error(f"Block hash: {current_block.hash}")
                logger.error(f"Difficulty: {self.difficulty}")
                return False

            # Verify all transactions in the block
            for transaction in current_block.transactions:
                if not transaction.verify_crc():
                    logger.error(f"Transaction CRC verification failed - Block: {current_block.index}")
                    logger.error(f"Transaction CRC: {transaction.crc}")
                    return False

        return True

    def resolve_conflicts(self):
        """
        Consensus algorithm. Resolves conflicts by replacing our chain with the longest valid chain in the network.
        Returns True if our chain was replaced, False otherwise.
        """
        new_chain = None
        current_length = len(self.chain)
        
        logger.info(f"Starting chain resolution. Current length: {current_length}")

        # Get and verify chains from all nodes
        for node in self.nodes:
            try:
                logger.info(f"Contacting node: {node}")
                logger.info(f'{node}/blockchain/chain')
                response = requests.get(f'{node}/blockchain/chain', timeout=5)
                logger.info(f"Response status: {response.status_code}")
                logger.info(f"Response data: {response.json()}")
                if response.status_code == 200:
                    chain_data = response.json()
                    chain_length = chain_data['length']
                    chain = []

                    # Reconstruct the chain from JSON data
                    for block_data in chain_data['chain']:
                        transactions = [Transaction.from_dict(t) for t in block_data['transactions']]
                        block = Block(
                            block_data['index'],
                            block_data['previous_hash'],
                            transactions,
                            block_data['timestamp']
                        )
                        block.hash = block_data['hash']
                        chain.append(block)

                    # Check if the chain is longer and valid
                    if chain_length > current_length and self.is_chain_valid(chain):
                        current_length = chain_length
                        new_chain = chain
                        logger.info(f"Found valid longer chain from {node}, length: {chain_length}")

            except requests.exceptions.RequestException as e:
                logger.error(f"Error contacting node {node}: {e}")
                continue

        # Replace our chain if we found a valid longer one
        if new_chain:
            self.chain = new_chain
            logger.info("Chain replaced successfully")
            return True

        logger.info("Current chain is authoritative")
        return False

    def create_genesis_block(self):
        return Block(0, "0", [Transaction("Genesis Block")], time.time())

    def get_latest_block(self):
        return self.chain[-1]

    def add_transaction(self, transaction):
        if not transaction.verify_crc():
            raise ValueError("Transaction CRC verification failed")
        
        logger.info(f"Adding transaction to pending pool - CRC: {transaction.crc}")
        
        with self.lock:
            self.pending_transactions.append(transaction)
            logger.info(f"Transaction added to pending pool - pending_transactions: {len(self.pending_transactions)}")


    def process_image(self, image_data):
        """Complete image processing pipeline"""
        logger.info("Starting image processing pipeline")
        
        try:
            # 1. Create transaction and get initial CRC
            transaction = Transaction(image_data, "image")
            initial_crc = transaction.calculate_crc()
            logger.info(f"Initial CRC: {initial_crc}")
            
            # 2. Verify transaction
            if not transaction.verify_crc():
                raise ValueError("Initial CRC verification failed")
            
            # 3. Broadcast to network and collect confirmations
            confirmation_result = self.broadcast_transaction(transaction)
            if not confirmation_result:
                raise ValueError("Failed to get network consensus")
            
            # 4. Add to pending transactions (if not already added by verify_transaction)
            if transaction not in self.pending_transactions:
                self.add_transaction(transaction)
            
            # 5. Mine block automatically if we have enough confirmations
            mining_result = self.mine_pending_transactions()
            

            logger.info("5 w process",mining_result)
            
            return {
                "success": True,
                "initial_crc": initial_crc,
                "final_crc": transaction.crc,
                "confirmations": len(transaction.confirmations),
                "mining_status": mining_result.get("status", "pending"),
                "mining_message": mining_result.get("message", "Transaction added to pending pool")
            }
            
        except Exception as e:
            logger.error(f"Image processing pipeline failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
          
    def verify_block(self, block):
            """Enhanced block verification with special handling for genesis block"""
            # Special case for genesis block
            if block.index == 0:
                if block.previous_hash != "0":
                    logger.error("Genesis block must have previous_hash '0'")
                    return False
                # For genesis block, we don't check mining difficulty
                return all(transaction.verify_crc() for transaction in block.transactions)
            
            # For all other blocks
            # Verify block meets difficulty requirement
            if block.hash[:self.difficulty] != "0" * self.difficulty:
                logger.info(f"self.difficulty: {self.difficulty}, block.hash: {block.hash}")
                logger.error(f"Block {block.index} does not meet difficulty requirement 2")
                return False

            # Verify transactions
            if not all(transaction.verify_crc() for transaction in block.transactions):
                logger.error(f"Transaction verification failed in block {block.index}")
                return False

            return True

    def mine_pending_transactions(self):
        logger.info("Starting mining process xxc")
        logger.info(self.pending_transactions)
        with self.lock:
            if not self.pending_transactions:
                return {
                    "success": False,
                    "message": "No pending transactions to mine",
                    "status": "idle"
                }

            try:
                self.mining_status["is_mining"] = True
                self.mining_status["progress"] = 0
                
                # Filtruj transakcje z wystarczającą liczbą potwierdzeń
                required_confirmations = (len(self.nodes) + 1) // 2
                valid_transactions = [
                    tx for tx in self.pending_transactions 
                    if len(tx.confirmations) >= required_confirmations
                ]

                logger.info(f"Valid transactions: {len(valid_transactions)}")


                if not valid_transactions:
                    return {
                        "success": False,
                        "message": "No transactions with sufficient confirmations",
                        "status": "waiting_for_confirmations"
                    }

                block = Block(
                    len(self.chain),
                    self.get_latest_block().hash,
                    valid_transactions
                )

                
                self.mining_status["progress"] = 50
                block.mine_block(self.difficulty)

                
                # Broadcast wykopanego bloku do sieci
                if not self.broadcast_mined_block(block):
                    logger.info("Failed to get network consensus for mined block")
                    return {
                        "success": False,
                        "message": "Failed to get network consensus for mined block",
                        "status": "consensus_failed"
                    }

                self.mining_status["progress"] = 75
                self.chain.append(block)

                
                # Usuń przetworzone transakcje
                self.pending_transactions = [
                    tx for tx in self.pending_transactions 
                    if tx not in valid_transactions
                ]

                logger.info(f"Pending transactions: {len(self.pending_transactions)}")  
                
                self.mining_status["progress"] = 100
                
                return {
                    "success": True,
                    "message": "Block mined and confirmed by network",
                    "status": "completed",
                    "block": {
                        "index": block.index,
                        "hash": block.hash,
                        "transaction_count": len(block.transactions)
                    }
                }
                
            except Exception as e:
                logger.exception(f"Error during mining: {e}")
                return {
                    "success": False,
                    "message": f"Mining failed: {str(e)}",
                    "status": "error"
                }
            finally:
                self.mining_status["is_mining"] = False

def create_blockchain_app():
    app = Flask(__name__)
    node_id = os.getenv('NODE_ID', 'node1')
    blockchain = BlockchainNode(node_id=node_id)

    @app.route('/simulate/failure', methods=['POST'])
    def simulate_failure():
        data = request.get_json()
        failure_type = data.get('type', 'node_down')
        
        if failure_type == 'node_down':
            logger.critical("Simulating node down failure. Exiting process.")
            os._exit(1)
            
        elif failure_type == 'data_corruption':
            logger.warning("Simulating data corruption")
            if len(blockchain.chain) > 1:
                block_idx = random.randint(1, len(blockchain.chain) - 1)
                block = blockchain.chain[block_idx]
                if block.transactions:
                    block.transactions[0].data = "corrupted_data"
                    return jsonify({'message': 'Data corruption simulated'}), 200
                    
        elif failure_type == 'hash_corruption':
            logger.warning("Simulating hash corruption")
            if len(blockchain.chain) > 1:
                block_idx = random.randint(1, len(blockchain.chain) - 1)
                blockchain.chain[block_idx].hash = "corrupted_hash"
                return jsonify({'message': 'Hash corruption simulated'}), 200

        return jsonify({'message': 'Unknown failure type'}), 400

    @app.route('/health', methods=['GET'])
    def health_check():
        return jsonify({'status': 'healthy', 'node_id': blockchain.node_id}), 200

    @app.route('/synchronize', methods=['POST'])
    def synchronize():
        data = request.get_json()
        try:
            new_chain = []
            incoming_chain_length = len(data['chain'])
            current_chain_length = len(blockchain.chain)
            
            # Jeśli łańcuchy są tej samej długości, porównaj hash ostatniego bloku
            if incoming_chain_length == current_chain_length:
                current_last_hash = blockchain.chain[-1].hash
                incoming_last_hash = data['chain'][-1]['hash']
                
                if current_last_hash == incoming_last_hash:
                    logger.info("Chains are identical - no synchronization needed")
                    return jsonify({'message': 'Chains already synchronized'}), 200
            
            # Rekonstrukcja łańcucha blok po bloku
            for block_data in data['chain']:
                try:
                    # Rekonstruuj transakcje
                    transactions = []
                    for tx_data in block_data['transactions']:
                        transaction = Transaction.from_dict(tx_data)
                        if not transaction.verify_crc():
                            raise ValueError(f"Transaction CRC verification failed for transaction {tx_data['crc']}")
                        transactions.append(transaction)
                    
                    # Stwórz nowy blok
                    block = Block(
                        block_data['index'],
                        block_data['previous_hash'],
                        transactions,
                        block_data['timestamp']
                    )
                    
                    # Ustaw nonce i przelicz hash
                    block.nonce = block_data['nonce']
                    calculated_hash = block.calculate_hash()
                    
                    # Porównaj otrzymany hash z przeliczonym
                    if calculated_hash != block_data['hash']:
                        logger.error(f"Hash mismatch for block {block.index}")
                        logger.error(f"Calculated: {calculated_hash}")
                        logger.error(f"Received: {block_data['hash']}")
                        return jsonify({'message': f'Hash mismatch for block {block.index}'}), 400
                    
                    block.hash = calculated_hash
                    new_chain.append(block)
                    
                except Exception as e:
                    logger.error(f"Error reconstructing block {block_data['index']}: {str(e)}")
                    return jsonify({'message': f'Block reconstruction failed: {str(e)}'}), 400
                
            # Weryfikuj cały łańcuch
            if not blockchain.is_chain_valid(new_chain):
                logger.error("Invalid chain received during synchronization")
                return jsonify({'message': 'Invalid chain received'}), 400
                
            # Aktualizuj chain tylko jeśli jest dłuższy lub jesteśmy w trybie recovery
            is_recovery_mode = len(blockchain.chain) <= 1
            if len(new_chain) > len(blockchain.chain) or is_recovery_mode:
                blockchain.chain = new_chain
                logger.info(f"Chain synchronized successfully - length: {len(new_chain)}")
                
                # Aktualizuj pending transactions
                chain_transactions = {tx.crc for block in new_chain for tx in block.transactions}
                new_pending_transactions = [
                    Transaction.from_dict(tx_data)
                    for tx_data in data['pending_transactions']
                    if tx_data['crc'] not in chain_transactions
                ]
                
                blockchain.pending_transactions = new_pending_transactions
                logger.info(f"Updated pending transactions pool - count: {len(blockchain.pending_transactions)}")
                
                return jsonify({'message': 'Synchronization successful'}), 200
            else:
                logger.info("Current chain is up to date")
                return jsonify({'message': 'Current chain is up to date'}), 200

        except Exception as e:
            logger.error(f"Error during synchronization: {e}")
            return jsonify({'message': f'Synchronization failed: {str(e)}'}), 500
    
    @app.route('/block/<int:index>', methods=['GET'])
    def get_block(index):
        if 0 <= index < len(blockchain.chain):
            block = blockchain.chain[index]
            block_data = {
                'index': block.index,
                'previous_hash': block.previous_hash,
                'timestamp': block.timestamp,
                'transactions': [t.to_dict() for t in block.transactions],
                'hash': block.hash,
                'nonce': block.nonce
            }
            return jsonify(block_data), 200
        return jsonify({'message': 'Block not found'}), 404

    @app.route('/transaction/new', methods=['POST'])
    def new_transaction():
        values = request.get_json()
        logger.info(f"Received new transaction request: {values}")

        try:
            transaction = Transaction(values['data'], values.get('type', 'generic'))
            logger.info("Created transaction")

            if blockchain.broadcast_transaction(transaction):
                blockchain.add_transaction(transaction)
                logger.info("Transaction successfully added and broadcasted")
                return jsonify({'message': 'Transaction added successfully!'}), 201
            logger.warning("Transaction rejected by the network")
            return jsonify({'message': 'Transaction rejected by network'}), 400
        except Exception as e:
            logger.exception(f"Error in new_transaction: {e}")
            return jsonify({'message': str(e)}), 400
        

    @app.route('/verify_mined_block', methods=['POST'])
    def verify_mined_block():
        block_data = request.get_json()

        logger.info("Received mined block for verification")
        
        # Zrekonstruuj blok
        transactions = [Transaction.from_dict(t) for t in block_data['transactions']]
        block = Block(
            block_data['index'],
            block_data['previous_hash'],
            transactions,
            block_data['timestamp']
        )
        block.nonce = block_data['nonce']
        block.hash = block_data['hash']
        
        # Weryfikuj blok
        if not blockchain.verify_block(block):
            return jsonify({'message': 'Block verification failed'}), 400
            
        # Weryfikuj, czy hash spełnia trudność
        if block.hash[:blockchain.difficulty] != "0" * blockchain.difficulty:
            return jsonify({'message': 'Block does not meet difficulty requirement'}), 400
        
        blockchain.chain.append(block)
            
        return jsonify({'message': 'Block verified'}), 200

    @app.route('/verify_transaction', methods=['POST'])
    def verify_transaction():
        transaction_data = request.get_json()
        logger.info("Transaction received for verification")

        if blockchain.verify_transaction(transaction_data):
            logger.info("Transaction verified successfully")
            return jsonify({'message': 'Transaction verified'}), 200
        logger.warning("Transaction verification failed")
        return jsonify({'message': 'Transaction verification failed'}), 400

    @app.route('/image/process', methods=['POST'])
    def process_image():
        try:
            if 'image' not in request.files:
                return jsonify({'error': 'No image file provided'}), 400
                
            image_file = request.files['image']
            image_data = image_file.read()
            
            # Uruchom cały pipeline
            result = blockchain.process_image(image_data)
            
            if result["success"]:
                return jsonify({
                    'success': True,
                    'message': 'Image successfully stored in blockchain',
                    'details': result
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': result["error"]
                }), 400
                
        except Exception as e:
            logger.exception("Image processing failed")
            return jsonify({'error': str(e)}), 500
    
    @app.route('/mine', methods=['GET'])
    def mine():
        logger.info("Starting mining process")
        # Sprawdź czy są jakieś transakcje oczekujące
        if not blockchain.pending_transactions:
            return jsonify({
                'success': False,
                'message': 'No pending transactions to mine',
                'status': 'idle'
            }), 200  # Zmiana kodu odpowiedzi na 200, bo to nie jest błąd
        
        # Sprawdź czy mining już trwa
        if blockchain.mining_status["is_mining"]:
            return jsonify({
                'success': False,
                'message': 'Mining already in progress',
                'progress': blockchain.mining_status["progress"],
                'status': 'mining'
            }), 409

        result = blockchain.mine_pending_transactions()

        logger.info(result["success"])
        
        if result["success"]:
            logger.info("Starting consensus resolution after mining")
            was_chain_replaced = blockchain.resolve_conflicts()

            # Powiadom inne węzły tylko jeśli mining się powiódł
            for node in blockchain.nodes:
                try:
                    logger.info(f"Notifying node {node} about the new chain - resolve")
                    requests.get(f'{node}/blockchain/nodes/resolve', timeout=5)
                    logger.info(f"Notified node {node} about the new chain")
                except requests.exceptions.RequestException as e:
                    logger.error(f"Error notifying node {node}: {e}")

            result.update({
                "chain_status": "replaced" if was_chain_replaced else "authoritative",
                "status": "completed"
            })
            return jsonify(result), 200
        else:
            # Jeśli mining się nie powiódł, ale to nie był błąd (np. brak wystarczających potwierdzeń)
            if "No transactions with sufficient confirmations" in result.get("message", ""):
                return jsonify({
                    'success': False,
                    'message': result["message"],
                    'status': 'waiting_for_confirmations'
                }), 200
            
            # Rzeczywisty błąd
            logger.error("Mining failed")
            return jsonify({
                'success': False,
                'message': result["message"],
                'status': 'error'
            }), 400

    @app.route('/chain', methods=['GET'])
    def get_chain():
        logger.info("Fetching the blockchain")
        response = {
            'chain': [
                {
                    'index': block.index,
                    'previous_hash': block.previous_hash,
                    'timestamp': block.timestamp,
                    'transactions': [t.to_dict() for t in block.transactions],
                    'hash': block.hash,
                    'confirmations': len(block.transactions[0].confirmations)
                }
                for block in blockchain.chain
            ],
            'length': len(blockchain.chain)
        }
        return jsonify(response), 200

    @app.route('/nodes/resolve', methods=['GET'])
    def consensus():
        logger.info("Starting consensus resolution")
        replaced = blockchain.resolve_conflicts()
        chain_data = [{
            'index': block.index,
            'previous_hash': block.previous_hash,
            'transactions': [t.to_dict() for t in block.transactions],
            'timestamp': block.timestamp,
            'hash': block.hash
        } for block in blockchain.chain]

        if replaced:
            logger.info("Chain was replaced with a longer valid chain")
        else:
            logger.info("Current chain is authoritative")

        return jsonify({
            'message': 'Chain was replaced' if replaced else 'Chain is authoritative',
            'chain': chain_data,
            'length': len(blockchain.chain)
        }), 200
    
    @app.route('/verify_hashes', methods=['POST'])
    def verify_hashes():
        """Endpoint to trigger hash verification"""
        try:
            blockchain.verify_and_correct_hashes()
            return jsonify({
                'message': 'Hash verification completed',
                'status': 'success'
            }), 200
        except Exception as e:
            logger.error(f"Error during hash verification: {e}")
            return jsonify({
                'message': f'Hash verification failed: {str(e)}',
                'status': 'error'
            }), 500

    return app