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

try:
    from version import get_version_info
    
    # Get version information
    __version_info__ = get_version_info("service_installer")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.5.0"
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
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('service_installer')

# Constants
SERVICE_NAME = "NCSIResolver"
SERVICE_DISPLAY_NAME = "NCSI Resolver Service"
SERVICE_DESCRIPTION = "Resolves Windows Network Connectivity Status Indicator issues by serving local NCSI test endpoints."
DEFAULT_INSTALL_DIR = r"C:\Program Files\NCSI Resolver"
DEFAULT_PORT = 80
NSSM_URL = "https://nssm.cc/release/nssm-2.24.zip"
TIMEOUT = 30  # seconds

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
        # Create installation directory if it doesn't exist
        os.makedirs(install_dir, exist_ok=True)
        
        # Copy necessary files
        source_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Copy Python scripts
        for filename in ["ncsi_server.py", "system_config.py"]:
            src_path = os.path.join(source_dir, filename)
            dst_path = os.path.join(install_dir, filename)
            
            if os.path.exists(src_path):
                shutil.copy2(src_path, dst_path)
                logger.info(f"Copied {filename} to {dst_path}")
            else:
                logger.error(f"Source file {src_path} not found")
                return False
        
        # Create the service wrapper script with properly substituted port value
        wrapper_path = os.path.join(install_dir, "service_wrapper.py")
        
        # Get the template content
        service_wrapper_template = """#!/usr/bin/env python3
\"\"\"
NCSI Resolver Service Wrapper

This script is used to start the NCSI server as a Windows service.
This is a simplified version designed for maximum compatibility.
\"\"\"

import os
import sys
import logging
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Get the current directory (where this script is located)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Set up logging to file
LOG_PATH = os.path.join(CURRENT_DIR, "ncsi_resolver.log")
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ncsi_service')

# NCSI content constants - embed directly to avoid file access issues
NCSI_TEXT = b"Microsoft Connect Test"
REDIRECT_HTML = b\"\"\"<!DOCTYPE html>
<html>
<head>
    <title>Connection Success</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            text-align: center;
            padding: 40px;
            background-color: #f7f7f7;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
            max-width: 500px;
            margin: 0 auto;
        }
        h1 {
            color: #0078d7;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Connection Successful</h1>
        <p>Your device is connected to the internet.</p>
        <p>This page is served by the NCSI Resolver utility running on your local network.</p>
    </div>
</body>
</html>
\"\"\"

# Define a simple request handler
class NCSIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        \"\"\"Log messages to our logger instead of stderr.\"\"\"
        logger.info(format % args)
        
    def do_GET(self):
        \"\"\"Handle GET requests.\"\"\"
        client_ip = self.client_address[0]
        logger.info(f"Request from {{client_ip}} for {{self.path}}")
        
        # Handle NCSI connectivity test paths
        if self.path == "/connecttest.txt" or self.path == "/ncsi.txt":
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-Length", str(len(NCSI_TEXT)))
            self.end_headers()
            self.wfile.write(NCSI_TEXT)
            
        # Handle NCSI redirect endpoint (used for captive portal detection)
        elif self.path == "/redirect":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(REDIRECT_HTML)))
            self.end_headers()
            self.wfile.write(REDIRECT_HTML)
            
        # Return a 404 for any other paths
        else:
            self.send_error(404, "Not Found")

def get_local_ip():
    \"\"\"Get the local IP address of the machine.\"\"\"
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {{e}}")
        return "0.0.0.0"  # Fall back to all interfaces

# Main service code
try:
    logger.info("Starting NCSI Resolver service...")
    
    # Get local IP or use all interfaces
    host = get_local_ip()
    
    # Define port - hardcoded for reliability
    port = {0}  # This will be replaced with the actual port number
    
    # Fallback to default port if substitution failed or value is invalid
    if not isinstance(port, int):
        logger.warning(f"Port value '{{port}}' is not valid, using default port 80")
        port = 80
    
    logger.info(f"Creating server on {{host}}:{{port}}")
    
    # Create and start the server
    httpd = HTTPServer((host, port), NCSIHandler)
    
    logger.info(f"NCSI Resolver server running on {{host}}:{{port}}")
    httpd.serve_forever()
    
except Exception as e:
    logger.error(f"Error starting NCSI Resolver service: {{e}}")
    sys.exit(1)
"""
        
        # Replace the port placeholder with the actual port
        service_wrapper_content = service_wrapper_template.format(port)
        
        # Write the file
        with open(wrapper_path, 'w') as f:
            f.write(service_wrapper_content)
        
        # Create junction points for easier navigation
        try:
            # Ensure backup directory exists
            backup_dir = os.path.join(os.environ.get('LOCALAPPDATA', os.path.expanduser('~')), 
                                    "NCSI_Resolver", "Backups")
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create junction point in installation directory pointing to backups
            backup_link_path = os.path.join(install_dir, "Backups")
            if not os.path.exists(backup_link_path):
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", backup_link_path, backup_dir],
                    check=False,
                    capture_output=True
                )
                logger.info(f"Created junction point from {backup_link_path} to {backup_dir}")
            
            # Create junction point in backup directory pointing to installation
            install_link_path = os.path.join(backup_dir, "Installation")
            if not os.path.exists(install_link_path):
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J", install_link_path, install_dir],
                    check=False,
                    capture_output=True
                )
                logger.info(f"Created junction point from {install_link_path} to {install_dir}")
                
        except Exception as e:
            logger.warning(f"Could not create directory junctions: {e}")
            # This is not critical, so we continue
        
        logger.info(f"Created service files in {install_dir}")
        return True
    
    except Exception as e:
        logger.error(f"Error creating service files: {e}")
        return False

