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

# Try importing our custom modules
try:
    # UPDATED: Changed import paths to reference the NCSIresolver subdirectory
    from NCSIresolver.config_manager import get_config
    from NCSIresolver.directory_manager import DirectoryManager
    from NCSIresolver.logger import get_logger
    try:
        from firewall_helper import add_firewall_rule, update_firewall_rule, check_port_blocking
        firewall_helper_available = True
    except ImportError:
        firewall_helper_available = False
    config_available = True
except ImportError:
    config_available = False
    firewall_helper_available = False
    # Define minimal logger if logger module not available
    def get_logger(name, verbosity=0, log_file=None):
        logger = logging.getLogger(name)
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
        logger.addHandler(handler)
        return logger

# Try to get version information
try:
    from version import get_version_info, get_version_string
    
    # Get version information
    __version_info__ = get_version_info("installer")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.7.4"
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
        check_service_status, create_service_files, get_nssm_path, verify_installation
    )
    all_modules_available = True
except ImportError as e:
    all_modules_available = False
    print(f"Warning: Some required modules could not be imported: {e}")
    print("Install functionality may be limited.")
    
    # Define minimal versions of required functions if not available
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
logger = get_logger('installer')

# Define constants (will use config_manager values if available)
if config_available:
    config = get_config()
    DEFAULT_INSTALL_DIR = config.get("installation.default_dir", r"C:\Program Files\NCSI Resolver")
    DEFAULT_PORT = config.get("server.default_port", 80)
else:
    DEFAULT_INSTALL_DIR = r"C:\Program Files\NCSI Resolver"
    DEFAULT_PORT = 80

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
    if not all_modules_available:
        logger.warning("Some required modules are missing. Install functionality may be limited.")
    
    # Check if required Python modules are available
    required_modules = ["http.server", "socket", "json", "pathlib"]
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

