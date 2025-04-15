import logging
import json
import time
from typing import Dict, Any

logger = logging.getLogger(__name__)

def register_handlers(p2p_node, blockchain):
    """Register all message handlers with the P2P node"""
    # Basic network handlers
    p2p_node.register_handler("introduction", lambda msg, sock: handle_introduction(p2p_node, msg, sock))
    p2p_node.register_handler("heartbeat", lambda msg, sock: handle_heartbeat(p2p_node, msg, sock))
    p2p_node.register_handler("get_peers", lambda msg, sock: handle_get_peers(p2p_node, msg, sock))
    p2p_node.register_handler("peers_list", lambda msg, sock: handle_peers_list(p2p_node, msg, sock))
    
    # Blockchain specific handlers
    p2p_node.register_handler("new_transaction", lambda msg, sock: handle_new_transaction(p2p_node, blockchain, msg, sock))
    p2p_node.register_handler("new_block", lambda msg, sock: handle_new_block(p2p_node, blockchain, msg, sock))
    p2p_node.register_handler("get_chain", lambda msg, sock: handle_get_chain(p2p_node, blockchain, msg, sock))
    p2p_node.register_handler("chain_response", lambda msg, sock: handle_chain_response(p2p_node, blockchain, msg, sock))
    p2p_node.register_handler("verify_transaction", lambda msg, sock: handle_verify_transaction(p2p_node, blockchain, msg, sock))
    
def handle_introduction(p2p_node, message, sock):
    """Handle introduction messages from peers"""
    peer_id = message.get('node_id')
    host = message.get('host')
    port = message.get('port')
    
    if peer_id and host and port:
        p2p_node.register_peer(peer_id, host, port)
        
        # Send back our own information
        if sock:
            response = {
                "type": "introduction",
                "node_id": p2p_node.node_id,
                "host": p2p_node.host,
                "port": p2p_node.port
            }
            p2p_node.send_message(response, sock)
            
            # Also send our peer list
            peers_response = {
                "type": "peers_list",
                "peers": [
                    {"node_id": pid, "host": pinfo["host"], "port": pinfo["port"]}
                    for pid, pinfo in p2p_node.peers.items()
                ]
            }
            p2p_node.send_message(peers_response, sock)
    else:
        logger.warning("Received incomplete introduction message")

def handle_heartbeat(p2p_node, message, sock):
    """Handle heartbeat messages from peers"""
    peer_id = message.get('node_id')
    timestamp = message.get('timestamp')
    
    if peer_id in p2p_node.peers:
        p2p_node.peers[peer_id]['last_seen'] = time.time()
        
        # Respond to heartbeat with our own
        if sock:
            response = {
                "type": "heartbeat",
                "node_id": p2p_node.node_id,
                "timestamp": time.time()
            }
            p2p_node.send_message(response, sock)
    else:
        # Unknown peer, ask for introduction
        if sock:
            response = {
                "type": "get_introduction",
                "node_id": p2p_node.node_id
            }
            p2p_node.send_message(response, sock)

def handle_get_peers(p2p_node, message, sock):
    """Handle requests for peer lists"""
    if not sock:
        return
        
    peer_id = message.get('node_id')
    if peer_id:
        # Update last seen time
        if peer_id in p2p_node.peers:
            p2p_node.peers[peer_id]['last_seen'] = time.time()
            
        # Send back our peer list
        response = {
            "type": "peers_list",
            "peers": [
                {"node_id": pid, "host": pinfo["host"], "port": pinfo["port"]}
                for pid, pinfo in p2p_node.peers.items()
            ]
        }
        p2p_node.send_message(response, sock)

def handle_peers_list(p2p_node, message, sock):
    """Handle received peer lists"""
    peers = message.get('peers', [])
    
    for peer in peers:
        peer_id = peer.get('node_id')
        host = peer.get('host')
        port = peer.get('port')
        
        if peer_id and host and port and peer_id != p2p_node.node_id:
            if peer_id not in p2p_node.peers and peer_id not in p2p_node.discovered_peers:
                p2p_node.discovered_peers.add(peer_id)
                
                # Try to connect to this new peer
                threading.Thread(
                    target=p2p_node.connect_to_peer,
                    args=(host, port),
                    daemon=True
                ).start()

