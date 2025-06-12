import os
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python tracker_starter.py <port>")
        sys.exit(1)
    
    port = int(sys.argv[1])
    
    # Set environment variables
    os.environ['TRACKER_PORT'] = str(port)
    os.environ['TRACKER_HOST'] = '0.0.0.0'
    os.environ['HOST_IP'] = '127.0.0.1'
    
    print(f"===== STARTING TRACKER ON PORT {port} =====")
    print(f"Press Ctrl+C to stop the tracker")
    
    # Import and run the tracker
    try:
        from tracker_server import create_tracker_app
        
        app = create_tracker_app()
        app.run(host='0.0.0.0', port=port)
    except Exception as e:
        logger.error(f"Error starting tracker: {e}")
        print(f"Error: {e}")
        input("Press Enter to close this window...")
