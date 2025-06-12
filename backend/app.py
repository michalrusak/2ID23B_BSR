import os
import sys
import logging
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from flask_cors import CORS
from blockchain_node import create_blockchain_app
import signal
import threading

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_app():
    """Creates the main application with blockchain sub-app."""
    logger.info("Creating main application...")

    try:
        app = Flask(__name__)
        CORS(app, resources={
            r"/blockchain/*": {"origins": ["http://localhost:4200"]}
        })

        # Create blockchain sub-app
        logger.info("Creating blockchain application...")
        blockchain_app = create_blockchain_app()

        # Add CORS to the sub-app
        CORS(blockchain_app, resources={r"/*": {"origins": ["http://localhost:4200"]}})

        # Connect sub-app to main app
        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
            '/blockchain': blockchain_app
        })

        logger.info("Main application created successfully.")
        return app
    except Exception as e:
        logger.error(f"Error creating application: {e}")
        sys.exit(1)

def start_tracker():
    """Start the tracker server in a separate thread"""
    from tracker_server import create_tracker_app
    tracker_app = create_tracker_app()
    port = int(os.getenv('TRACKER_PORT', 6969))
    logger.info(f"Starting tracker on port {port}...")
    tracker_app.run(host='0.0.0.0', port=port, threaded=True)

def start_node(port):
    """Start a single blockchain node."""
    app = create_app()
    logger.info(f"Starting node on port {port}...")
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))

    # Start tracker in a separate thread
    tracker_thread = threading.Thread(target=start_tracker, daemon=True)
    tracker_thread.start()
    logger.info("Tracker thread started")

    # Start the main app
    logger.info("Starting main application...")
    start_node(port)