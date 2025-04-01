#!/usr/bin/env python3
"""
NCSI Resolver Service Installer

This module installs the NCSI Resolver as a Windows service to ensure it runs
automatically at system startup.
"""

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Try importing our custom modules
try:
    # UPDATED: Changed import paths to reference the NCSIresolver subdirectory
    from NCSIresolver.config_manager import get_config
    from NCSIresolver.directory_manager import DirectoryManager
    from NCSIresolver.logger import get_logger
except ImportError:
    # If imported outside the package, define minimal versions
    config = None
    class DirectoryManager:
        def __init__(self, base_dir=None):
            pass
        def create_directory(self, path, description=None):
            os.makedirs(path, exist_ok=True)
            return path
        def create_junction_pair(self, dir1, dir2, link1_name=None, link2_name=None):
            return True

    def get_logger(name, verbosity=0, log_file=None):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        return logger

try:
    from version import get_version_info
    
    # Get version information
    __version_info__ = get_version_info("service_installer")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.7.0"
    __description__ = "NCSI Resolver Service Installer"

# Import system configuration module
try:
    from system_config import is_admin, run_as_admin
except ImportError:
    # If imported outside the package, define these functions here
    def is_admin():
        """Check if the current process has administrative privileges."""
        try:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def run_as_admin(script_path, *args):
        """Restart the current script with administrative privileges."""
        if not is_admin():
            import ctypes
            import sys
            
            arg_list = list(args)
            
            if script_path.endswith('.py'):
                cmd = [sys.executable, script_path] + arg_list
            else:
                cmd = [script_path] + arg_list
            
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", cmd[0], ' '.join(f'"{arg}"' for arg in cmd[1:]), None, 1
                )
                sys.exit(0)
            except Exception as e:
                print(f"Failed to get admin privileges: {e}")
                sys.exit(1)

# Set up logging
logger = get_logger('service_installer')

# Define constants (will use config_manager values if available)
# Define TIMEOUT here at the module level - FIX for the syntax error
SERVICE_NAME = "NCSIResolver"
SERVICE_DISPLAY_NAME = "NCSI Resolver Service"
SERVICE_DESCRIPTION = "Resolves Windows Network Connectivity Status Indicator issues by serving local NCSI test endpoints."
DEFAULT_INSTALL_DIR = r"C:\Program Files\NCSI Resolver"
DEFAULT_PORT = 80
NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
# Define TIMEOUT at the module level - FIX
global TIMEOUT
TIMEOUT = 30  # seconds
BACKUP_DIR = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "NCSI_Resolver", "Backups")

# Get configuration (if available)
if 'get_config' in globals():
    config = get_config()
    # Get constants from config
    SERVICE_NAME = config.get("installation.service_name", "NCSIResolver")
    SERVICE_DISPLAY_NAME = config.get("installation.service_display_name", "NCSI Resolver Service")
    SERVICE_DESCRIPTION = config.get("installation.service_description",
                                    "Resolves Windows Network Connectivity Status Indicator issues by serving local NCSI test endpoints.")
    DEFAULT_INSTALL_DIR = config.get("installation.default_dir", r"C:\Program Files\NCSI Resolver")
    DEFAULT_PORT = config.get("server.default_port", 80)
    NSSM_URL = config.get("installation.nssm_url", "https://nssm.cc/release/nssm-2.24.zip")
    TIMEOUT = config.get("installation.timeout", 30)  # seconds
    BACKUP_DIR = config.get("server.backup_dir", os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), "NCSI_Resolver", "Backups"))