def test_connectivity(host: str = None, port: int = DEFAULT_PORT, suggest_alternatives: bool = True) -> Tuple[bool, Optional[int]]:
    """
    Test if the NCSI server can be started on the specified port.
    
    Args:
        host: Host address to bind to (default: local IP)
        port: Port to listen on
        suggest_alternatives: Whether to suggest alternative ports
    
    Returns:
        Tuple[bool, Optional[int]]: (Success, Alternative port if available)
    """
    # Import socket to test port availability
    import socket
    
    # Determine host address if not specified
    if host is None:
        try:
            # Get local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))  # Connect to a known public IP
            host = s.getsockname()[0]
            s.close()
        except:
            host = "0.0.0.0"  # Use all interfaces if can't determine
    
    # Try the specified port
    try:
        # Try to bind to the port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind((host, port))
        sock.close()
        return True, None  # Port is available
    except Exception as e:
        logger.error(f"Port {port} on {host} is unavailable: {e}")
        
        # If not suggesting alternatives, just return failure
        if not suggest_alternatives:
            return False, None
            
        # Try some common alternative ports
        alternative_ports = [8080, 8888, 8000, 8081, 5225]
        for alt_port in alternative_ports:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind((host, alt_port))
                sock.close()
                logger.info(f"Alternative port {alt_port} is available")
                return False, alt_port  # Found an alternative port
            except:
                continue
                
        # No alternative found
        return False, None

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
    # Check prerequisites
    if not check_prerequisites():
        return False
    
    # Check administrative privileges
    if not is_admin():
        if quick_mode:
            # In quick mode, assume caller has already handled admin elevation (e.g., NSIS installer)
            # Continue anyway but log a warning
            logger.warning("Running without administrative privileges in quick mode - some features may fail")
        else:
            logger.warning("Administrative privileges are required for installation.")
            input("Press Enter to continue and request admin privileges...")

            # Re-run with admin privileges
            run_as_admin(
                sys.argv[0],
                f"--install-dir={install_dir}",
                f"--port={port}",
                "--nobanner"  # Add nobanner flag when elevating
            )
            return True
    
    # Test port availability before proceeding with installation
    logger.info(f"Testing port {port} availability...")
    port_ok, alternative_port = test_connectivity(None, port)
    
    if not port_ok:
        if alternative_port:
            if quick_mode:
                # In quick mode, automatically use the alternative port
                logger.warning(f"Port {port} is in use. Automatically using alternative port {alternative_port}")
                port = alternative_port
            else:
                # Ask the user if they want to use the alternative port
                response = input(f"\nPort {port} is in use. Would you like to use port {alternative_port} instead? (Y/N): ")
                if response.lower() == 'y':
                    logger.info(f"Using alternative port {alternative_port}")
                    port = alternative_port
                else:
                    logger.error(f"Port {port} is in use. Please choose a different port or close the application using it.")
                    return False
        else:
            logger.error(f"Port {port} is in use and no alternatives are available. Please choose a different port or close applications that may be using ports.")
            return False
    
    # Get NSSM path
    nssm_path = get_nssm_path()
    if not nssm_path:
        logger.error("Failed to obtain NSSM for service installation.")
        return False
    
    logger.info("Starting installation...")
    
    # Check for Wi-Fi adapters
    wifi_adapters = detect_wifi_adapters() if 'detect_wifi_adapters' in globals() else []
    has_wifi = len(wifi_adapters) > 0
    
    if has_wifi:
        logger.info(f"Found {len(wifi_adapters)} wireless adapter(s): {', '.join(wifi_adapters)}")
    else:
        logger.info("No wireless adapters detected. Wi-Fi optimization will be skipped.")
    
    # Configure system settings - Pass the detected port to configure_system
    logger.info(f"Configuring Windows system settings (using port {port})...")
    
    # Use the configure_system function if available / Pass WiFi info to configure_system
    if 'configure_system' in globals():
        if not configure_system(probe_host=None, probe_path="/ncsi.txt", port=port, restart_services=True, configure_wifi=has_wifi):
            logger.error("Failed to configure system settings.")
            return False
    else:
        logger.warning("System configuration module not available. System settings will not be modified.")
    
    # Configure Windows Firewall if available
    if firewall_helper_available:
        logger.info(f"Configuring Windows Firewall for port {port}...")
        if add_firewall_rule(port):
            logger.info("Windows Firewall configured successfully")
        else:
            logger.warning("Failed to configure Windows Firewall, continuing anyway")
    else:
        logger.warning("Firewall helper module not available. Firewall will not be configured.")
    
    # Create service files (skip if running from NSIS installer and files already exist)
    ncsi_server_path = os.path.join(install_dir, "NCSIresolver", "ncsi_server.py")
    if quick_mode and os.path.exists(ncsi_server_path):
        logger.info(f"Service files already present in {install_dir}, skipping file creation")
    else:
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
            
    # Verify service connectivity
    if service_started:
        logger.info("Service started successfully, verifying connectivity...")
        try:
            # Try to connect to the service
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2)
            s.connect(("127.0.0.1", port))
            s.close()
            logger.info(f"Successfully connected to service on port {port}")
        except Exception as e:
            logger.warning(f"Could not connect to service: {e}")
            logger.info("The service is running but might not be accessible.")
            logger.info("This could be due to firewall settings or other network configuration.")
            
            # Check if port is being blocked by firewall
            if firewall_helper_available:
                blocked, reason = check_port_blocking("127.0.0.1", port)
                if blocked:
                    logger.warning(f"Port {port} appears to be blocked: {reason}")
                    logger.info("Attempting to add firewall rule...")
                    if add_firewall_rule(port):
                        logger.info("Added firewall rule, please try connecting again")
                    else:
                        logger.warning("Failed to add firewall rule")
                else:
                    logger.info(f"Port {port} is not blocked by firewall: {reason}")
    
    # Verify installation
    if 'check_configuration' in globals():
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
    else:
        # If check_configuration not available, just check service status
        status = check_service_status()
        if status.get("installed"):
            if status.get("running"):
                logger.info("NCSI Resolver has been successfully installed!")
                logger.info("Windows should now correctly detect internet connectivity.")
                return True
            else:
                logger.warning("Service is installed but not running. You may need to start it manually.")
                return False
        else:
            logger.error("Installation failed. Service is not installed.")
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
        run_as_admin(sys.argv[0], "--uninstall", "--quick" if quick_mode else "") #, "--nobanner")
        return True
    
    # Get NSSM path
    nssm_path = get_nssm_path()
    if not nssm_path:
        logger.error("Failed to obtain NSSM for service uninstallation.")
        return False
    
    logger.info("Starting uninstallation...")
    
    # Remove firewall rule if the helper is available
    if firewall_helper_available:
        try:
            from firewall_helper import remove_firewall_rule
            if remove_firewall_rule():
                logger.info("Removed Windows Firewall rule")
            else:
                logger.warning("Failed to remove Windows Firewall rule, continuing anyway")
        except Exception as e:
            logger.warning(f"Error removing firewall rule: {e}")
    
    # Uninstall service
    logger.info("Stopping and removing NCSI Resolver service...")
    if not uninstall_service(nssm_path):
        logger.warning("Failed to completely uninstall service.")
    
    # Reset system configuration if available
    if 'reset_configuration' in globals():
        logger.info("Restoring system configuration to defaults...")
        if not reset_configuration():
            logger.warning("Failed to fully reset system configuration.")
    else:
        logger.warning("System configuration reset function not available.")
    
    logger.info("NCSI Resolver has been uninstalled.")
    return True

