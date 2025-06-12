import os
import sys
import time
import logging
import threading
import argparse
import subprocess
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Check and fix bencode dependencies
def check_and_fix_dependencies():
    try:
        # Try to import bencode and see if it works
        import bencode
        logger.info("Bencode library check passed")
    except ImportError as e:
        logger.error(f"Bencode import error: {e}")
        logger.info("Installing correct version of bencode.py...")
        
        # Uninstall conflicting packages
        subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "bencode"])
        subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "bencode.py"])
        subprocess.call([sys.executable, "-m", "pip", "uninstall", "-y", "bencodepy"])
        
        # Install the correct version
        subprocess.call([sys.executable, "-m", "pip", "install", "bencode.py==4.0.0"])
        logger.info("Dependency fixed, please restart the application")
        sys.exit(1)

# Create a simple bencode implementation for our needs if libraries fail
class SimpleBencode:
    @staticmethod
    def encode(data):
        """Simple bencode encoder for basic types"""
        if isinstance(data, int):
            return f"i{data}e".encode()
        elif isinstance(data, str):
            return f"{len(data)}:{data}".encode()
        elif isinstance(data, bytes):
            return f"{len(data)}:".encode() + data
        elif isinstance(data, list):
            result = b"l"
            for item in data:
                result += SimpleBencode.encode(item)
            return result + b"e"
        elif isinstance(data, dict):
            result = b"d"
            for key in sorted(data.keys()):
                if isinstance(key, str):
                    k = key.encode()
                else:
                    k = key
                result += SimpleBencode.encode(k)
                result += SimpleBencode.encode(data[key])
            return result + b"e"
        else:
            raise ValueError(f"Cannot encode {type(data)} objects")

    @staticmethod
    def decode(data):
        """Simple bencode decoder for basic types"""
        # This is a very simplified implementation
        # In a real-world scenario, you'd want a more robust decoder
        if data.startswith(b"i"):
            end = data.index(b"e")
            return int(data[1:end]), data[end+1:]
        elif data.startswith(b"l"):
            result = []
            data = data[1:]
            while data[0:1] != b"e":
                item, data = SimpleBencode.decode(data)
                result.append(item)
            return result, data[1:]
        elif data.startswith(b"d"):
            result = {}
            data = data[1:]
            while data[0:1] != b"e":
                key, data = SimpleBencode.decode(data)
                value, data = SimpleBencode.decode(data)
                result[key] = value
            return result, data[1:]
        else:
            # String or bytes
            colon_pos = data.index(b":")
            length = int(data[:colon_pos])
            start_pos = colon_pos + 1
            end_pos = start_pos + length
            return data[start_pos:end_pos], data[end_pos:]

def run_flask_app(app, host='0.0.0.0', port=5000, name=None):
    """Run a Flask app in a separate process"""
    logger.info(f"Starting {name} on port {port}...")
    app.run(host=host, port=port, threaded=True)

