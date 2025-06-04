import os
import sys
import logging
import glob
import re
import shutil
from torrentool.torrent import Torrent

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_torrent_naming(data_dir):
    """Fix inconsistent naming between torrent files and data files"""
    logger.info(f"Fixing torrent naming in directory: {data_dir}")
    
    # Get all files in the directory
    all_files = os.listdir(data_dir)
    logger.info(f"Found {len(all_files)} files in directory")
    
    # Find all torrent files
    torrent_files = [f for f in all_files if f.endswith('.torrent')]
    logger.info(f"Found {len(torrent_files)} torrent files")
    
    # Find all data files
    data_files = [f for f in all_files if f.endswith('.json')]
    logger.info(f"Found {len(data_files)} data files")
    
    # Extract blockchain index pattern (e.g., "blockchain_1", "blockchain_2", etc.)
    blockchain_pattern = re.compile(r'blockchain_(\d+)')
    
    # Group files by index
    torrent_by_index = {}
    data_by_index = {}
    
    # Map torrent files by index
    for torrent_file in torrent_files:
        match = blockchain_pattern.search(torrent_file)
        if match:
            index = int(match.group(1))
            torrent_by_index[index] = torrent_file
    
    # Map data files by index
    for data_file in data_files:
        match = blockchain_pattern.search(data_file)
        if match:
            index = int(match.group(1))
            data_by_index[index] = data_file
    
    logger.info(f"Mapped torrent files by index: {torrent_by_index}")
    logger.info(f"Mapped data files by index: {data_by_index}")
    
    # Find orphaned files (torrent without matching data file or vice versa)
    orphaned_torrents = [idx for idx in torrent_by_index.keys() if idx not in data_by_index]
    orphaned_data = [idx for idx in data_by_index.keys() if idx not in torrent_by_index]
    
    logger.info(f"Found {len(orphaned_torrents)} orphaned torrent files")
    logger.info(f"Found {len(orphaned_data)} orphaned data files")
    
    # Fix orphaned torrents by renumbering them to match existing data files
    for idx in orphaned_torrents:
        torrent_file = torrent_by_index[idx]
        torrent_path = os.path.join(data_dir, torrent_file)
        
        # Try to load the torrent to see what data file it's looking for
        try:
            torrent = Torrent.from_file(torrent_path)
            data_name = torrent.name
            logger.info(f"Torrent {torrent_file} is looking for data file: {data_name}")
            
            # Check if this data file exists
            data_path = os.path.join(data_dir, data_name)
            if os.path.exists(data_path):
                logger.info(f"Found matching data file: {data_name}")
                
                # Extract index from data name if it matches the pattern
                data_match = blockchain_pattern.search(data_name)
                if data_match:
                    new_index = int(data_match.group(1))
                    new_torrent_name = f"blockchain_{new_index}.torrent"
                    new_torrent_path = os.path.join(data_dir, new_torrent_name)
                    
                    # Rename the torrent file to match the data file index
                    if new_torrent_name != torrent_file:
                        logger.info(f"Renaming torrent file: {torrent_file} -> {new_torrent_name}")
                        if os.path.exists(new_torrent_path):
                            logger.warning(f"Destination file already exists, creating backup")
                            backup_path = f"{new_torrent_path}.bak"
                            shutil.copy2(new_torrent_path, backup_path)
                        
                        shutil.copy2(torrent_path, new_torrent_path)
                        logger.info(f"Successfully renamed torrent file")
            else:
                # Data file doesn't exist
                logger.warning(f"No data file found for torrent: {torrent_file}")
                
                # Check if we have orphaned data files we can use
                if orphaned_data:
                    # Use the first orphaned data file
                    data_idx = orphaned_data.pop(0)
                    data_file = data_by_index[data_idx]
                    data_path = os.path.join(data_dir, data_file)
                    
                    logger.info(f"Creating new torrent for data file: {data_file}")
                    
                    # Create a new torrent file from the data file
                    try:
                        # Get host IP for tracker
                        host_ip = os.getenv('HOST_IP', '127.0.0.1')
                        tracker_url = f"http://{host_ip}:6969/announce"
                        
                        new_torrent = Torrent.create_from(data_path)
                        new_torrent.announce_urls = [tracker_url]
                        new_torrent.comment = f"Fixed torrent for {data_file}"
                        new_torrent.created_by = "Torrent Fix Tool"
                        
                        # Save with matching name
                        new_torrent_name = f"blockchain_{data_idx}.torrent"
                        new_torrent_path = os.path.join(data_dir, new_torrent_name)
                        new_torrent.to_file(new_torrent_path)
                        
                        logger.info(f"Created new torrent: {new_torrent_name}")
                    except Exception as e:
                        logger.error(f"Failed to create new torrent: {e}")
        except Exception as e:
            logger.error(f"Error processing torrent {torrent_file}: {e}")
    
    # Fix orphaned data files by creating new torrents for them
    for idx in orphaned_data:
        data_file = data_by_index[idx]
        data_path = os.path.join(data_dir, data_file)
        
        logger.info(f"Creating torrent for orphaned data file: {data_file}")
        
        try:
            # Get host IP for tracker
            host_ip = os.getenv('HOST_IP', '127.0.0.1')
            tracker_url = f"http://{host_ip}:6969/announce"
            
            new_torrent = Torrent.create_from(data_path)
            new_torrent.announce_urls = [tracker_url]
            new_torrent.comment = f"Torrent for {data_file}"
            new_torrent.created_by = "Torrent Fix Tool"
            
            # Save with matching name
            new_torrent_name = f"blockchain_{idx}.torrent"
            new_torrent_path = os.path.join(data_dir, new_torrent_name)
            new_torrent.to_file(new_torrent_path)
            
            logger.info(f"Created new torrent: {new_torrent_name}")
        except Exception as e:
            logger.error(f"Failed to create torrent for data file: {e}")
    
    logger.info("Naming fix completed!")

if __name__ == "__main__":
    # Use blockchain_data directory in current working directory by default
    data_dir = os.path.join(os.getcwd(), "blockchain_data")
    
    # Allow command-line override
    if len(sys.argv) > 1:
        data_dir = sys.argv[1]
    
    # Ensure directory exists
    if not os.path.exists(data_dir):
        logger.error(f"Directory does not exist: {data_dir}")
        sys.exit(1)
    
    logger.info(f"Starting torrent naming fix for directory: {data_dir}")
    fix_torrent_naming(data_dir)