def handle_new_transaction(p2p_node, blockchain, message, sock):
    """Handle new transaction broadcast from peers"""
    transaction_data = message.get('transaction')
    if not transaction_data:
        logger.warning("Received new_transaction message without transaction data")
        return
        
    try:
        # Create transaction from data
        transaction = blockchain.Transaction.from_dict(transaction_data)
        
        # Verify the transaction
        if transaction.verify_crc():
            # Add sender to confirmations
            sender_id = message.get('node_id')
            if sender_id:
                transaction.confirmations.add(f"http://{sender_id}:5001")
                
            # Add our own confirmation
            transaction.confirmations.add(f"http://{p2p_node.node_id}:5001")
            
            # Add to pending pool if not already there
            blockchain.add_transaction(transaction)
            
            # Send confirmation back
            if sock:
                response = {
                    "type": "transaction_verified",
                    "node_id": p2p_node.node_id,
                    "transaction_crc": transaction.crc,
                    "result": True
                }
                p2p_node.send_message(response, sock)
            
            # Forward to other peers (if we're not the originator)
            if message.get('originator') != p2p_node.node_id:
                # Mark ourselves as having seen this message
                forward_message = {
                    "type": "new_transaction",
                    "transaction": transaction_data,
                    "node_id": p2p_node.node_id,
                    "originator": message.get('originator', message.get('node_id')),
                    "timestamp": time.time()
                }
                
                # Forward to a subset of peers to avoid flooding
                with p2p_node.lock:
                    peers_copy = list(p2p_node.peers.items())
                    
                # Forward to at most 3 random peers
                import random
                if len(peers_copy) > 3:
                    peers_copy = random.sample(peers_copy, 3)
                    
                for peer_id, peer_info in peers_copy:
                    if peer_id != message.get('node_id'):  # Don't send back to sender
                        try:
                            p2p_node.send_message(forward_message, peer_id=peer_id)
                        except Exception as e:
                            logger.error(f"Failed to forward transaction to {peer_id}: {e}")
                
        else:
            # Transaction failed verification
            logger.warning(f"Received invalid transaction with CRC: {transaction.crc}")
            if sock:
                response = {
                    "type": "transaction_verified",
                    "node_id": p2p_node.node_id,
                    "transaction_crc": transaction.crc,
                    "result": False
                }
                p2p_node.send_message(response, sock)
                
    except Exception as e:
        logger.error(f"Error handling new transaction: {e}")
        if sock:
            response = {
                "type": "transaction_verified",
                "node_id": p2p_node.node_id,
                "result": False,
                "error": str(e)
            }
            p2p_node.send_message(response, sock)

def handle_new_block(p2p_node, blockchain, message, sock):
    """Handle new block broadcast from peers"""
    block_data = message.get('block')
    if not block_data:
        logger.warning("Received new_block message without block data")
        return
        
    try:
        # Reconstruct transactions
        transactions = []
        for tx_data in block_data['transactions']:
            transaction = blockchain.Transaction.from_dict(tx_data)
            transactions.append(transaction)
            
        # Create block
        block = blockchain.Block(
            block_data['index'],
            block_data['previous_hash'],
            transactions,
            block_data['timestamp']
        )
        block.nonce = block_data['nonce']
        block.hash = block_data['hash']
        
        # Verify block
        if blockchain.verify_block(block):
            # Add to blockchain
            with blockchain.lock:
                # Check if we already have this block
                if len(blockchain.chain) > block.index and blockchain.chain[block.index].hash == block.hash:
                    logger.info(f"Block {block.index} already exists in the chain")
                elif len(blockchain.chain) == block.index:
                    # This is the next block we need
                    blockchain.chain.append(block)
                    logger.info(f"Added new block {block.index} to the chain")
                    
                    # Remove transactions that are now in the blockchain
                    blockchain.pending_transactions = [
                        tx for tx in blockchain.pending_transactions
                        if not any(tx.crc == chain_tx.crc for chain_tx in block.transactions)
                    ]
                    
                    # Send confirmation
                    if sock:
                        response = {
                            "type": "block_verified",
                            "node_id": p2p_node.node_id,
                            "block_index": block.index,
                            "block_hash": block.hash,
                            "result": True
                        }
                        p2p_node.send_message(response, sock)
                    
                    # Forward the block to other peers
                    if message.get('originator') != p2p_node.node_id:
                        forward_message = {
                            "type": "new_block",
                            "block": block_data,
                            "node_id": p2p_node.node_id,
                            "originator": message.get('originator', message.get('node_id')),
                            "timestamp": time.time()
                        }
                        p2p_node.broadcast_message(forward_message)
                else:
                    # We might be behind in the chain
                    logger.warning(f"Received block {block.index} but current chain length is {len(blockchain.chain)}")
                    
                    # Request full chain from sender
                    if sock:
                        response = {
                            "type": "get_chain",
                            "node_id": p2p_node.node_id
                        }
                        p2p_node.send_message(response, sock)
        else:
            # Block failed verification
            logger.warning(f"Received invalid block with hash: {block.hash}")
            if sock:
                response = {
                    "type": "block_verified",
                    "node_id": p2p_node.node_id,
                    "block_index": block.index,
                    "block_hash": block.hash,
                    "result": False
                }
                p2p_node.send_message(response, sock)
                
    except Exception as e:
        logger.error(f"Error handling new block: {e}")
        if sock:
            response = {
                "type": "block_verified",
                "node_id": p2p_node.node_id,
                "result": False,
                "error": str(e)
            }
            p2p_node.send_message(response, sock)

