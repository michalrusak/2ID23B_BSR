import os
import logging
import datetime

class SimpleLogger:
    """A simple file-based logger to replace database logging"""
    
    def __init__(self, log_file="blockchain.log"):
        """Initialize the logger with a log file path"""
        self.log_file = log_file
        
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Simple logger initialized, writing to {log_file}")
    
    def log_transaction(self, tx_type, tx_data, node_id="unknown"):
        """Log a transaction to the log file"""
        self.logger.info(f"Transaction - Type: {tx_type}, Node: {node_id}, Data: {tx_data[:100]}...")
    
    def log_block_mined(self, block_index, block_hash, tx_count, node_id="unknown"):
        """Log when a block is mined"""
        self.logger.info(f"Block Mined - Index: {block_index}, Hash: {block_hash}, Transactions: {tx_count}, Node: {node_id}")
    
    def log_error(self, error_msg, node_id="unknown"):
        """Log an error"""
        self.logger.error(f"Error - Node: {node_id}, Message: {error_msg}")
    
    def log_recovery(self, recovery_type, details, node_id="unknown"):
        """Log a recovery action"""
        self.logger.info(f"Recovery - Type: {recovery_type}, Node: {node_id}, Details: {details}")

# Create a singleton instance
simple_logger = SimpleLogger()

def get_logger():
    """Get the singleton logger instance"""
    return simple_logger
