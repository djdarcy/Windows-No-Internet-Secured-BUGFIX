#!/usr/bin/env python3
"""
NCSI Resolver Installer Script

This script provides a complete installation solution for the NCSI Resolver,
including system configuration and service installation.
"""

import argparse
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# For installer.py (add near the top after other imports)
try:
    from version import get_version_info, get_version_string
    
    # Get version information
    __version_info__ = get_version_info("installer")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.5.0"
    __description__ = "Windows Network Connectivity Status Indicator Resolver Installer"


# Add parent directory to path for imports
parent_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, parent_dir)

# Try to import the other modules
try:
    from system_config import (
        is_admin, run_as_admin, configure_system, check_configuration,
        reset_configuration, get_local_ip, detect_wifi_adapters
    )
    from service_installer import (
        install_service, uninstall_service, start_service, stop_service,
        check_service_status, create_service_files, get_nssm_path
    )
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Make sure system_config.py and service_installer.py are in the same directory as this script.")
    sys.exit(1)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('installer')

# Constants
DEFAULT_INSTALL_DIR = r"C:\Program Files\NCSI Resolver"
DEFAULT_PORT = 80

def print_banner():
    """Print a welcome banner for the installer."""
    banner = r"""
 _   _  ___ ___ ___  ___                _             
| \ | |/ __/ __|_ _|| _ \ ___  ___  ___| | __ _____  __
|  \| | (__\_ \ | | |   // -_)(_-< / _ \ \_\ V / -_)| _|
|_|\__|\___/___|___||_|_\\___||__/ \___/\__|\_/\____|_|                                                             
    Windows Network Connectivity Status Indicator Resolver
    """
    print(banner)
    print("\nThis installer will set up the NCSI Resolver to fix Windows 'No Internet' issues.\n")

def check_prerequisites():
    """
    Check if all prerequisites are met for installation.
    
    Returns:
        bool: True if all prerequisites are met, False otherwise
    """
    # Check if running on Windows
    if sys.platform != "win32":
        logger.error("This application is only compatible with Windows.")
        return False
    
    # Check if Python is 3.6+
    if sys.version_info < (3, 6):
        logger.error(f"Python 3.6 or higher is required. Current version: {sys.version}")
        return False
    
    # Check if required modules are available
    required_modules = ["http.server", "winreg", "ctypes"]
    missing_modules = []
    
    for module_name in required_modules:
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(module_name)
    
    if missing_modules:
        logger.error(f"Missing required Python modules: {', '.join(missing_modules)}")
        return False
    
    return True

def test_connectivity(host: str = None, port: int = DEFAULT_PORT) -> bool:
    """
    Test if the NCSI server can be started on the specified port.
    
    Args:
        host: Host address to bind to (default: local IP)
        port: Port to listen on
    
    Returns:
        bool: True if successful, False otherwise
    """
    # Import socket to test port availability
    import socket
    
    # Determine host address if not specified
    if host is None:
        host = get_local_ip() or "0.0.0.0"
    
    try:
        # Try to bind to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.close()
        return True
    except Exception as e:
        logger.error(f"Port {port} on {host} is unavailable: {e}")
        return False

def perform_full_installation(install_dir: str, port: int, quick_mode: bool = False) -> bool:
    """
    Perform a full installation of the NCSI Resolver.
    
    Args:
        install_dir: Directory to install the service
        port: Port to use for the NCSI server
        quick_mode: Skip confirmations and use defaults
        
    Returns:
        bool: True if successful, False otherwise
    """
    print_banner()
    
    # Check prerequisites
    if not check_prerequisites():
        return False
    
    # Check administrative privileges
    if not is_admin():
        logger.warning("Administrative privileges are required for installation.")
        if not quick_mode:
            input("Press Enter to continue and request admin privileges...")
        
        # Re-run with admin privileges
        run_as_admin(
            sys.argv[0],
            f"--install-dir={install_dir}",
            f"--port={port}",
            "--quick" if quick_mode else ""
        )
        return True
    
    # Test connectivity
    if not test_connectivity(None, port):
        logger.error(f"Port {port} is in use. Please choose a different port or close the application using it.")
        return False
    
    # Get NSSM path
    nssm_path = get_nssm_path()
    if not nssm_path:
        logger.error("Failed to obtain NSSM for service installation.")
        return False
    
    logger.info("Starting installation...")
    
    # Check for Wi-Fi adapters
    wifi_adapters = detect_wifi_adapters()
    has_wifi = len(wifi_adapters) > 0
    
    if has_wifi:
        logger.info(f"Found {len(wifi_adapters)} wireless adapter(s): {', '.join(wifi_adapters)}")
    else:
        logger.info("No wireless adapters detected. Wi-Fi optimization will be skipped.")
    
    # Configure system settings
    logger.info("Configuring Windows system settings...")
    
    # Pass the Wi-Fi information to configure_system
    if not configure_system(probe_host=None, probe_path="/ncsi.txt", restart_services=True, configure_wifi=has_wifi):
        logger.error("Failed to configure system settings.")
        return False
    
    # Create service files
    logger.info(f"Creating service files in {install_dir}...")
    if not create_service_files(install_dir, port):
        logger.error("Failed to create service files.")
        return False
    
    # Install and start the service
    logger.info("Installing and starting NCSI Resolver service...")
    if not install_service(install_dir, nssm_path):
        logger.error("Failed to install service.")
        return False
    
    # Use a timeout when starting the service
    start_timeout = 30  # seconds
    start_time = time.time()
    service_started = False
    
    logger.info(f"Starting service (timeout: {start_timeout} seconds)...")
    
    if not start_service():
        logger.warning("Service installed but could not be started automatically.")
        logger.warning("You may need to start it manually using 'net start NCSIResolver'.")
    else:
        # Wait for service to be fully running, but with timeout
        while time.time() - start_time < start_timeout:
            status = check_service_status()
            if status.get("running"):
                service_started = True
                break
            time.sleep(1)
    
    # Verify installation
    config = check_configuration()
    status = check_service_status()
    
    if config.get("is_configured") and status.get("installed"):
        logger.info("NCSI Resolver has been successfully installed and configured!")
        logger.info(f"Service status: {status.get('status', 'Unknown')}")
        
        if status.get("running"):
            logger.info("Windows should now correctly detect internet connectivity.")
        else:
            logger.warning("Service is not running. You may need to start it manually.")
        
        return True
    else:
        logger.error("Installation appears incomplete. Please check the logs for errors.")
        return False

