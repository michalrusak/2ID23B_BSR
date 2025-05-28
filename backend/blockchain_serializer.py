import pickle
import zlib
import base64
import hashlib
import json
import logging

logger = logging.getLogger(__name__)

class BlockchainSerializer:
    """
    Handles serialization and deserialization of blockchain data
    """
    
    @staticmethod
    def serialize_to_binary(blockchain):
        """Serialize blockchain to binary format"""
        try:
            # First convert to dict representation
            chain_data = []
            for block in blockchain.chain:
                block_dict = {
                    'index': block.index,
                    'previous_hash': block.previous_hash,
                    'timestamp': block.timestamp,
                    'transactions': [t.to_dict() for t in block.transactions],
                    'hash': block.hash,
                    'nonce': block.nonce
                }
                chain_data.append(block_dict)
                
            # Add additional metadata
            blockchain_data = {
                'chain': chain_data,
                'node_id': blockchain.node_id,
                'difficulty': blockchain.difficulty,
                'timestamp': blockchain.chain[-1].timestamp,
                'length': len(blockchain.chain),
                'version': '1.0'
            }
            
            # Serialize with pickle and compress
            serialized = pickle.dumps(blockchain_data)
            compressed = zlib.compress(serialized)
            
            # Calculate and store checksums
            checksums = {
                'sha256': hashlib.sha256(compressed).hexdigest(),
                'crc32': format(zlib.crc32(compressed) & 0xFFFFFFFF, '08x')
            }
            
            # Add checksums to header
            header = json.dumps(checksums).encode('utf-8')
            header_len = len(header).to_bytes(4, byteorder='big')
            
            # Combine header and data
            result = header_len + header + compressed
            
            logger.info(f"Serialized blockchain - Original: {len(serialized)} bytes, Compressed: {len(compressed)} bytes, Total: {len(result)} bytes")
            return result
            
        except Exception as e:
            logger.error(f"Error serializing blockchain: {e}")
            raise
    
    @staticmethod
    def deserialize_from_binary(binary_data):
        """Deserialize blockchain from binary format"""
        try:
            # Extract header length
            header_len = int.from_bytes(binary_data[:4], byteorder='big')
            
            # Extract header
            header = binary_data[4:4+header_len]
            checksums = json.loads(header.decode('utf-8'))
            
            # Extract compressed data
            compressed = binary_data[4+header_len:]
            
            # Verify checksums
            calculated_sha256 = hashlib.sha256(compressed).hexdigest()
            calculated_crc32 = format(zlib.crc32(compressed) & 0xFFFFFFFF, '08x')
            
            if calculated_sha256 != checksums['sha256']:
                logger.error(f"SHA256 checksum mismatch - Expected: {checksums['sha256']}, Got: {calculated_sha256}")
                raise ValueError("SHA256 checksum verification failed")
                
            if calculated_crc32 != checksums['crc32']:
                logger.error(f"CRC32 checksum mismatch - Expected: {checksums['crc32']}, Got: {calculated_crc32}")
                raise ValueError("CRC32 checksum verification failed")
            
            # Decompress and deserialize
            decompressed = zlib.decompress(compressed)
            blockchain_data = pickle.loads(decompressed)
            
            logger.info(f"Deserialized blockchain - Length: {blockchain_data['length']}, Version: {blockchain_data['version']}")
            return blockchain_data
            
        except json.JSONDecodeError:
            logger.error("Invalid header format")
            raise ValueError("Invalid header format in binary data")
        except zlib.error:
            logger.error("Decompression failed - data may be corrupted")
            raise ValueError("Decompression failed - data may be corrupted")
        except pickle.UnpicklingError:
            logger.error("Deserialization failed - incompatible data format")
            raise ValueError("Deserialization failed - incompatible data format")
        except Exception as e:
            logger.error(f"Error deserializing blockchain: {e}")
            raise
    
    @staticmethod
    def create_blockchain_magnet(binary_data, node_id):
        """Create a magnet link for the blockchain data"""
        try:
            # Generate infohash (SHA1 hash of the data)
            infohash = hashlib.sha1(binary_data).hexdigest()
            
            # Create basic magnet link
            magnet = f"magnet:?xt=urn:btih:{infohash}&dn=blockchain_{node_id}"
            
            # Add additional metadata
            header_len = int.from_bytes(binary_data[:4], byteorder='big')
            header = binary_data[4:4+header_len]
            checksums = json.loads(header.decode('utf-8'))
            
            # Add checksums
            magnet += f"&xs=sha256:{checksums['sha256']}"
            
            # Add blockchain specific info
            blockchain_data = BlockchainSerializer.deserialize_from_binary(binary_data)
            magnet += f"&length={blockchain_data['length']}"
            magnet += f"&difficulty={blockchain_data['difficulty']}"
            
            return {
                'magnet': magnet,
                'infohash': infohash,
                'checksums': checksums,
                'size': len(binary_data),
                'blockchain_length': blockchain_data['length']
            }
            
        except Exception as e:
            logger.error(f"Error creating magnet link: {e}")
            raise
