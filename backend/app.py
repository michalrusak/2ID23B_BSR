import os
import sys
import logging
from flask import Flask
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from flask_cors import CORS
from blockchain_node import create_blockchain_app
from user_management import create_user_app
from dotenv import load_dotenv
import signal
import multiprocessing

# Wczytaj zmienne środowiskowe
load_dotenv()

# Konfiguracja loggera
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def create_app():
    """Tworzy główną aplikację z pod-aplikacjami blockchain i user management."""
    logger.info("Tworzenie głównej aplikacji...")

    try:
        app = Flask(__name__)
        CORS(app, resources={
            r"/blockchain/*": {"origins": ["http://localhost:4200"]},
            r"/user/*": {"origins": ["http://localhost:4200"]}
        })

        # Tworzenie pod-aplikacji
        logger.info("Tworzenie aplikacji blockchain...")
        blockchain_app = create_blockchain_app()

        logger.info("Tworzenie aplikacji user management...")
        user_app = create_user_app()

        # Dodawanie CORS do pod-aplikacji
        CORS(blockchain_app, resources={r"/*": {"origins": ["http://localhost:4200"]}})
        CORS(user_app, resources={r"/*": {"origins": ["http://localhost:4200"]}})

        # Łączenie pod-aplikacji z główną aplikacją
        app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {
            '/blockchain': blockchain_app,
            '/user': user_app
        })

        logger.info("Główna aplikacja została utworzona pomyślnie.")
        return app
    except Exception as e:
        logger.error(f"Błąd podczas tworzenia aplikacji: {e}")
        sys.exit(1)

def start_node(port):
    """Uruchamia pojedynczy węzeł blockchain."""
    app = create_app()
    logger.info(f"Uruchamianie węzła na porcie {port}...")
    app.run(host='0.0.0.0', port=port)

def start_network(num_nodes=6, start_port=5001):
    logger.info(f"Uruchamianie sieci z {num_nodes} węzłami...")
    processes = []
    node_addresses = generate_node_addresses(start_port, num_nodes)
    logger.info(f"Adresy węzłów: {node_addresses}")
    
    for i in range(num_nodes):
        port = start_port + i
        process = multiprocessing.Process(target=start_node, args=(port))
        process.start()
        processes.append(process)

    def signal_handler(sig, frame):
        logger.info("Zamykanie sieci...")
        for process in processes:
            process.terminate()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    for process in processes:
        process.join()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5001))

    # Uruchamianie pojedynczego węzła
    logger.info("Uruchamianie aplikacji...")
    start_node(port)

def generate_node_addresses(start_port, num_nodes):
    return [f"http://node{i}:{5000 + i}" for i in range(1, num_nodes + 1)]