def perform_uninstallation(quick_mode: bool = False) -> bool:
    """
    Uninstall the NCSI Resolver.
    
    Args:
        quick_mode: Skip confirmations
        
    Returns:
        bool: True if successful, False otherwise
    """
    # Check administrative privileges
    if not is_admin():
        logger.warning("Administrative privileges are required for uninstallation.")
        if not quick_mode:
            input("Press Enter to continue and request admin privileges...")
        
        # Re-run with admin privileges
        run_as_admin(sys.argv[0], "--uninstall", "--quick" if quick_mode else "")
        return True
    
    # Get NSSM path
    nssm_path = get_nssm_path()
    if not nssm_path:
        logger.error("Failed to obtain NSSM for service uninstallation.")
        return False
    
    logger.info("Starting uninstallation...")
    
    # Uninstall service
    logger.info("Stopping and removing NCSI Resolver service...")
    if not uninstall_service(nssm_path):
        logger.warning("Failed to completely uninstall service.")
    
    # Reset system configuration
    logger.info("Restoring system configuration to defaults...")
    if not reset_configuration():
        logger.warning("Failed to fully reset system configuration.")
    
    logger.info("NCSI Resolver has been uninstalled.")
    return True

def main():
    """Main entry point when running as a script."""
    parser = argparse.ArgumentParser(description=__description__)
    
    # Add version action (uses version.py if available)
    try:
        parser.add_argument('--version', action='version', 
                           version=get_version_string("installer"))
    except NameError:
        # Fallback if get_version_string is not available
        parser.add_argument('--version', action='version', 
                           version=f'{__description__} v{__version__}')
    
    # Define command actions
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--install", action="store_true", help="Install NCSI Resolver")
    action_group.add_argument("--uninstall", action="store_true", help="Uninstall NCSI Resolver")
    action_group.add_argument("--check", action="store_true", help="Check installation status")
    
    # Additional options
    parser.add_argument("--install-dir", default=DEFAULT_INSTALL_DIR, help=f"Installation directory (default: {DEFAULT_INSTALL_DIR})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to use for the NCSI server (default: {DEFAULT_PORT})")
    parser.add_argument("--quick", action="store_true", help="Quick mode (skip confirmations)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Perform requested action
    if args.install:
        perform_full_installation(args.install_dir, args.port, args.quick)
    
    elif args.uninstall:
        perform_uninstallation(args.quick)
    
    elif args.check:
        # Check current status
        config = check_configuration()
        service_status = check_service_status()
        
        print("\nNCSI Resolver Status:")
        print("-" * 50)
        print(f"System Configuration: {'Configured' if config.get('is_configured') else 'Not Configured'}")
        
        # Print registry settings
        if 'registry_settings' in config:
            print("\nRegistry Settings:")
            for key, value in config['registry_settings'].items():
                print(f"  {key}: {value}")
        
        # Print hosts file redirect
        if 'hosts_file_redirect' in config:
            print(f"\nHosts File Redirect: {config.get('hosts_file_redirect') or 'Not set'}")
        
        # Print service status
        print(f"\nService Status: {service_status.get('status', 'Unknown')}")
        print(f"Service Installed: {'Yes' if service_status.get('installed') else 'No'}")
        print(f"Service Running: {'Yes' if service_status.get('running') else 'No'}")
        
        # Overall status
        if config.get("is_configured") and service_status.get("running"):
            print("\nOverall Status: NCSI Resolver is fully operational")
        elif config.get("is_configured") and service_status.get("installed"):
            print("\nOverall Status: NCSI Resolver is installed but not running")
        elif config.get("is_configured"):
            print("\nOverall Status: System is configured but service is not installed")
        else:
            print("\nOverall Status: NCSI Resolver is not installed")

if __name__ == "__main__":
    main()
