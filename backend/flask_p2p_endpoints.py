from flask import Blueprint, request, jsonify
import os
import logging
import json
import base64
import hashlib
import time

logger = logging.getLogger(__name__)

def create_p2p_blueprint(blockchain_node):
    """Create a Flask Blueprint for P2P network endpoints"""
    p2p_bp = Blueprint('p2p', __name__)
    
    @p2p_bp.route('/peers', methods=['GET'])
    def get_peers():
        """Get all peers in the P2P network"""
        # Ensure CORS headers are set
        response = jsonify({
            'peers': list(blockchain_node.p2p.peers),
            'node_id': blockchain_node.node_id,
            'count': len(blockchain_node.p2p.peers)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
    
    @p2p_bp.route('/torrents', methods=['GET'])
    def get_torrents():
        """Get all available torrents"""
        torrents = []
        
        # Just return an empty list if no torrents are available yet
        if not hasattr(blockchain_node.p2p, 'torrent_files'):
            return jsonify({
                'torrents': [],
                'count': 0
            }), 200
            
        for infohash, torrent in blockchain_node.p2p.torrent_files.items():
            try:
                torrents.append({
                    'infohash': infohash,
                    'name': torrent['metadata']['info']['name'],
                    'size': torrent['metadata']['info']['length'],
                    'peers': list(torrent['peers']),
                    'created': torrent['metadata'].get('creation date', int(time.time()))
                })
            except Exception as e:
                logger.error(f"Error processing torrent {infohash}: {e}")
        
        response = jsonify({
            'torrents': torrents,
            'count': len(torrents)
        })
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 200
    
    @p2p_bp.route('/create-torrent', methods=['POST'])
    def create_torrent():
        """Create a new torrent from file data"""
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': 'No file provided'
            }), 400
        
        # Handle file upload
        file = request.files['file']
        file_data = file.read()
        
        try:
            # Create torrent metadata
            torrent_info = blockchain_node.p2p.create_torrent_metadata(file_data)
            
            response = jsonify({
                'success': True,
                'infohash': torrent_info['infohash'],
                'message': 'Created torrent successfully'
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 201
        except Exception as e:
            logger.error(f"Error creating torrent: {e}")
            return jsonify({
                'success': False,
                'message': f'Error creating torrent: {str(e)}'
            }), 500
    
    @p2p_bp.route('/download/<infohash>', methods=['GET'])
    def download_torrent(infohash):
        """Download a torrent by infohash"""
        if hasattr(blockchain_node.p2p, 'torrent_files') and infohash in blockchain_node.p2p.torrent_files:
            return jsonify({
                'success': True,
                'message': 'File already exists locally',
                'infohash': infohash
            }), 200
            
        try:
            # Try to download the torrent
            data = blockchain_node.p2p.download_blockchain_torrent(infohash)
            
            if data:
                return jsonify({
                    'success': True,
                    'message': 'Downloaded successfully',
                    'size': len(data),
                    'infohash': infohash
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to download torrent'
                }), 404
        except Exception as e:
            logger.error(f"Error downloading torrent: {e}")
            return jsonify({
                'success': False,
                'message': f'Error downloading torrent: {str(e)}'
            }), 500
    
    return p2p_bp
