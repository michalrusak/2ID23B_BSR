import os
import socket
import threading
import json
import time
import random
import base64
import hashlib
import requests
import logging
from urllib.parse import urlparse
import bencodepy  # for torrent functionality

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class P2PNetwork:
    def __init__(self, node_id, host='0.0.0.0', port=None, bootstrap_nodes=None):
        """Initialize the P2P network node"""
        self.node_id = node_id
        self.host = host
        self.port = port or int(os.getenv('PORT', 5001))
        self.peers = set()
        self.failed_peers = {}
        self.bootstrap_nodes = bootstrap_nodes or []
        self.is_running = False
        self.server_thread = None
        self.message_handlers = {}
        self.lock = threading.Lock()
        self.torrent_files = {}  # Maps infohash to torrent metadata
        self.swarm = {}  # Maps infohash to list of peers that have the file
        
        # Error counter for different error types
        self.error_stats = {
            "network_errors": 0,
            "data_corruption": 0,
            "node_failures": 0
        }
        
        # Add default message handlers
        self.register_handler("discover_peers", self.handle_discover_peers)
        self.register_handler("peer_announce", self.handle_peer_announce)
        self.register_handler("blockchain_request", self.handle_blockchain_request)
        self.register_handler("torrent_announce", self.handle_torrent_announce)
        self.register_handler("piece_request", self.handle_piece_request)
        
    def start_server(self):
        """Start the P2P server to listen for incoming connections"""
        if self.is_running:
            return
            
        self.is_running = True
        self.server_thread = threading.Thread(target=self._run_server)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        # Start peer discovery and maintenance
        threading.Thread(target=self._maintain_peers, daemon=True).start()
        
        # Start error recovery process
        threading.Thread(target=self._error_recovery, daemon=True).start()
        
        logger.info(f"P2P Network started for node {self.node_id} on {self.host}:{self.port}")
        
        # Connect to bootstrap nodes
        if self.bootstrap_nodes:
            for node in self.bootstrap_nodes:
                self.connect_to_peer(node)
        
    def _run_server(self):
        """Run the server socket to accept incoming connections"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(10)
            
            logger.info(f"P2P server listening on {self.host}:{self.port}")
            
            while self.is_running:
                try:
                    client_sock, addr = server_socket.accept()
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_sock, addr)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")
                    self.error_stats["network_errors"] += 1
        except Exception as e:
            logger.error(f"Error starting server: {e}")
            self.error_stats["network_errors"] += 1
        finally:
            if 'server_socket' in locals():
                server_socket.close()
    
    def _handle_client(self, client_socket, address):
        """Handle incoming client connection"""
        try:
            data = b''
            while self.is_running:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                
                try:
                    # Try to decode the message
                    message = json.loads(data.decode('utf-8'))
                    
                    # Process the message
                    if 'type' in message and message['type'] in self.message_handlers:
                        response = self.message_handlers[message['type']](message)
                        if response:
                            client_socket.send(json.dumps(response).encode('utf-8'))
                    else:
                        logger.warning(f"Unknown message type: {message.get('type')}")
                        
                    # Reset data buffer after processing
                    data = b''
                except json.JSONDecodeError:
                    # Incomplete message, continue receiving
                    continue
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    self.error_stats["data_corruption"] += 1
                    data = b''
        except Exception as e:
            logger.error(f"Error handling client {address}: {e}")
            self.error_stats["network_errors"] += 1
        finally:
            client_socket.close()
    
    def connect_to_peer(self, peer_address):
        """Connect to a peer and add it to the peers list"""
        if peer_address in self.peers:
            return True
            
        try:
            # Parse the peer address
            parsed_url = urlparse(peer_address)
            host = parsed_url.hostname
            port = parsed_url.port
            
            # Connect to the peer
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((host, port))
            
            # Send peer announcement
            peer_info = {
                "type": "peer_announce",
                "node_id": self.node_id,
                "address": f"http://{self.host}:{self.port}"
            }
            sock.send(json.dumps(peer_info).encode('utf-8'))
            
            # Add to peers
            with self.lock:
                self.peers.add(peer_address)
                if peer_address in self.failed_peers:
                    del self.failed_peers[peer_address]
            
            sock.close()
            logger.info(f"Connected to peer {peer_address}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to peer {peer_address}: {e}")
            with self.lock:
                if peer_address not in self.failed_peers:
                    self.failed_peers[peer_address] = time.time()
            self.error_stats["network_errors"] += 1
            return False
    
    def discover_peers(self):
        """Discover peers from known peers"""
        if not self.peers:
            # If no peers, try bootstrap nodes
            for node in self.bootstrap_nodes:
                self.connect_to_peer(node)
            return
        
        # Ask existing peers for their peers
        peers_to_ask = list(self.peers)
        random.shuffle(peers_to_ask)
        
        for peer in peers_to_ask[:min(5, len(peers_to_ask))]:
            try:
                # Use REST API for peer discovery
                response = requests.get(
                    f"{peer}/blockchain/p2p/peers",
                    timeout=5
                )
                
                if response.status_code == 200:
                    peer_list = response.json().get("peers", [])
                    for new_peer in peer_list:
                        if new_peer != f"http://{self.host}:{self.port}" and new_peer not in self.peers:
                            self.connect_to_peer(new_peer)
            except Exception as e:
                logger.error(f"Error discovering peers from {peer}: {e}")
                with self.lock:
                    if peer not in self.failed_peers:
                        self.failed_peers[peer] = time.time()
                self.error_stats["network_errors"] += 1
    
    def _maintain_peers(self):
        """Periodically check peer health and discover new peers"""
        while self.is_running:
            try:
                # Check health of existing peers
                peers_to_check = list(self.peers)
                for peer in peers_to_check:
                    try:
                        response = requests.get(
                            f"{peer}/blockchain/health",
                            timeout=3
                        )
                        if response.status_code != 200:
                            logger.warning(f"Peer {peer} is unhealthy: {response.status_code}")
                            with self.lock:
                                self.peers.remove(peer)
                                self.failed_peers[peer] = time.time()
                            self.error_stats["node_failures"] += 1
                    except Exception:
                        logger.warning(f"Peer {peer} is unreachable")
                        with self.lock:
                            self.peers.remove(peer)
                            self.failed_peers[peer] = time.time()
                        self.error_stats["node_failures"] += 1
                
                # Try to recover failed peers periodically
                failed_peers = list(self.failed_peers.keys())
                for peer in failed_peers:
                    if time.time() - self.failed_peers[peer] > 60:  # Try after 1 minute
                        if self.connect_to_peer(peer):
                            logger.info(f"Recovered peer {peer}")
                
                # Discover new peers
                self.discover_peers()
                
                # Wait before next maintenance
                time.sleep(30)
            except Exception as e:
                logger.error(f"Error in peer maintenance: {e}")
                time.sleep(10)
    
    def _error_recovery(self):
        """Periodically attempt to recover from errors"""
        while self.is_running:
            try:
                # If too many network errors, try to restart networking
                if self.error_stats["network_errors"] > 10:
                    logger.warning("Too many network errors, attempting recovery")
                    # Reset error counter
                    self.error_stats["network_errors"] = 0
                    
                    # Try to reconnect to all peers
                    for peer in list(self.peers):
                        self.connect_to_peer(peer)
                
                # If too many data corruption errors, try to re-sync blockchain
                if self.error_stats["data_corruption"] > 5:
                    logger.warning("Too many data corruption errors, initiating blockchain resync")
                    self.error_stats["data_corruption"] = 0
                    # Notify blockchain node to resync (will be handled by blockchain_node.py)
                    
                # If too many node failures, try to find new peers
                if self.error_stats["node_failures"] > len(self.peers) / 2:
                    logger.warning("Too many node failures, searching for new peers")
                    self.error_stats["node_failures"] = 0
                    self.discover_peers()
                
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in error recovery: {e}")
                time.sleep(30)
    
    def register_handler(self, message_type, handler_function):
        """Register a handler for a specific message type"""
        self.message_handlers[message_type] = handler_function
    
    def broadcast_message(self, message):
        """Broadcast a message to all peers"""
        message_json = json.dumps(message)
        message_bytes = message_json.encode('utf-8')
        
        failed_peers = []
        for peer in self.peers:
            try:
                # Parse peer address
                parsed_url = urlparse(peer)
                host = parsed_url.hostname
                port = parsed_url.port
                
                # Create socket and send message
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((host, port))
                sock.send(message_bytes)
                sock.close()
            except Exception as e:
                logger.error(f"Failed to send message to {peer}: {e}")
                failed_peers.append(peer)
                self.error_stats["network_errors"] += 1
        
        # Remove failed peers
        with self.lock:
            for peer in failed_peers:
                self.peers.remove(peer)
                self.failed_peers[peer] = time.time()
    
    def create_torrent_metadata(self, data, piece_length=1024*1024):
        """Create torrent-like metadata for a blockchain data file"""
        # Calculate pieces hashes
        pieces = []
        current_pos = 0
        data_bytes = data if isinstance(data, bytes) else data.encode('utf-8')
        
        while current_pos < len(data_bytes):
            piece = data_bytes[current_pos:current_pos + piece_length]
            piece_hash = hashlib.sha1(piece).digest()
            pieces.append(piece_hash)
            current_pos += piece_length
        
        # Create metadata
        info = {
            'piece length': piece_length,
            'pieces': b''.join(pieces),
            'name': f'blockchain_{self.node_id}_{int(time.time())}.dat',
            'length': len(data_bytes)
        }
        
        # Calculate infohash
        info_bencoded = bencodepy.encode(info)
        infohash = hashlib.sha1(info_bencoded).hexdigest()
        
        # Create full metadata
        metadata = {
            'info': info,
            'announce': f"http://{self.host}:{self.port}/blockchain/p2p/announce",
            'created by': f"blockchain_node_{self.node_id}",
            'creation date': int(time.time())
        }
        
        # Store metadata
        self.torrent_files[infohash] = {
            'metadata': metadata,
            'data': data_bytes,
            'peers': set([f"http://{self.host}:{self.port}"])
        }
        
        # Announce to peers
        self.announce_torrent(infohash)
        
        return {
            'infohash': infohash,
            'metadata': metadata
        }
    
    def announce_torrent(self, infohash):
        """Announce a torrent to all peers"""
        if infohash not in self.torrent_files:
            return False
            
        announce_message = {
            'type': 'torrent_announce',
            'node_id': self.node_id,
            'infohash': infohash,
            'metadata': self.torrent_files[infohash]['metadata']
        }
        
        self.broadcast_message(announce_message)
        return True
    
    def get_torrent_piece(self, infohash, piece_index, piece_length):
        """Get a specific piece of a torrent file"""
        if infohash not in self.torrent_files:
            return None
            
        torrent_data = self.torrent_files[infohash]['data']
        start_pos = piece_index * piece_length
        end_pos = min(start_pos + piece_length, len(torrent_data))
        
        if start_pos >= len(torrent_data):
            return None
            
        return torrent_data[start_pos:end_pos]
    
    def download_blockchain_torrent(self, infohash):
        """Download a blockchain file using torrent-like protocol"""
        # First check if we already have this torrent
        if infohash in self.torrent_files:
            return self.torrent_files[infohash]['data']
        
        # If not, find peers that have it
        if infohash not in self.swarm or not self.swarm[infohash]:
            logger.error(f"No peers found for infohash {infohash}")
            return None
        
        # Get metadata from a peer
        peer = random.choice(list(self.swarm[infohash]))
        try:
            response = requests.get(
                f"{peer}/blockchain/p2p/torrent/{infohash}",
                timeout=10
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to get metadata: {response.status_code}")
                return None
                
            metadata = response.json()['metadata']
            piece_length = metadata['info']['piece length']
            total_length = metadata['info']['length']
            pieces = metadata['info']['pieces']
            
            # Download pieces
            data = bytearray(total_length)
            piece_count = (total_length + piece_length - 1) // piece_length
            
            for i in range(piece_count):
                # Select a random peer that has this file
                download_peer = random.choice(list(self.swarm[infohash]))
                
                try:
                    piece_response = requests.get(
                        f"{download_peer}/blockchain/p2p/piece/{infohash}/{i}",
                        timeout=10
                    )
                    
                    if piece_response.status_code != 200:
                        logger.error(f"Failed to download piece {i}: {piece_response.status_code}")
                        continue
                        
                    piece_data = base64.b64decode(piece_response.json()['data'])
                    
                    # Verify piece hash
                    piece_hash = hashlib.sha1(piece_data).digest()
                    expected_hash = pieces[i*20:(i+1)*20]
                    
                    if piece_hash != expected_hash:
                        logger.error(f"Piece {i} hash mismatch")
                        self.error_stats["data_corruption"] += 1
                        continue
                    
                    # Write piece to data buffer
                    start_pos = i * piece_length
                    end_pos = min(start_pos + len(piece_data), total_length)
                    data[start_pos:end_pos] = piece_data
                    
                except Exception as e:
                    logger.error(f"Error downloading piece {i}: {e}")
                    self.error_stats["network_errors"] += 1
                    continue
            
            # Verify complete file hash
            if hashlib.sha1(data).hexdigest() != infohash:
                logger.error("Complete file hash mismatch")
                self.error_stats["data_corruption"] += 1
                return None
                
            # Store the downloaded torrent
            self.torrent_files[infohash] = {
                'metadata': metadata,
                'data': bytes(data),
                'peers': set([f"http://{self.host}:{self.port}"])
            }
            
            # Announce that we have the file
            self.announce_torrent(infohash)
            
            return bytes(data)
            
        except Exception as e:
            logger.error(f"Error downloading torrent: {e}")
            self.error_stats["network_errors"] += 1
            return None
    
    def create_magnet_link(self, infohash):
        """Create a magnet link for a torrent file"""
        if infohash not in self.torrent_files:
            return None
            
        torrent = self.torrent_files[infohash]
        name = torrent['metadata']['info']['name']
        
        # Create magnet link with trackers (peers)
        trackers = "&".join([f"tr={peer}" for peer in torrent['peers']])
        magnet = f"magnet:?xt=urn:btih:{infohash}&dn={name}&{trackers}"
        
        return magnet
    
    # Message handlers
    def handle_discover_peers(self, message):
        """Handle a peer discovery request"""
        return {
            "type": "peer_list",
            "peers": list(self.peers)
        }
    
    def handle_peer_announce(self, message):
        """Handle a peer announcement"""
        peer_id = message.get("node_id")
        peer_address = message.get("address")
        
        if peer_address and peer_id:
            with self.lock:
                self.peers.add(peer_address)
                if peer_address in self.failed_peers:
                    del self.failed_peers[peer_address]
            
            return {
                "type": "peer_acknowledge",
                "node_id": self.node_id,
                "address": f"http://{self.host}:{self.port}"
            }
        return None
    
    def handle_blockchain_request(self, message):
        """Handle a request for blockchain data"""
        # This will be implemented in blockchain_node.py
        return None
    
    def handle_torrent_announce(self, message):
        """Handle a torrent announcement"""
        infohash = message.get("infohash")
        metadata = message.get("metadata")
        node_id = message.get("node_id")
        
        if infohash and metadata and node_id:
            # Add to swarm
            if infohash not in self.swarm:
                self.swarm[infohash] = set()
            self.swarm[infohash].add(f"http://{node_id}:{self.port}")
            
            return {
                "type": "torrent_acknowledge",
                "node_id": self.node_id,
                "infohash": infohash
            }
        return None
    
    def handle_piece_request(self, message):
        """Handle a request for a torrent piece"""
        infohash = message.get("infohash")
        piece_index = message.get("piece_index")
        
        if infohash in self.torrent_files and piece_index is not None:
            metadata = self.torrent_files[infohash]['metadata']
            piece_length = metadata['info']['piece length']
            
            piece_data = self.get_torrent_piece(infohash, piece_index, piece_length)
            
            if piece_data:
                return {
                    "type": "piece_data",
                    "infohash": infohash,
                    "piece_index": piece_index,
                    "data": base64.b64encode(piece_data).decode('utf-8')
                }
        return None