def handle_get_chain(p2p_node, blockchain, message, sock):
    """Handle requests for the blockchain"""
    if not sock:
        return
        
    try:
        # Prepare chain data
        chain_data = []
        with blockchain.lock:
            for block in blockchain.chain:
                block_data = {
                    'index': block.index,
                    'previous_hash': block.previous_hash,
                    'timestamp': block.timestamp,
                    'transactions': [t.to_dict() for t in block.transactions],
                    'hash': block.hash,
                    'nonce': block.nonce
                }
                chain_data.append(block_data)
                
        response = {
            "type": "chain_response",
            "node_id": p2p_node.node_id,
            "chain": chain_data,
            "pending_transactions": [t.to_dict() for t in blockchain.pending_transactions]
        }
        
        p2p_node.send_message(response, sock)
        
    except Exception as e:
        logger.error(f"Error handling get_chain request: {e}")

def handle_chain_response(p2p_node, blockchain, message, sock):
    """Handle blockchain data received from peers"""
    chain_data = message.get('chain')
    pending_transactions = message.get('pending_transactions', [])
    
    if not chain_data:
        logger.warning("Received chain_response without chain data")
        return
        
    try:
        # Reconstruct the chain
        new_chain = []
        for block_data in chain_data:
            transactions = []
            for tx_data in block_data['transactions']:
                transaction = blockchain.Transaction.from_dict(tx_data)
                transactions.append(transaction)
                
            block = blockchain.Block(
                block_data['index'],
                block_data['previous_hash'],
                transactions,
                block_data['timestamp']
            )
            block.nonce = block_data['nonce']
            block.hash = block_data['hash']
            new_chain.append(block)
            
        # Verify the chain
        if blockchain.is_chain_valid(new_chain):
            # Check if the chain is longer than ours
            with blockchain.lock:
                if len(new_chain) > len(blockchain.chain):
                    blockchain.chain = new_chain
                    logger.info(f"Updated chain from peer, new length: {len(new_chain)}")
                    
                    # Update pending transactions - add ones we don't have
                    existing_txs = {tx.crc for tx in blockchain.pending_transactions}
                    for tx_data in pending_transactions:
                        if tx_data['crc'] not in existing_txs:
                            try:
                                tx = blockchain.Transaction.from_dict(tx_data)
                                if tx.verify_crc():
                                    blockchain.pending_transactions.append(tx)
                            except Exception as e:
                                logger.error(f"Error adding pending transaction: {e}")
        else:
            logger.warning("Received invalid chain from peer")
            
    except Exception as e:
        logger.error(f"Error handling chain response: {e}")

def handle_verify_transaction(p2p_node, blockchain, message, sock):
    """Handle transaction verification requests"""
    transaction_data = message.get('transaction')
    if not transaction_data or not sock:
        return
        
    try:
        transaction = blockchain.Transaction.from_dict(transaction_data)
        verification_result = transaction.verify_crc()
        
        response = {
            "type": "transaction_verified",
            "node_id": p2p_node.node_id,
            "transaction_crc": transaction.crc,
            "result": verification_result
        }
        
        p2p_node.send_message(response, sock)
        
        if verification_result:
            # Add sender to confirmations
            sender_id = message.get('node_id')
            if sender_id:
                transaction.confirmations.add(f"http://{sender_id}:5001")
                
            # Add our own confirmation
            transaction.confirmations.add(f"http://{p2p_node.node_id}:5001")
            
            # Add to pending pool if not already there
            blockchain.add_transaction(transaction)
            
    except Exception as e:
        logger.error(f"Error verifying transaction: {e}")
        response = {
            "type": "transaction_verified",
            "node_id": p2p_node.node_id,
            "result": False,
            "error": str(e)
        }
        p2p_node.send_message(response, sock)