def run_node(node_id, port):
    """Run a blockchain node in a new console window"""
    try:
        # Create command to run the node in a separate process
        cmd = [sys.executable, 'node_starter.py', node_id, str(port)]
        
        # On Windows, use CREATE_NEW_CONSOLE to open a new window
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                cmd, 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux/Mac
            # For Unix systems, we could use xterm, gnome-terminal, etc.
            # This is a simple example using xterm
            process = subprocess.Popen(
                ['xterm', '-e', f'{sys.executable} node_starter.py {node_id} {port}']
            )
            
        logger.info(f"Started node {node_id} in a new console (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"Error starting node {node_id}: {e}")
        return None

def run_tracker():
    """Run the tracker server in a new console window"""
    try:
        # Create command to run the tracker in a separate process
        cmd = [sys.executable, 'tracker_starter.py', str(os.getenv('TRACKER_PORT', 6969))]
        
        # On Windows, use CREATE_NEW_CONSOLE to open a new window
        if os.name == 'nt':  # Windows
            process = subprocess.Popen(
                cmd, 
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
        else:  # Linux/Mac
            # For Unix systems
            process = subprocess.Popen(
                ['xterm', '-e', f'{sys.executable} tracker_starter.py {os.getenv("TRACKER_PORT", 6969)}']
            )
            
        logger.info(f"Started tracker in a new console (PID: {process.pid})")
        return process
    except Exception as e:
        logger.error(f"Error starting tracker: {e}")
        return None

def ensure_data_directory():
    """Ensure the blockchain_data directory exists"""
    data_dir = os.path.join(os.getcwd(), "blockchain_data")
    os.makedirs(data_dir, exist_ok=True)
    logger.info(f"Blockchain data directory: {data_dir}")
    return data_dir

def install_missing_packages():
    """Install any missing packages"""
    required_packages = [
        "flask==2.0.1",
        "python-dotenv==0.19.0",
        "pyjwt==2.1.0",
        "werkzeug==2.0.1",
        "requests==2.26.0",
        "pillow==9.5.0",
        "flask-cors",
        "torrentool==1.1.1",
        "bencode.py==4.0.0"
    ]
    
    for package in required_packages:
        try:
            package_name = package.split("==")[0]
            importlib.import_module(package_name.replace("-", "_"))
            logger.info(f"Package {package_name} is already installed")
        except ImportError:
            logger.info(f"Installing missing package: {package}")
            subprocess.call([sys.executable, "-m", "pip", "install", package])

def main():
    parser = argparse.ArgumentParser(description="Run the blockchain network locally")
    parser.add_argument('--nodes', type=int, default=6, help='Number of nodes to run (default: 6)')
    parser.add_argument('--base-port', type=int, default=5001, help='Base port for nodes (default: 5001)')
    parser.add_argument('--tracker-port', type=int, default=6969, help='Port for tracker (default: 6969)')
    parser.add_argument('--fix-deps', action="store_true", help='Fix dependencies and exit')
    
    args = parser.parse_args()
    
    # Install any missing packages
    install_missing_packages()
    
    # Check and fix bencode dependency issues
    check_and_fix_dependencies()
    
    # If we're just fixing dependencies, exit
    if args.fix_deps:
        logger.info("Dependencies checked and fixed. Exiting.")
        return
    
    # Set tracker port environment variable
    os.environ['TRACKER_PORT'] = str(args.tracker_port)
    os.environ['HOST_IP'] = '127.0.0.1'  # Ensure this is set for local testing
    
    # Create blockchain_data directory if it doesn't exist
    data_dir = ensure_data_directory()
    
    # Patch the bencode module if needed
    try:
        import bencode
    except ImportError:
        logger.warning("Using simple bencode implementation as fallback")
        sys.modules['bencode'] = SimpleBencode
        
    # Start tracker
    tracker_process = run_tracker()
    if not tracker_process:
        logger.error("Failed to start tracker. Exiting.")
        return
    
    logger.info("Waiting for tracker to start...")
    time.sleep(2)  # Give the tracker time to start
    
    # Start nodes
    node_processes = []
    for i in range(1, args.nodes + 1):
        node_id = f"node{i}"
        port = args.base_port + i - 1
        node_process = run_node(node_id, port)
        if node_process:
            node_processes.append(node_process)
            logger.info(f"Node {node_id} started on port {port}")
        else:
            logger.error(f"Failed to start node {node_id}")
        
        # Small delay to avoid race conditions
        time.sleep(1)
    
    if not node_processes:
        logger.error("No nodes could be started. Exiting.")
        return
        
    logger.info(f"All {len(node_processes)} nodes started in separate consoles")
    logger.info(f"Tracker running on port {args.tracker_port}")
    logger.info("Press Ctrl+C to stop all servers")
    
    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Shutting down servers...")
        
        # Terminate all processes
        for process in node_processes:
            try:
                process.terminate()
            except:
                pass
                
        try:
            tracker_process.terminate()
        except:
            pass
            
        logger.info("All servers shut down")

if __name__ == "__main__":
    main()