# Create a global flag to track if banner has been displayed
_banner_displayed = False

def run_diagnostics(install_dir: str, port: int) -> Dict[str, any]:
    """
    Run diagnostic checks for NCSI Resolver installation.

    Args:
        install_dir: Target installation directory
        port: Port to be used for NCSI server

    Returns:
        Dict containing diagnostic results and recommendations
    """
    print("\n" + "=" * 60)
    print("NCSI Resolver - Installation Diagnostics")
    print("=" * 60 + "\n")

    results = {
        'passed': [],
        'failed': [],
        'warnings': [],
        'info': []
    }

    # Check 1: Python version
    print("[1/9] Checking Python version...")
    python_version = sys.version_info
    if python_version >= (3, 8):
        results['passed'].append(f"[OK] Python {python_version.major}.{python_version.minor}.{python_version.micro} (meets requirement >= 3.8)")
        print(f"  [OK] Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        results['failed'].append(f"[FAIL] Python {python_version.major}.{python_version.minor} is too old (need 3.8+)")
        print(f"  [FAIL] Python version too old: {python_version.major}.{python_version.minor}")
        print(f"         Install Python 3.8+ from https://www.python.org/downloads/")

    # Check 2: Python executable location
    print(f"\n[2/9] Checking Python executable...")
    python_exe = sys.executable
    results['info'].append(f"Python executable: {python_exe}")
    print(f"  [INFO] Location: {python_exe}")

    # Check 3: Required Python modules
    print(f"\n[3/9] Checking required Python modules...")
    required_modules = ['http.server', 'socket', 'subprocess', 'ctypes', 'winreg']
    missing_modules = []
    for module in required_modules:
        try:
            __import__(module)
            results['passed'].append(f"[OK] Module '{module}' available")
        except ImportError:
            missing_modules.append(module)
            results['failed'].append(f"[FAIL] Module '{module}' missing")

    if missing_modules:
        print(f"  [FAIL] Missing modules: {', '.join(missing_modules)}")
    else:
        print(f"  [OK] All required modules available")

    # Check 4: Admin privileges
    print(f"\n[4/9] Checking administrator privileges...")
    if is_admin():
        results['passed'].append("[OK] Running with administrator privileges")
        print(f"  [OK] Administrator privileges: Yes")
    else:
        results['failed'].append("[FAIL] Not running as administrator")
        print(f"  [FAIL] Administrator privileges: No")
        print(f"         Right-click and select 'Run as administrator'")

    # Check 5: Port availability
    print(f"\n[5/9] Checking port {port} availability...")
    import socket
    try:
        test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        test_socket.bind(('0.0.0.0', port))
        test_socket.close()
        results['passed'].append(f"[OK] Port {port} is available")
        print(f"  [OK] Port {port} is available")
    except OSError as e:
        results['failed'].append(f"[FAIL] Port {port} is in use or blocked")
        print(f"  [FAIL] Port {port} is not available")
        print(f"     Try using a different port with --port=8080")
        if port == 80:
            print(f"     Port 80 may be used by IIS, Apache, or other web servers")

    # Check 6: Installation directory
    print(f"\n[6/9] Checking installation directory...")
    try:
        install_path = Path(install_dir)
        if install_path.exists():
            results['warnings'].append(f"[WARN] Installation directory already exists: {install_dir}")
            print(f"  [WARN] Directory exists: {install_dir}")
            print(f"     Existing installation will be updated")
        else:
            # Try to create parent directory to test permissions
            parent = install_path.parent
            if parent.exists():
                results['passed'].append(f"[OK] Can access parent directory: {parent}")
                print(f"  [OK] Parent directory accessible: {parent}")
            else:
                results['warnings'].append(f"[WARN] Parent directory does not exist: {parent}")
                print(f"  [WARN] Parent directory does not exist: {parent}")
    except Exception as e:
        results['failed'].append(f"[FAIL] Cannot access installation directory: {e}")
        print(f"  [FAIL] Error: {e}")

    # Check 7: NSSM availability
    print(f"\n[7/9] Checking for NSSM (service manager)...")
    try:
        if 'get_nssm_path' in globals():
            nssm_path = get_nssm_path()
            if nssm_path and Path(nssm_path).exists():
                results['passed'].append(f"[OK] NSSM found: {nssm_path}")
                print(f"  [OK] NSSM available: {nssm_path}")
            else:
                results['warnings'].append("[WARN] NSSM not found (will be downloaded)")
                print(f"  [INFO] NSSM will be downloaded during installation")
        else:
            results['info'].append("Cannot check NSSM (function not available)")
            print(f"  [INFO] NSSM check skipped")
    except Exception as e:
        results['warnings'].append(f"[WARN] NSSM check failed: {e}")
        print(f"  [WARN] Could not check NSSM: {e}")

    # Check 8: Firewall (informational)
    print(f"\n[8/9] Checking Windows Firewall...")
    try:
        fw_result = subprocess.run(
            ['netsh', 'advfirewall', 'show', 'currentprofile'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if fw_result.returncode == 0 and 'State' in fw_result.stdout:
            if 'ON' in fw_result.stdout:
                results['info'].append("Windows Firewall is active")
                print(f"  [INFO] Windows Firewall is ON (installer will create rule)")
            else:
                results['info'].append("Windows Firewall is disabled")
                print(f"  [INFO] Windows Firewall is OFF")
        else:
            results['info'].append("Could not determine firewall status")
            print(f"  [INFO] Firewall status: Unknown")
    except Exception:
        results['info'].append("Firewall check skipped")
        print(f"  [INFO] Firewall check skipped")

    # Check 9: Existing installation
    print(f"\n[9/9] Checking for existing installation...")
    try:
        if 'check_service_status' in globals():
            service_status = check_service_status()
            if service_status.get('installed'):
                results['warnings'].append("[WARN] NCSI Resolver service is already installed")
                print(f"  [WARN] Service already installed")
                if service_status.get('running'):
                    print(f"     Service is currently running")
                else:
                    print(f"     Service is installed but not running")
                print(f"     Installation will update the existing service")
            else:
                results['passed'].append("[OK] No existing service installation found")
                print(f"  [OK] No existing installation")
        else:
            results['info'].append("Cannot check existing service")
            print(f"  [INFO] Service check skipped")
    except Exception as e:
        results['info'].append(f"Service check failed: {e}")
        print(f"  [INFO] Could not check for existing service")

    # Summary
    print("\n" + "=" * 60)
    print("Diagnostic Summary")
    print("=" * 60)

    passed_count = len(results['passed'])
    failed_count = len(results['failed'])
    warning_count = len(results['warnings'])

    print(f"\n[OK]   Passed:   {passed_count}")
    print(f"[FAIL] Failed:   {failed_count}")
    print(f"[WARN] Warnings: {warning_count}")

    if failed_count == 0:
        print("\n[SUCCESS] All checks passed! Ready to install.")
        print("          Run: python installer.py --install")
    elif failed_count <= 2:
        print("\n[WARN] Some issues detected but may still work.")
        print("       Review failed checks above and try installation.")
    else:
        print("\n[ERROR] Multiple issues detected. Please resolve them first.")
        print("        Review failed checks above before installing.")

    print("\n" + "=" * 60 + "\n")

    return results

def display_banner(show_banner: bool = True):
    """
    Display the NCSI Resolver ASCII banner.
    
    Args:
        show_banner: Whether to show the banner
    """
    global _banner_displayed
    
    # Skip if banner suppressed or already displayed
    if not show_banner or _banner_displayed:
        return
        
    banner = r"""
 _   _  ___ ___ ___  ___                _             
| \ | |/ __/ __|_ _|| _ \ ___  ___  ___| | __ _____  __
|  \| | (__\_ \ | | |   // -_)(_-< / _ \ \_\ V / -_)| _|
|_|\__|\___/___|___||_|_\\___||__/ \___/\__|\_/\____|_|                                                             
    Windows Network Connectivity Status Indicator Resolver
    """
    print(banner)
    print("\nThis installer will set up the NCSI Resolver to fix Windows 'No Internet' issues.\n")
    
    # Set flag to indicate banner has been displayed
    _banner_displayed = True

def main():
    """Main entry point when running as a script."""
    global _banner_displayed
    
    parser = argparse.ArgumentParser(description=__description__)
    
    # Add version action (uses version.py if available)
    if 'get_version_string' in globals():
        parser.add_argument('--version', action='version', 
                           version=get_version_string("installer"))
    else:
        # Fallback if get_version_string is not available
        parser.add_argument('--version', action='version', 
                           version=f'{__description__} v{__version__}')
    
    # Define command actions
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--install", action="store_true", help="Install NCSI Resolver")
    action_group.add_argument("--uninstall", action="store_true", help="Uninstall NCSI Resolver")
    action_group.add_argument("--check", action="store_true", help="Check installation status")
    action_group.add_argument("--status", action="store_true", help="Alias for --check")
    action_group.add_argument("--diagnose", action="store_true", help="Run diagnostic checks without installing")
    
    # Additional options
    parser.add_argument("--install-dir", default=DEFAULT_INSTALL_DIR, help=f"Installation directory (default: {DEFAULT_INSTALL_DIR})")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to use for the NCSI server (default: {DEFAULT_PORT})")
    parser.add_argument("--quick", action="store_true", help="Quick mode (skip confirmations)")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-v", "--verbose", action="count", default=0, help="Increase verbosity (can be used multiple times)")
    parser.add_argument("--nobanner", action="store_true", help="Suppress the banner display")
    
    args = parser.parse_args()
    
    # If --status is used, treat it as --check
    if args.status:
        args.check = True
    
    # Configure logging based on verbosity
    if args.debug:
        logger.setLevel(logging.DEBUG)
    elif args.verbose > 0:
        # Set verbosity level based on number of -v flags
        verbosity_levels = {
            1: logging.INFO,
            2: logging.WARNING,
            3: logging.DEBUG
        }
        level = verbosity_levels.get(args.verbose, logging.DEBUG)
        logger.setLevel(level)
    
    # Set banner display flag based on argument
    _banner_displayed = args.nobanner
    
    # Display ASCII banner (unless suppressed)
    display_banner(not args.nobanner)
    
    # Perform requested action
    if args.install:
        success = perform_full_installation(args.install_dir, args.port, args.quick)
        if not success:
            sys.exit(1)
    
    elif args.uninstall:
        success = perform_uninstallation(args.quick)
        if not success:
            sys.exit(1)
    
    elif args.check:
        # Check current status
        if 'check_configuration' in globals() and 'check_service_status' in globals():
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
                
                # Extract port from registry if present
                if 'ActiveWebProbeHost' in config['registry_settings']:
                    probe_host = config['registry_settings']['ActiveWebProbeHost']
                    # Check if port is specified in host (e.g., "192.168.1.1:8080")
                    port = 80
                    if ':' in probe_host:
                        host_parts = probe_host.split(':')
                        if len(host_parts) > 1 and host_parts[1].isdigit():
                            port = int(host_parts[1])
                            print(f"  Port: {port}")
            
            # Print hosts file redirect
            if 'hosts_file_redirect' in config:
                print(f"\nHosts File Redirect: {config.get('hosts_file_redirect') or 'Not set'}")
            
            # Print service status
            print(f"\nService Status: {service_status.get('status', 'Unknown')}")
            print(f"Service Installed: {'Yes' if service_status.get('installed') else 'No'}")
            print(f"Service Running: {'Yes' if service_status.get('running') else 'No'}")
            
            # Check if service is accessible
            server_accessible = False
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                
                # Try to determine the port to test
                try:
                    test_port = port  # Use the port extracted from registry, if available
                except NameError:
                    test_port = 80    # Default to port 80 if not specified
                
                # Try to connect to localhost on the appropriate port
                s.connect(("127.0.0.1", test_port))
                s.close()
                server_accessible = True
                print(f"\nServer Connectivity: OK (Accessible on port {test_port})")
            except:
                if 'test_port' in locals():
                    print(f"\nServer Connectivity: FAILED (Not accessible on port {test_port})")
                else:
                    print("\nServer Connectivity: FAILED (Port unknown)")
                
                # Try to determine why it's not accessible
                if service_status.get("running", False):
                    # Service is running but can't connect - could be port conflict
                    print("  Possible cause: Port conflict with another application")
                    print("  Try reinstalling with a different port (e.g., --port=8080)")
                else:
                    # Service isn't running
                    print("  Possible cause: Service is not running")
                    print("  Try starting the service with: net start NCSIResolver")
            
            # Overall status - more accurate based on all factors
            if config.get("is_configured") and service_status.get("running") and server_accessible:
                print("\nOverall Status: NCSI Resolver is fully operational")
            elif config.get("is_configured") and service_status.get("running") and not server_accessible:
                print("\nOverall Status: NCSI Resolver is partially operational (service running but port may be blocked)")
            elif config.get("is_configured") and service_status.get("installed") and not service_status.get("running"):
                print("\nOverall Status: NCSI Resolver is installed but not running")
            elif config.get("is_configured"):
                print("\nOverall Status: System is configured but service is not installed")
            else:
                print("\nOverall Status: NCSI Resolver is not installed")
        else:
            # Limited functionality if modules not available
            print("\nNCSI Resolver Status Check:")
            print("-" * 50)
            print("Status check functionality is limited due to missing modules.")
            
            # Try to check service status if available
            if 'check_service_status' in globals():
                service_status = check_service_status()
                print(f"\nService Status: {service_status.get('status', 'Unknown')}")
                print(f"Service Installed: {'Yes' if service_status.get('installed') else 'No'}")
                print(f"Service Running: {'Yes' if service_status.get('running') else 'No'}")
            else:
                print("\nCannot check service status. Module not available.")

    elif args.diagnose:
        # Run diagnostic checks
        results = run_diagnostics(args.install_dir, args.port)

        # Exit with appropriate code based on results
        if len(results['failed']) > 0:
            sys.exit(1)

if __name__ == "__main__":
    main()