def check_nssm_installed() -> bool:
    """
    Check if NSSM (Non-Sucking Service Manager) is installed or available.
    
    Returns:
        bool: True if NSSM is available, False otherwise
    """
    try:
        # Try to run nssm help command
        result = subprocess.run(
            ["nssm", "help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return "NSSM: The Non-Sucking Service Manager" in result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False

def download_nssm() -> Optional[str]:
    """
    Download NSSM if not already installed.
    
    Returns:
        Optional[str]: Path to nssm.exe if successful, None otherwise
    """
    logger.info("Downloading NSSM (Non-Sucking Service Manager)...")
    
    try:
        # Create temp directory
        temp_dir = Path(tempfile.gettempdir()) / "nssm_download"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Download NSSM
        zip_path = temp_dir / "nssm.zip"
        
        # Check if we already have the zip
        if not os.path.exists(zip_path):
            urllib.request.urlretrieve(NSSM_URL, zip_path)
            logger.info(f"Downloaded NSSM zip to {zip_path}")
        else:
            logger.info(f"Using previously downloaded NSSM zip from {zip_path}")
        
        # Check if we've already extracted it
        nssm_win64_path = temp_dir / "nssm-2.24" / "win64" / "nssm.exe"
        nssm_win32_path = temp_dir / "nssm-2.24" / "win32" / "nssm.exe"
        
        if os.path.exists(nssm_win64_path) or os.path.exists(nssm_win32_path):
            logger.info("NSSM already extracted")
        else:
            # Extract NSSM
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
            logger.info("Extracted NSSM zip file")
        
        # Find nssm.exe (use 64-bit version if available)
        if os.path.exists(nssm_win64_path):
            nssm_path = nssm_win64_path
        elif os.path.exists(nssm_win32_path):
            nssm_path = nssm_win32_path
        else:
            logger.error("Failed to find nssm.exe in extracted files")
            return None
        
        logger.info(f"Found NSSM at {nssm_path}")
        return str(nssm_path)
    
    except Exception as e:
        logger.error(f"Failed to download NSSM: {e}")
        return None

def get_nssm_path() -> Optional[str]:
    """
    Get the path to NSSM executable, downloading it if necessary and caching it.
    
    Returns:
        Optional[str]: Path to nssm.exe if available, None otherwise
    """
    # First, check if we already have a cached copy in the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    cached_nssm = os.path.join(script_dir, "nssm.exe")
    
    if os.path.exists(cached_nssm):
        logger.info(f"Using cached NSSM from {cached_nssm}")
        return cached_nssm
    
    # Check if NSSM is in PATH
    try:
        result = subprocess.run(
            ["where", "nssm"], 
            capture_output=True, 
            text=True, 
            check=True,
            timeout=5
        )
        nssm_path = result.stdout.strip().split('\n')[0]
        logger.info(f"Found NSSM in PATH: {nssm_path}")
        return nssm_path
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    # Download NSSM if not found
    nssm_path = download_nssm()
    
    # If download successful, copy to script directory for future use
    if nssm_path:
        try:
            shutil.copy2(nssm_path, cached_nssm)
            logger.info(f"Cached NSSM to {cached_nssm} for future use")
            return cached_nssm
        except Exception as e:
            logger.warning(f"Could not cache NSSM to script directory: {e}")
            return nssm_path
    
    return None

def create_service_files(install_dir: str, port: int = DEFAULT_PORT) -> bool:
    """
    Create necessary files for the service in the installation directory.
    
    Args:
        install_dir: Directory to install service files
        port: Port to use for the NCSI server
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Creating installation directory at {install_dir}")
        # Create installation directory if it doesn't exist
        os.makedirs(install_dir, exist_ok=True)
        
        # Copy necessary files
        source_dir = os.path.dirname(os.path.abspath(__file__))
        logger.debug(f"Using source directory: {source_dir}")
        
        # Files to copy
        files_to_copy = [
            {"src": os.path.join(source_dir, "NCSIresolver", "ncsi_server.py"), 
            "dst": os.path.join(install_dir, "ncsi_server.py")},
            {"src": os.path.join(source_dir, "system_config.py"), 
            "dst": os.path.join(install_dir, "system_config.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "service_wrapper.py"), 
            "dst": os.path.join(install_dir, "service_wrapper.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "redirect.html"), 
            "dst": os.path.join(install_dir, "redirect.html")},
            {"src": os.path.join(source_dir, "NCSIresolver", "config.json"), 
            "dst": os.path.join(install_dir, "config.json")},
            {"src": os.path.join(source_dir, "NCSIresolver", "config_manager.py"), 
            "dst": os.path.join(install_dir, "config_manager.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "logger.py"), 
            "dst": os.path.join(install_dir, "logger.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "directory_manager.py"), 
            "dst": os.path.join(install_dir, "directory_manager.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "network_diagnostics.py"), 
            "dst": os.path.join(install_dir, "network_diagnostics.py")},
            {"src": os.path.join(source_dir, "NCSIresolver", "security_monitoring.py"), 
            "dst": os.path.join(install_dir, "security_monitoring.py")}
        ]
        
        # Count of successfully copied files
        copied_files = 0
        
        # Copy files using the updated structure
        for file_info in files_to_copy:
            src_path = file_info["src"]
            dst_path = file_info["dst"]
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                logger.info(f"Copied {os.path.basename(src_path)} to {dst_path}")
                copied_files += 1
            else:
                logger.warning(f"Source file {src_path} not found, skipping")
        
        # Check if we at least copied the essential files
        essential_files = ["ncsi_server.py", "system_config.py", "service_wrapper.py"]
        for filename in essential_files:
            if not os.path.exists(os.path.join(install_dir, filename)):
                logger.error(f"Essential file {filename} was not copied")
                return False
        
        # Update configuration with the port setting
        config_path = os.path.join(install_dir, "config.json")
        try:
            if os.path.exists(config_path):
                # Load configuration
                with open(config_path, 'r') as f:
                    import json
                    config_data = json.load(f)
                
                # Update port
                if 'server' not in config_data:
                    config_data['server'] = {}
                config_data['server']['default_port'] = port
                
                # Save updated configuration
                with open(config_path, 'w') as f:
                    json.dump(config_data, f, indent=2)
                
                logger.info(f"Updated configuration with port {port}")
            else:
                logger.warning("Configuration file not found, port will use default value")
        except Exception as e:
            logger.warning(f"Failed to update configuration: {e}")
        
        # Create directory structure with junction points
        try:
            # Create DirectoryManager instance
            dir_manager = DirectoryManager(install_dir)
            
            # Set up directory structure
            backup_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 
                                     "NCSI_Resolver", "Backups")
            logs_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 
                                   "NCSI_Resolver", "Logs")
            
            # Ensure directories exist
            os.makedirs(backup_dir, exist_ok=True)
            os.makedirs(logs_dir, exist_ok=True)
            
            # Create junction points
            dir_manager.create_junction_pair(install_dir, backup_dir, "Backups", "Installation")
            dir_manager.create_junction_pair(install_dir, logs_dir, "Logs", "Installation")
            
            logger.info("Created directory structure with junction points")
        except Exception as e:
            logger.warning(f"Could not create all directory junctions: {e}")
            # This is not critical, so we continue
        
        logger.info(f"Created service files in {install_dir}")
        return True
    
    except Exception as e:
        logger.error(f"Error creating service files: {e}")
        import traceback
        logger.debug(f"Stack trace: {traceback.format_exc()}")
        return False

def install_service(install_dir: str, nssm_path: str) -> bool:
    """
    Install the NCSI Resolver as a Windows service using NSSM.
    
    Args:
        install_dir: Directory where service files are installed
        nssm_path: Path to NSSM executable
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Path to wrapper script
        wrapper_path = os.path.join(install_dir, "service_wrapper.py")
        if not os.path.exists(wrapper_path):
            logger.error(f"Service wrapper script not found at {wrapper_path}")
            return False
        
        # Check if Python is in PATH
        python_path = sys.executable
        
        # Check if service already exists
        try:
            subprocess.run(
                ["sc", "query", SERVICE_NAME],
                check=True,
                capture_output=True,
                timeout=5
            )
            # Service exists, remove it first
            logger.info(f"Service {SERVICE_NAME} already exists, removing it first...")
            stop_service()
            subprocess.run(
                [nssm_path, "remove", SERVICE_NAME, "confirm"],
                check=True,
                capture_output=True,
                timeout=10
            )
            # Wait a moment for service removal
            time.sleep(2)
        except subprocess.CalledProcessError:
            # Service doesn't exist, which is what we want
            pass
        
        # Install the service - properly quote paths with spaces
        logger.info(f"Installing service {SERVICE_NAME} to run {wrapper_path}")
        install_result = subprocess.run(
            [nssm_path, "install", SERVICE_NAME, python_path, wrapper_path],
            check=False,
            capture_output=True,
            timeout=10
        )
        
        if install_result.returncode != 0:
            stderr = install_result.stderr.decode() if install_result.stderr else "Unknown error"
            logger.error(f"Failed to install service: {stderr}")
            return False
        
        # Configure service properties
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "DisplayName", SERVICE_DISPLAY_NAME],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "Description", SERVICE_DESCRIPTION],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        # Set startup directory
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "AppDirectory", install_dir],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        # Configure to restart on failure
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "AppRestartDelay", "30000"],  # 30 seconds
            check=True,
            capture_output=True,
            timeout=5
        )
        
        # Set to auto-start
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "Start", "SERVICE_AUTO_START"],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        # UPDATED: Set stdout/stderr logging to use the Logs directory
        logs_dir = os.path.join(install_dir, "Logs")
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir, exist_ok=True)
            
        log_path = os.path.join(logs_dir, "service_output.log")
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "AppStdout", log_path],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "AppStderr", log_path],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        # Explicitly set the full command line to handle spaces correctly
        subprocess.run(
            [nssm_path, "set", SERVICE_NAME, "AppParameters", f'"{wrapper_path}"'],
            check=True,
            capture_output=True,
            timeout=5
        )
        
        logger.info(f"Successfully installed {SERVICE_DISPLAY_NAME}")
        return True
    
    except subprocess.TimeoutExpired as e:
        logger.error(f"Timeout while installing service: {e}")
        return False
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"Error installing service: {stderr}")
        return False
    
    except Exception as e:
        logger.error(f"Error installing service: {e}")
        return False

