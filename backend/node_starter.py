import os
import sys
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python node_starter.py <node_id> <port>")
        sys.exit(1)
    
    node_id = sys.argv[1]
    port = int(sys.argv[2])
    
    # Set environment variables
    os.environ['NODE_ID'] = node_id
    os.environ['PORT'] = str(port)
    os.environ['HOST_IP'] = '127.0.0.1'
    
    print(f"===== STARTING NODE {node_id} ON PORT {port} =====")
    print(f"Press Ctrl+C to stop this node")
    
    # Import and run the node
    try:
        from app import create_app, start_node
        
        # Start the node
        app = create_app()
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error starting node: {e}")
        print(f"Error: {e}")
        input("Press Enter to close this window...")