# Fix for the install_service function in service_installer.py

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
        # Path to wrapper script - ensure it's properly quoted for spaces
        wrapper_path = os.path.join(install_dir, "service_wrapper.py")
        
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
        command = f'"{python_path}" "{wrapper_path}"'
        install_result = subprocess.run(
            [nssm_path, "install", SERVICE_NAME, python_path, wrapper_path],
            check=True,
            capture_output=True,
            timeout=10
        )
        
        if install_result.returncode != 0:
            logger.error(f"Failed to install service: {install_result.stderr.decode()}")
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
        
        # Set startup directory - properly quoted for spaces
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
        
        # Set stdout/stderr logging
        log_path = os.path.join(install_dir, "service_output.log")
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
        logger.error(f"Error installing service: {e.stderr.decode() if e.stderr else str(e)}")
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
        logger.error(f"Error uninstalling service: {e.stderr.decode() if e.stderr else str(e)}")
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
        sc_query = subprocess.run(
            ["sc", "query", SERVICE_NAME],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if sc_query.returncode != 0:
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
        
        return result
    
    except subprocess.TimeoutExpired:
        logger.error("Timeout while checking service status")
        result["status"] = "Query timeout"
        return result
        
    except Exception as e:
        logger.error(f"Error checking service status: {e}")
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
    
    # Additional options
    parser.add_argument("--install-dir", default=DEFAULT_INSTALL_DIR, help=f"Installation directory (default: {DEFAULT_INSTALL_DIR})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to use for the NCSI server (default: {DEFAULT_PORT})")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--timeout", type=int, default=TIMEOUT, help=f"Timeout for operations in seconds (default: {TIMEOUT})")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Use timeout from args if specified
    timeout_value = args.timeout
    
    # Check if running on Windows
    if platform.system() != "Windows":
        logger.error("This script is only compatible with Windows")
        sys.exit(1)
    
    # Check admin privileges for actions that require them
    if (args.install or args.uninstall or args.start or args.stop or args.restart) and not is_admin():
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
        
        if args.install_dir != DEFAULT_INSTALL_DIR:
            elevate_args.append(f"--install-dir={args.install_dir}")
        
        if args.port != DEFAULT_PORT:
            elevate_args.append(f"--port={args.port}")
        
        if args.debug:
            elevate_args.append("--debug")
            
        if args.timeout != TIMEOUT:
            elevate_args.append(f"--timeout={args.timeout}")
        
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
        if not start_service():
            logger.warning("Service installed but could not be started")
        
        logger.info(f"NCSI Resolver service installed successfully at {args.install_dir}")
    
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
        
        logger.info("NCSI Resolver service uninstalled successfully")
    
    elif args.start:
        # Start the service
        if not start_service():
            logger.error("Failed to start service")
            sys.exit(1)
    
    elif args.stop:
        # Stop the service
        if not stop_service():
            logger.error("Failed to stop service")
            sys.exit(1)
    
    elif args.restart:
        # Restart the service
        if not stop_service():
            logger.warning("Failed to stop service, attempting to start anyway")
        
        # Wait a moment to ensure service is fully stopped
        time.sleep(2)
        
        if not start_service():
            logger.error("Failed to start service")
            sys.exit(1)
        
        logger.info("NCSI Resolver service restarted successfully")

if __name__ == "__main__":
    main()
