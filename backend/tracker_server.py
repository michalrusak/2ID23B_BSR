import os
import time
import logging
import urllib.parse
import binascii
from flask import Flask, request, Response, jsonify
from werkzeug.middleware.proxy_fix import ProxyFix
import random
import socket

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class Tracker:
    """Custom BitTorrent tracker to coordinate peer connections"""
    
    def __init__(self, announce_interval=1800):
        """Initialize the tracker"""
        self.torrents = {}  # info_hash -> {peers}
        self.announce_interval = announce_interval  # How often peers should announce in seconds
        self.clean_interval = 2400  # How often to clean inactive peers in seconds
        self.last_clean = time.time()
        self.stats = {
            "announces": 0,
            "scrapes": 0,
            "completed": 0,
            "started": 0,
            "stopped": 0
        }
        logger.info("Tracker initialized")
    
    def add_peer(self, info_hash, peer_id, ip, port, event=None, uploaded=0, downloaded=0, left=0):
        """Add or update a peer for a torrent"""
        try:
            # Convert info_hash to hex string for consistent dict keys
            hex_info_hash = binascii.hexlify(info_hash).decode('utf-8')
            
            # Create torrent entry if it doesn't exist
            if hex_info_hash not in self.torrents:
                self.torrents[hex_info_hash] = {
                    "peers": {},
                    "complete": 0,    # Seeders
                    "incomplete": 0,  # Leechers
                    "downloaded": 0,  # Completed downloads
                    "created": time.time()
                }
            
            # Check if peer is a seeder (left=0 means they have the complete file)
            is_seeder = (left == 0)
            was_seeder = False
            
            # Update statistics based on event
            if event == "started":
                self.stats["started"] += 1
            elif event == "completed":
                self.stats["completed"] += 1
                self.torrents[hex_info_hash]["downloaded"] += 1
            elif event == "stopped":
                self.stats["stopped"] += 1
                
                # If peer exists and is stopping, remove them
                peer_key = f"{ip}:{port}"
                if peer_key in self.torrents[hex_info_hash]["peers"]:
                    was_seeder = self.torrents[hex_info_hash]["peers"][peer_key]["left"] == 0
                    # Remove the peer
                    del self.torrents[hex_info_hash]["peers"][peer_key]
                    
                    # Update seeder/leecher counts
                    if was_seeder:
                        self.torrents[hex_info_hash]["complete"] = max(0, self.torrents[hex_info_hash]["complete"] - 1)
                    else:
                        self.torrents[hex_info_hash]["incomplete"] = max(0, self.torrents[hex_info_hash]["incomplete"] - 1)
                    
                    # Skip further processing if peer is stopping
                    return
            
            # Add or update peer
            peer_key = f"{ip}:{port}"
            
            # Check if peer already exists
            peer_exists = peer_key in self.torrents[hex_info_hash]["peers"]
            
            if peer_exists:
                was_seeder = self.torrents[hex_info_hash]["peers"][peer_key]["left"] == 0
            
            # Add/update the peer entry
            self.torrents[hex_info_hash]["peers"][peer_key] = {
                "peer_id": peer_id,
                "ip": ip,
                "port": port,
                "uploaded": uploaded,
                "downloaded": downloaded,
                "left": left,
                "last_announce": time.time()
            }
            
            # Update seeder/leecher counts
            if peer_exists:
                if was_seeder and not is_seeder:
                    # Changed from seeder to leecher
                    self.torrents[hex_info_hash]["complete"] -= 1
                    self.torrents[hex_info_hash]["incomplete"] += 1
                elif not was_seeder and is_seeder:
                    # Changed from leecher to seeder
                    self.torrents[hex_info_hash]["incomplete"] -= 1
                    self.torrents[hex_info_hash]["complete"] += 1
            else:
                # New peer
                if is_seeder:
                    self.torrents[hex_info_hash]["complete"] += 1
                else:
                    self.torrents[hex_info_hash]["incomplete"] += 1
        except Exception as e:
            logger.error(f"Error adding peer: {e}")
            raise
    
    def get_peers(self, info_hash, numwant=50, no_peer_id=False, compact=False):
        """Get a list of peers for a torrent"""
        # Convert info_hash to hex string
        hex_info_hash = binascii.hexlify(info_hash).decode('utf-8')
        
        # Check if torrent exists
        if hex_info_hash not in self.torrents:
            return []
        
        # Select random peers up to numwant
        peers_dict = self.torrents[hex_info_hash]["peers"]
        peer_keys = list(peers_dict.keys())
        random.shuffle(peer_keys)
        
        if numwant > 0 and numwant < len(peer_keys):
            peer_keys = peer_keys[:numwant]
        
        peers = []
        
        # Format peers according to the request
        if compact:
            # Compact format: 6 bytes per peer (4 for IP, 2 for port)
            peers_binary = b""
            for key in peer_keys:
                peer = peers_dict[key]
                # Convert IP string to 4 bytes
                ip_parts = peer["ip"].split(".")
                if len(ip_parts) == 4:
                    try:
                        ip_bytes = bytes([int(p) for p in ip_parts])
                        # Convert port to 2 bytes in network byte order (big-endian)
                        port_bytes = peer["port"].to_bytes(2, byteorder='big')
                        peers_binary += ip_bytes + port_bytes
                    except Exception as e:
                        logger.error(f"Error encoding peer {peer['ip']}:{peer['port']}: {e}")
            
            peers = peers_binary
        else:
            # Dictionary format
            for key in peer_keys:
                peer = peers_dict[key]
                peer_data = {
                    "ip": peer["ip"],
                    "port": peer["port"]
                }
                
                if not no_peer_id:
                    peer_data["peer id"] = peer["peer_id"]
                
                peers.append(peer_data)
        
        return peers
    
    def get_torrent_stats(self, info_hash):
        """Get statistics for a torrent"""
        # Convert info_hash to hex string
        hex_info_hash = binascii.hexlify(info_hash).decode('utf-8')
        
        # Check if torrent exists
        if hex_info_hash not in self.torrents:
            return {
                "complete": 0,
                "incomplete": 0,
                "downloaded": 0
            }
        
        # Return stats
        torrent = self.torrents[hex_info_hash]
        return {
            "complete": torrent["complete"],
            "incomplete": torrent["incomplete"],
            "downloaded": torrent["downloaded"]
        }
    
    def clean_inactive_peers(self):
        """Remove peers that haven't announced in a while"""
        if time.time() - self.last_clean < self.clean_interval:
            return
        
        logger.info("Cleaning inactive peers")
        self.last_clean = time.time()
        inactive_threshold = time.time() - (self.announce_interval * 2)
        
        for info_hash, torrent in list(self.torrents.items()):
            inactive_peers = []
            
            for peer_key, peer in list(torrent["peers"].items()):
                if peer["last_announce"] < inactive_threshold:
                    inactive_peers.append(peer_key)
            
            # Remove inactive peers
            for peer_key in inactive_peers:
                peer = torrent["peers"][peer_key]
                if peer["left"] == 0:
                    torrent["complete"] -= 1
                else:
                    torrent["incomplete"] -= 1
                
                del torrent["peers"][peer_key]
            
            # Remove torrent if no peers left and it's been around for a while
            if len(torrent["peers"]) == 0 and (time.time() - torrent["created"]) > 86400:  # 24 hours
                del self.torrents[info_hash]
                logger.info(f"Removed torrent {info_hash} with no peers")
        
        logger.info(f"Cleaned inactive peers")
    
    def get_stats(self):
        """Get tracker statistics"""
        active_torrents = len(self.torrents)
        total_peers = sum(len(t["peers"]) for t in self.torrents.values())
        total_seeders = sum(t["complete"] for t in self.torrents.values())
        total_leechers = sum(t["incomplete"] for t in self.torrents.values())
        
        return {
            "torrents": active_torrents,
            "peers": total_peers,
            "seeders": total_seeders,
            "leechers": total_leechers,
            "announces": self.stats["announces"],
            "scrapes": self.stats["scrapes"],
            "completed": self.stats["completed"],
            "uptime": int(time.time() - self.stats.get("start_time", time.time()))
        }

