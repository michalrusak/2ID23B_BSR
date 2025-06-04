import os
import sys
import time
import logging
import tempfile
import json
import base64
from flask import Flask, request, jsonify, send_file
from torrentool.torrent import Torrent
from torrent_utils import BlockchainTorrent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BitTorrentServer:
    """BitTorrent server for seeding blockchain data"""
    
    def __init__(self, data_dir=None):
        """Initialize BitTorrent server"""
        self.data_dir = data_dir or os.path.join(tempfile.gettempdir(), "blockchain_torrents")
        self.active_torrents = {}
        self.torrent_manager = BlockchainTorrent(node_id="torrent_server")
        
        # Create data directory if it doesn't exist
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"BitTorrent server initialized with data directory: {self.data_dir}")
    
    def create_torrent_from_blockchain(self, blockchain_data, comment="Blockchain Data", custom_trackers=None):
        """Create a torrent file from blockchain data"""
        try:
            # Define trackers - use custom ones if provided or use defaults
            trackers = custom_trackers or [
               ' http://localhost:6969/announce',
                'http://127.0.0.1:6969/announce',
                'http:// 192.168.117.1:6969/announce',
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
            
            # Save blockchain data to a file
            timestamp = int(time.time())
            data_file_path = os.path.join(self.data_dir, f"blockchain_data_{timestamp}.json")
            
            # Process blockchain data to ensure proper handling of image data
            processed_data = blockchain_data.copy()
            
            # Ensure image data is properly handled
            if 'chain' in processed_data:
                for block in processed_data['chain']:
                    if 'transactions' in block:
                        for tx in block['transactions']:
                            if tx.get('type') == 'image' and isinstance(tx.get('data'), str):
                                try:
                                    # Store the actual image data instead of base64
                                    image_data = base64.b64decode(tx['data'])
                                    tx['data'] = image_data.decode('latin1')  # Use latin1 to preserve binary data
                                    logger.info(f"Processed image data in transaction with CRC: {tx.get('crc')}")
                                except Exception as e:
                                    logger.error(f"Error processing image data: {e}")
            
            with open(data_file_path, 'w') as f:
                json.dump(processed_data, f, indent=2)
            
            # Create torrent file using torrentool
            torrent_file_path = os.path.join(self.data_dir, f"blockchain_{timestamp}.torrent")
            torrent = Torrent.create_from(data_file_path)
            torrent.announce_urls = trackers
            torrent.comment = comment
            torrent.created_by = "Blockchain Torrent Server"
            
            # Save the torrent file
            torrent.to_file(torrent_file_path)
            
            # Get info hash
            info_hash = torrent.info_hash
            
            # Store the active torrent info
            self.active_torrents[info_hash] = {
                'data_file': data_file_path,
                'torrent_file': torrent_file_path,
                'info_hash': info_hash,
                'created_at': timestamp,
                'comment': comment,
                'trackers': trackers
            }
            
            logger.info(f"Created torrent file: {torrent_file_path} with info hash: {info_hash}")
            
            return {
                'torrent_file': torrent_file_path,
                'data_file': data_file_path,
                'info_hash': info_hash
            }
        
        except Exception as e:
            logger.error(f"Error creating torrent from blockchain: {e}")
            return None
    
    def get_torrent_file(self, info_hash):
        """Get torrent file by info hash"""
        if info_hash in self.active_torrents:
            return self.active_torrents[info_hash]['torrent_file']
        return None
    
    def get_data_file(self, info_hash):
        """Get data file by info hash"""
        if info_hash in self.active_torrents:
            return self.active_torrents[info_hash]['data_file']
        return None
    
    def list_active_torrents(self):
        """List all active torrents"""
        return {
            info_hash: {
                'info_hash': info_hash,
                'created_at': torrent['created_at'],
                'comment': torrent['comment'],
                'torrent_file': os.path.basename(torrent['torrent_file']),
                'data_file': os.path.basename(torrent['data_file']),
                'trackers': torrent['trackers']
            }
            for info_hash, torrent in self.active_torrents.items()
        }
    
    def cleanup(self):
        """Clean up temporary files"""
        for info_hash, torrent in self.active_torrents.items():
            try:
                os.remove(torrent['torrent_file'])
                os.remove(torrent['data_file'])
            except Exception as e:
                logger.error(f"Error cleaning up torrent files: {e}")
        
        self.active_torrents = {}
        logger.info("Cleaned up all torrent files")

def create_torrent_server_app():
    """Create Flask app for BitTorrent server"""
    app = Flask(__name__)
    
    # Get data directory from environment or use default
    data_dir = os.getenv('TORRENT_DATA_DIR', None)
    
    torrent_server = BitTorrentServer(data_dir=data_dir)
    
    @app.route('/create-torrent', methods=['POST'])
    def create_torrent():
        """Create torrent from blockchain data"""
        data = request.get_json()
        
        if not data or 'blockchain_data' not in data:
            return jsonify({'success': False, 'message': 'Missing blockchain data'}), 400
        
        comment = data.get('comment', 'Blockchain Data')
        custom_trackers = data.get('trackers', None)
        
        result = torrent_server.create_torrent_from_blockchain(
            data['blockchain_data'],
            comment=comment,
            custom_trackers=custom_trackers
        )
        
        if result:
            return jsonify({
                'success': True,
                'info_hash': result['info_hash'],
                'torrent_file': os.path.basename(result['torrent_file']),
                'data_file': os.path.basename(result['data_file']),
                'message': 'Torrent created successfully. You can now add this to uTorrent.'
            }), 200
        
        return jsonify({'success': False, 'message': 'Failed to create torrent'}), 500
    
    @app.route('/torrents', methods=['GET'])
    def list_torrents():
        """List all active torrents"""
        return jsonify({
            'success': True,
            'torrents': torrent_server.list_active_torrents()
        }), 200
    
    @app.route('/torrent/<info_hash>', methods=['GET'])
    def get_torrent(info_hash):
        """Get torrent file by info hash"""
        torrent_file = torrent_server.get_torrent_file(info_hash)
        
        if torrent_file and os.path.exists(torrent_file):
            return send_file(
                torrent_file,
                as_attachment=True,
                download_name=f"blockchain_{info_hash}.torrent",
                mimetype='application/x-bittorrent'
            )
        
        return jsonify({'success': False, 'message': 'Torrent not found'}), 404
    
    @app.route('/data/<info_hash>', methods=['GET'])
    def get_data(info_hash):
        """Get data file by info hash"""
        data_file = torrent_server.get_data_file(info_hash)
        
        if data_file and os.path.exists(data_file):
            return send_file(
                data_file,
                as_attachment=True,
                download_name=f"blockchain_data_{info_hash}.json",
                mimetype='application/json'
            )
        
        return jsonify({'success': False, 'message': 'Data file not found'}), 404
    
    @app.route('/cleanup', methods=['POST'])
    def cleanup():
        """Clean up temporary files"""
        torrent_server.cleanup()
        return jsonify({'success': True, 'message': 'Cleaned up all torrent files'}), 200
    
    @app.route('/health', methods=['GET'])
    def health_check():
        """Health check endpoint"""
        return jsonify({'status': 'healthy'}), 200
    
    return app

if __name__ == '__main__':
    # Default port for the torrent server
    port = int(os.getenv('TORRENT_SERVER_PORT', 8080))
    
    app = create_torrent_server_app()
    
    # Print startup instructions
    print("=" * 80)
    print("BitTorrent Server for Blockchain")
    print("=" * 80)
    print(f"Server running on port {port}")
    print("\nHow to use with uTorrent:")
    print("1. Create a torrent via POST to /create-torrent")
    print("2. Download the torrent file via GET /torrent/<info_hash>")
    print("3. Open the torrent file in uTorrent")
    print("4. Make sure the data file is accessible at the location shown in /torrents")
    print("5. Start seeding in uTorrent")
    print("\nAvailable endpoints:")
    print("- POST /create-torrent: Create a new torrent from blockchain data")
    print("- GET  /torrents: List all active torrents")
    print("- GET  /torrent/<info_hash>: Download a specific torrent file")
    print("- GET  /data/<info_hash>: Download the data file for a torrent")
    print("- POST /cleanup: Remove all torrent files")
    print("=" * 80)
    
    app.run(host='0.0.0.0', port=port)
