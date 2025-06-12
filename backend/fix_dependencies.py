import sys
import subprocess
import importlib
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def fix_bencode_dependency():
    """Fix the bencode dependency issue"""
    logger.info("Fixing bencode dependency...")
    
    # Uninstall potentially conflicting packages
    packages_to_uninstall = ["bencode", "bencode.py", "bencodepy"]
    for package in packages_to_uninstall:
        try:
            logger.info(f"Uninstalling {package}...")
            subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", package])
        except subprocess.CalledProcessError:
            logger.info(f"{package} not installed or couldn't be uninstalled")
    
    # Install the correct version
    logger.info("Installing bencode.py 4.0.0...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "bencode.py==4.0.0"])
    
    # Verify installation
    try:
        import bencode
        logger.info(f"Successfully installed bencode: {bencode}")
        return True
    except ImportError as e:
        logger.error(f"Failed to import bencode after installation: {e}")
        return False

def check_requirements():
    """Check if all required packages are installed"""
    requirements = [
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
    
    missing = []
    
    for req in requirements:
        package_name = req.split("==")[0]
        module_name = package_name.lower().replace("-", "_")
        
        try:
            importlib.import_module(module_name)
            logger.info(f"✅ {package_name} is installed")
        except ImportError:
            logger.warning(f"❌ {package_name} is missing")
            missing.append(req)
    
    if missing:
        logger.info("Installing missing packages...")
        for package in missing:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
                logger.info(f"Installed {package}")
            except subprocess.CalledProcessError:
                logger.error(f"Failed to install {package}")
    
    return len(missing) == 0

if __name__ == "__main__":
    logger.info("Checking and fixing dependencies...")
    
    # Check and install missing packages
    if not check_requirements():
        logger.warning("Some requirements were missing and have been installed")
    
    # Fix bencode dependency
    if fix_bencode_dependency():
        logger.info("Successfully fixed bencode dependency")
    else:
        logger.error("Failed to fix bencode dependency")
        sys.exit(1)
    
    logger.info("All dependencies have been fixed!")