def create_tracker_app():
    """Create Flask app for the tracker"""
    app = Flask(__name__)
    app.wsgi_app = ProxyFix(app.wsgi_app)
    
    tracker = Tracker()
    tracker.stats["start_time"] = time.time()
    
    @app.route('/announce', methods=['GET'])
    def announce():
        """Handle BitTorrent announce requests"""
        tracker.stats["announces"] += 1
        tracker.clean_inactive_peers()
        
        try:
            # Get required parameters with better error handling
            try:
                # Get info_hash - this is binary data
                info_hash_raw = request.args.get('info_hash', '')
                if not info_hash_raw:
                    raise ValueError("Missing info_hash parameter")
                
                # Handle URL-encoded binary data properly
                if isinstance(info_hash_raw, str):
                    info_hash = info_hash_raw.encode('latin1', errors='replace')
                else:
                    info_hash = info_hash_raw
                
                # Similarly handle peer_id
                peer_id_raw = request.args.get('peer_id', '')
                if isinstance(peer_id_raw, str):
                    peer_id = peer_id_raw.encode('latin1', errors='replace')
                else:
                    peer_id = peer_id_raw
                
                # Log the raw and processed info_hash to help debug
                logger.info(f"Raw info_hash type: {type(info_hash_raw)}, length: {len(info_hash_raw)}")
                logger.info(f"Processed info_hash: {binascii.hexlify(info_hash).decode('utf-8')}")
                
                # Get numeric parameters
                try:
                    port = int(request.args.get('port', 0))
                    uploaded = int(request.args.get('uploaded', 0))
                    downloaded = int(request.args.get('downloaded', 0))
                    left = int(request.args.get('left', 0))
                    compact = int(request.args.get('compact', 0))
                    no_peer_id = int(request.args.get('no_peer_id', 0))
                    numwant = int(request.args.get('numwant', 50))
                except ValueError as e:
                    logger.error(f"Invalid numeric parameter: {e}")
                    raise ValueError(f"Invalid numeric parameter: {e}")
                
                event = request.args.get('event', None)
                
            except Exception as e:
                logger.error(f"Error parsing announce parameters: {e}")
                raise ValueError(f"Error parsing parameters: {e}")
            
            # Get client IP
            if 'X-Forwarded-For' in request.headers:
                ip = request.headers['X-Forwarded-For'].split(',')[0].strip()
            else:
                ip = request.remote_addr
                
            # Add/update the peer
            tracker.add_peer(info_hash, peer_id, ip, port, event, uploaded, downloaded, left)
            
            # Get peers to return
            peers = tracker.get_peers(info_hash, numwant, no_peer_id, compact)
            
            # Get stats for this torrent
            stats = tracker.get_torrent_stats(info_hash)
            
            # Create response
            response = {
                'interval': tracker.announce_interval,
                'complete': stats['complete'],
                'incomplete': stats['incomplete'],
                'peers': peers
            }
            
            # Return bencode-encoded response
            import bencode
            logger.info(f"Announce successful from {ip}:{port} for {binascii.hexlify(info_hash).decode('utf-8')}")
            return Response(bencode.encode(response), mimetype='text/plain')
            
        except Exception as e:
            logger.error(f"Error handling announce: {str(e)}")
            logger.exception("Detailed error information:")
            # Return error
            import bencode
            error_response = {'failure reason': str(e)}
            return Response(bencode.encode(error_response), mimetype='text/plain')
    
    @app.route('/scrape', methods=['GET'])
    def scrape():
        """Handle BitTorrent scrape requests"""
        tracker.stats["scrapes"] += 1
        
        try:
            # Get info_hash parameter(s) with better error handling
            info_hash_list = []
            
            # Process each info_hash parameter
            for info_hash_raw in request.args.getlist('info_hash'):
                try:
                    if isinstance(info_hash_raw, str):
                        info_hash = info_hash_raw.encode('latin1', errors='replace')
                    else:
                        info_hash = info_hash_raw
                    info_hash_list.append(info_hash)
                except Exception as e:
                    logger.error(f"Error processing info_hash in scrape: {e}")
                    continue
            
            if not info_hash_list:
                # If no info_hash provided, return stats for all torrents (limited to 100)
                torrents = {}
                for i, hash_hex in enumerate(list(tracker.torrents.keys())[:100]):
                    try:
                        info_hash = binascii.unhexlify(hash_hex)
                        stats = tracker.get_torrent_stats(info_hash)
                        torrents[info_hash] = {
                            'complete': stats['complete'],
                            'incomplete': stats['incomplete'],
                            'downloaded': stats['downloaded']
                        }
                    except Exception as e:
                        logger.error(f"Error processing torrent {hash_hex} in scrape: {e}")
                        continue
            else:
                # Process each info_hash
                torrents = {}
                for info_hash in info_hash_list:
                    try:
                        stats = tracker.get_torrent_stats(info_hash)
                        torrents[info_hash] = {
                            'complete': stats['complete'],
                            'incomplete': stats['incomplete'],
                            'downloaded': stats['downloaded']
                        }
                    except Exception as e:
                        logger.error(f"Error processing info_hash in scrape: {e}")
                        continue
            
            # Create response
            response = {'files': torrents}
            
            # Return bencode-encoded response
            import bencode
            return Response(bencode.encode(response), mimetype='text/plain')
            
        except Exception as e:
            logger.error(f"Error handling scrape: {e}")
            logger.exception("Detailed error information:")
            # Return error
            import bencode
            error_response = {'failure reason': str(e)}
            return Response(bencode.encode(error_response), mimetype='text/plain')
    
    @app.route('/debug', methods=['GET'])
    def debug():
        """Debug endpoint to get tracker information"""
        info = {
            'stats': tracker.get_stats(),
            'torrents': {
                hash_hex: {
                    'complete': torrent['complete'],
                    'incomplete': torrent['incomplete'],
                    'downloaded': torrent['downloaded'],
                    'peer_count': len(torrent['peers']),
                    'created': time.ctime(torrent['created'])
                }
                for hash_hex, torrent in tracker.torrents.items()
            }
        }
        return jsonify(info)
    
    @app.route('/stats', methods=['GET'])
    def stats():
        """Return tracker statistics in JSON format"""
        return jsonify(tracker.get_stats())
    
    @app.route('/health', methods=['GET'])
    def health():
        """Health check endpoint"""
        return jsonify({'status': 'healthy'})
    
    return app

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"

if __name__ == '__main__':
    # Default port for the tracker
    port = int(os.getenv('TRACKER_PORT', 6969))
    host = os.getenv('TRACKER_HOST', '0.0.0.0')
    
    local_ip = get_local_ip()
    
    app = create_tracker_app()
    
    # Print startup instructions
    print("=" * 80)
    print("Custom BitTorrent Tracker for Blockchain")
    print("=" * 80)
    print(f"Tracker running on http://{local_ip}:{port}")
    print(f"Announce URL: http://{local_ip}:{port}/announce")
    print(f"Scrape URL: http://{local_ip}:{port}/scrape")
    print("\nAdd this tracker to your torrent files with:")
    print(f"http://{local_ip}:{port}/announce")
    print("=" * 80)
    
    app.run(host=host, port=port)