def start_service() -> bool:
    """
    Start the NCSI Resolver service.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Starting service {SERVICE_NAME}")
        subprocess.run(
            ["net", "start", SERVICE_NAME],
            check=True,
            capture_output=True,
            timeout=TIMEOUT
        )
        
        logger.info(f"Started {SERVICE_DISPLAY_NAME}")
        return True
    
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while starting service")
        return False
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        if "already been started" in error_msg:
            logger.info(f"{SERVICE_DISPLAY_NAME} is already running")
            return True
        else:
            logger.error(f"Error starting service: {error_msg}")
            return False
    
    except Exception as e:
        logger.error(f"Error starting service: {e}")
        return False

def stop_service() -> bool:
    """
    Stop the NCSI Resolver service.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        logger.info(f"Stopping service {SERVICE_NAME}")
        subprocess.run(
            ["net", "stop", SERVICE_NAME],
            check=True,
            capture_output=True,
            timeout=TIMEOUT
        )
        
        logger.info(f"Stopped {SERVICE_DISPLAY_NAME}")
        return True
    
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while stopping service")
        # Force kill the service process if it's not stopping nicely
        try:
            subprocess.run(
                ["taskkill", "/F", "/FI", f"SERVICES eq {SERVICE_NAME}"],
                check=False,
                capture_output=True,
                timeout=5
            )
            logger.warning("Forcefully terminated service processes")
        except Exception:
            pass
        return False
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.decode() if e.stderr else str(e)
        if "not started" in error_msg:
            logger.info(f"{SERVICE_DISPLAY_NAME} is not running")
            return True
        else:
            logger.error(f"Error stopping service: {error_msg}")
            return False
    
    except Exception as e:
        logger.error(f"Error stopping service: {e}")
        return False

def uninstall_service(nssm_path: str) -> bool:
    """
    Uninstall the NCSI Resolver service.
    
    Args:
        nssm_path: Path to NSSM executable
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Stop the service first
        stop_service()
        
        # Wait a moment to ensure service is fully stopped
        time.sleep(2)
        
        # Uninstall the service
        logger.info(f"Removing service {SERVICE_NAME}")
        subprocess.run(
            [nssm_path, "remove", SERVICE_NAME, "confirm"],
            check=True,
            capture_output=True,
            timeout=TIMEOUT
        )
        
        logger.info(f"Uninstalled {SERVICE_DISPLAY_NAME}")
        return True
    
    except subprocess.TimeoutExpired:
        logger.error(f"Timeout while uninstalling service")
        return False
        
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode() if e.stderr else str(e)
        logger.error(f"Error uninstalling service: {stderr}")
        return False
    
    except Exception as e:
        logger.error(f"Error uninstalling service: {e}")
        return False

def check_service_status() -> Dict[str, Union[bool, str]]:
    """
    Check the status of the NCSI Resolver service.
    
    Returns:
        Dict: Status information for the service
    """
    result = {
        "installed": False,
        "running": False,
        "status": "Not installed"
    }
    
    try:
        # Check if service is installed
        logger.info(f"Checking status of service {SERVICE_NAME}")
        sc_query = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if sc_query.returncode != 0:
            logger.info(f"Service {SERVICE_NAME} is not installed")
            return result
        
        # Service is installed
        result["installed"] = True
        
        # Check if service is running
        if "RUNNING" in sc_query.stdout:
            result["running"] = True
            result["status"] = "Running"
        elif "STOPPED" in sc_query.stdout:
            result["status"] = "Stopped"
        elif "STARTING" in sc_query.stdout:
            result["status"] = "Starting"
        elif "STOPPING" in sc_query.stdout:
            result["status"] = "Stopping"
        else:
            result["status"] = "Unknown"
        
        logger.info(f"Service {SERVICE_NAME} status: {result['status']}")
        return result
    
    except subprocess.TimeoutExpired:
        logger.error("Timeout while checking service status")
        result["status"] = "Query timeout"
        return result
        
    except Exception as e:
        logger.error(f"Error checking service status: {e}")
        return result

def verify_installation(install_dir: str) -> Dict[str, Union[bool, str]]:
    """
    Verify the NCSI Resolver installation.
    
    Args:
        install_dir: Installation directory
        
    Returns:
        Dict: Verification results
    """
    result = {
        "success": True,
        "errors": [],
        "files_ok": True,
        "service_ok": False,
        "registry_ok": False,
        "hosts_ok": False,
        "connection_ok": False
    }
    
    # Check for essential files
    essential_files = ["ncsi_server.py", "system_config.py", "service_wrapper.py"]
    for filename in essential_files:
        file_path = os.path.join(install_dir, filename)
        if not os.path.exists(file_path):
            result["files_ok"] = False
            result["success"] = False
            result["errors"].append(f"Essential file {filename} is missing")
    
    # Check service status
    service_status = check_service_status()
    result["service_ok"] = service_status.get("installed", False)
    if not result["service_ok"]:
        result["success"] = False
        result["errors"].append("Service is not installed")
    
    # Check if service is running
    if service_status.get("running", False):
        result["service_running"] = True
    else:
        result["service_running"] = False
        if result["service_ok"]:  # Only an error if service is installed
            result["success"] = False
            result["errors"].append("Service is installed but not running")
    
    # Try system_config check_configuration if available
    try:
        from system_config import check_configuration
        config_status = check_configuration()
        result["registry_ok"] = "ActiveWebProbeHost" in config_status.get("registry_settings", {})
        result["hosts_ok"] = config_status.get("hosts_file_redirect") is not None
        
        if not result["registry_ok"]:
            result["success"] = False
            result["errors"].append("Registry settings are not properly configured")
        
        if not result["hosts_ok"]:
            result["success"] = False
            result["errors"].append("Hosts file is not properly configured")
    except ImportError:
        # Can't check system configuration
        result["errors"].append("Could not verify system configuration")
    
    # Try to connect to the local NCSI server
    try:
        import socket
        import time
        
        # Get local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        
        # Try to connect to the NCSI server
        port = 80  # Default port
        
        # Try multiple times
        for _ in range(3):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect((local_ip, port))
                s.close()
                result["connection_ok"] = True
                break
            except:
                time.sleep(1)
        
        if not result["connection_ok"]:
            result["success"] = False
            result["errors"].append(f"Could not connect to NCSI server on {local_ip}:{port}")
    except Exception as e:
        result["errors"].append(f"Error checking server connection: {e}")
    
    return result

def main():
    """Main entry point when running as a script."""
    parser = argparse.ArgumentParser(description="NCSI Resolver Service Installer")
    
    # Define command actions
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--install", action="store_true", help="Install the service")
    action_group.add_argument("--uninstall", action="store_true", help="Uninstall the service")
    action_group.add_argument("--start", action="store_true", help="Start the service")
    action_group.add_argument("--stop", action="store_true", help="Stop the service")
    action_group.add_argument("--status", action="store_true", help="Check service status")
    action_group.add_argument("--restart", action="store_true", help="Restart the service")
    action_group.add_argument("--verify", action="store_true", help="Verify installation")
    
    # Additional options
    parser.add_argument("--install-dir", default=DEFAULT_INSTALL_DIR, help=f"Installation directory (default: {DEFAULT_INSTALL_DIR})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to use for the NCSI server (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"Timeout for operations in seconds (default: {TIMEOUT})")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (can be used multiple times)")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Use timeout from args if specified
    global timeout
    TIMEOUT = args.timeout
    
    # Check if running on Windows
    if platform.system() != "Windows":
        logger.error("This script is only compatible with Windows")
        sys.exit(1)
    
    # Check admin privileges for actions that require them
    if (args.install or args.uninstall or args.start or args.stop or args.restart or args.verify) and not is_admin():
        logger.info("Administrative privileges required, requesting elevation...")
        
        # Build argument list for elevation
        elevate_args = []
        if args.install:
            elevate_args.append("--install")
        elif args.uninstall:
            elevate_args.append("--uninstall")
        elif args.start:
            elevate_args.append("--start")
        elif args.stop:
            elevate_args.append("--stop")
        elif args.restart:
            elevate_args.append("--restart")
        elif args.verify:
            elevate_args.append("--verify")
        
        if args.install_dir != DEFAULT_INSTALL_DIR:
            elevate_args.append(f"--install-dir={args.install_dir}")
        
        if args.port != DEFAULT_PORT:
            elevate_args.append(f"--port={args.port}")
        
        if args.debug:
            elevate_args.append("--debug")
            
        if args.timeout != TIMEOUT:
            elevate_args.append(f"--timeout={args.timeout}")
            
        if args.verbose > 0:
            elevate_args.append("-" + "v" * args.verbose)
        
        run_as_admin(sys.argv[0], *elevate_args)
        return
    
    # Check service status
    if args.status:
        status = check_service_status()
        
        print(f"\nNCSI Resolver Service Status:")
        print(f"  Installed: {'Yes' if status['installed'] else 'No'}")
        if status['installed']:
            print(f"  Status: {status['status']}")
        
        return
        
    # Verify installation
    if args.verify:
        verify_results = verify_installation(args.install_dir)
        
        print(f"\nNCSI Resolver Installation Verification:")
        print(f"  Overall status: {'Success' if verify_results['success'] else 'Issues detected'}")
        print(f"  Files: {'OK' if verify_results['files_ok'] else 'Missing'}")
        print(f"  Service: {'OK' if verify_results['service_ok'] else 'Not installed'}")
        if verify_results['service_ok']:
            print(f"  Service running: {'Yes' if verify_results.get('service_running', False) else 'No'}")
        print(f"  Registry: {'OK' if verify_results['registry_ok'] else 'Not configured'}")
        print(f"  Hosts file: {'OK' if verify_results['hosts_ok'] else 'Not configured'}")
        print(f"  Server connection: {'OK' if verify_results['connection_ok'] else 'Failed'}")
        
        if verify_results['errors']:
            print("\nErrors detected:")
            for error in verify_results['errors']:
                print(f"  - {error}")
                
        return
    
    # Handle other actions
    if args.install:
        # Get NSSM path
        nssm_path = get_nssm_path()
        if not nssm_path:
            logger.error("NSSM not found and could not be downloaded")
            sys.exit(1)
        
        logger.info(f"Installing NCSI Resolver service to {args.install_dir}...")
        
        # Create service files
        if not create_service_files(args.install_dir, args.port):
            logger.error("Failed to create service files")
            sys.exit(1)
        
        # Install the service
        if not install_service(args.install_dir, nssm_path):
            logger.error("Failed to install service")
            sys.exit(1)
        
        # Start the service
        service_started = start_service()
        
        # Verify installation
        verify_results = verify_installation(args.install_dir)
        
        if verify_results['success'] and service_started:
            print("\nNCSI Resolver has been installed successfully")
            print("The service is now running in the background.")
            print("Windows should now correctly detect your internet connection.")
        elif not service_started:
            print("\nNCSI Resolver has been installed but the service failed to start.")
            print("Please check the logs for errors and try starting the service manually.")
        else:
            print("\nNCSI Resolver installation completed with some issues:")
            for error in verify_results['errors']:
                print(f"  - {error}")
    
    elif args.uninstall:
        # Get NSSM path
        nssm_path = get_nssm_path()
        if not nssm_path:
            logger.error("NSSM not found and could not be downloaded")
            sys.exit(1)
        
        # Uninstall the service
        if not uninstall_service(nssm_path):
            logger.error("Failed to uninstall service")
            sys.exit(1)
        
        # Make sure registry and hosts file are restored (if system_config is available)
        try:
            from system_config import reset_configuration
            if reset_configuration():
                logger.info("System configuration reset to original settings")
            else:
                logger.warning("Could not fully reset system configuration")
        except ImportError:
            logger.warning("Could not reset system configuration (system_config module not available)")
        
        print("\nNCSI Resolver has been uninstalled successfully")
        print("Windows NCSI settings have been restored to default values.")
    
    elif args.start:
        # Start the service
        if not start_service():
            logger.error("Failed to start service")
            sys.exit(1)
            
        print(f"\n{SERVICE_DISPLAY_NAME} started successfully")
    
    elif args.stop:
        # Stop the service
        if not stop_service():
            logger.error("Failed to stop service")
            sys.exit(1)
            
        print(f"\n{SERVICE_DISPLAY_NAME} stopped successfully")
    
    elif args.restart:
        # Restart the service
        if not stop_service():
            logger.warning("Failed to stop service, attempting to start anyway")
        
        # Wait a moment to ensure service is fully stopped
        time.sleep(2)
        
        if not start_service():
            logger.error("Failed to start service")
            sys.exit(1)
        
        print(f"\n{SERVICE_DISPLAY_NAME} restarted successfully")

if __name__ == "__main__":
    main()