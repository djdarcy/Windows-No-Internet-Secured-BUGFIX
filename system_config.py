#!/usr/bin/env python3
"""
Windows System Configuration Utilities for NCSI Resolver

This module provides functions to configure Windows system settings required for
the NCSI Resolver to work properly, including registry edits and hosts file modifications.
"""

import ctypes
import logging
import os
import platform
import re
import subprocess
import sys
import winreg
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from version import get_version_info
    
    # Get version information
    __version_info__ = get_version_info("system_config")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.5.0"
    __description__ = "Windows System Configuration for NCSI Resolver"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('system_config')

# Constants
HOSTS_FILE_PATH = r"C:\Windows\System32\drivers\etc\hosts"
NCSI_REGISTRY_KEY = r"SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet"
DEFAULT_NCSI_HOST = "www.msftconnecttest.com"
DEFAULT_NCSI_IP = "127.0.0.1"
TIMEOUT = 10

def is_admin() -> bool:
    """
    Check if the current process has administrative privileges.
    
    Returns:
        bool: True if running with admin privileges, False otherwise
    """
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def run_as_admin(script_path: str, *args) -> None:
    """
    Restart the current script with administrative privileges.
    
    Args:
        script_path: Path to the script to run
        *args: Additional arguments to pass
    """
    if not is_admin():
        logger.info("Requesting administrative privileges...")
        
        # Convert to a list for easier handling
        arg_list = list(args)
        
        # Prepare the arguments
        if script_path.endswith('.py'):
            # If it's a .py file, we need to call it with python
            cmd = [sys.executable, script_path] + arg_list
        else:
            # Otherwise assume it's executable
            cmd = [script_path] + arg_list
        
        try:
            # Request elevation via ShellExecute
            ctypes.windll.shell32.ShellExecuteW(
                None, "runas", cmd[0], ' '.join(f'"{arg}"' for arg in cmd[1:]), None, 1
            )
            sys.exit(0)
        except Exception as e:
            logger.error(f"Failed to get admin privileges: {e}")
            sys.exit(1)

def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of the machine.
    
    Returns:
        str: The local IP address, or None if it can't be determined
    """
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {e}")
        return None

def update_hosts_file(hostname: str = DEFAULT_NCSI_HOST, ip: str = None, backup: bool = True) -> bool:
    """
    Update the Windows hosts file to redirect NCSI requests.
    
    Args:
        hostname: The hostname to redirect
        ip: The IP address to redirect to (default: local IP)
        backup: Whether to create a backup of the hosts file
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update hosts file")
        return False
    
    # Use local IP if not specified
    if ip is None:
        ip = get_local_ip() or DEFAULT_NCSI_IP
    
    hosts_path = Path(HOSTS_FILE_PATH)
    
    # Check if hosts file exists
    if not hosts_path.exists():
        logger.error(f"Hosts file not found at {HOSTS_FILE_PATH}")
        return False
    
    try:
        # Read current hosts file
        with open(hosts_path, 'r') as f:
            hosts_content = f.read()
        
        # Create backup if requested
        if backup:
            backup_path = hosts_path.with_suffix('.bak')
            with open(backup_path, 'w') as f:
                f.write(hosts_content)
            logger.info(f"Created hosts file backup at {backup_path}")
        
        # Check if the hostname is already in the hosts file
        pattern = re.compile(rf'^\s*\d+\.\d+\.\d+\.\d+\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        match = pattern.search(hosts_content)
        
        if match:
            # Update existing entry
            hosts_content = pattern.sub(f"{ip} {hostname}", hosts_content)
            logger.info(f"Updated hosts file entry for {hostname} to {ip}")
        else:
            # Add new entry
            if not hosts_content.endswith('\n'):
                hosts_content += '\n'
            hosts_content += f"{ip} {hostname}\n"
            logger.info(f"Added new hosts file entry for {hostname} to {ip}")
        
        # Write updated hosts file
        with open(hosts_path, 'w') as f:
            f.write(hosts_content)
        
        return True
    
    except Exception as e:
        logger.error(f"Error updating hosts file: {e}")
        return False

def update_ncsi_registry(probe_host: str = None, probe_path: str = "/ncsi.txt") -> bool:
    """
    Update the Windows registry for NCSI settings.
    
    Args:
        probe_host: The hostname to use for NCSI probes (default: local IP)
        probe_path: The path to use for NCSI probes
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to update registry")
        return False
    
    # Use local IP if not specified
    if probe_host is None:
        probe_host = get_local_ip() or DEFAULT_NCSI_IP
    
    try:
        # Open the registry key
        reg_key = winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_WRITE
        )
        
        # Update registry values
        winreg.SetValueEx(reg_key, "ActiveWebProbeHost", 0, winreg.REG_SZ, probe_host)
        winreg.SetValueEx(reg_key, "ActiveWebProbePath", 0, winreg.REG_SZ, probe_path)
        
        # Close the key
        winreg.CloseKey(reg_key)
        
        logger.info(f"Updated NCSI registry settings to use {probe_host}{probe_path}")
        return True
    
    except Exception as e:
        logger.error(f"Error updating registry: {e}")
        return False

def check_ncsi_registry() -> Dict[str, str]:
    """
    Check the current NCSI registry settings.
    
    Returns:
        Dict[str, str]: A dictionary of current settings
    """
    result = {}
    
    try:
        # Open the registry key
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_READ
        )
        
        # Read registry values
        try:
            result["ActiveWebProbeHost"] = winreg.QueryValueEx(reg_key, "ActiveWebProbeHost")[0]
        except FileNotFoundError:
            result["ActiveWebProbeHost"] = "default (not set)"
        
        try:
            result["ActiveWebProbePath"] = winreg.QueryValueEx(reg_key, "ActiveWebProbePath")[0]
        except FileNotFoundError:
            result["ActiveWebProbePath"] = "default (not set)"
        
        # Close the key
        winreg.CloseKey(reg_key)
        
    except Exception as e:
        logger.error(f"Error reading registry: {e}")
    
    return result

def check_hosts_file(hostname: str = DEFAULT_NCSI_HOST) -> Optional[str]:
    """
    Check if the hostname is redirected in the hosts file.
    
    Args:
        hostname: The hostname to check
        
    Returns:
        Optional[str]: The IP address if found, None otherwise
    """
    try:
        with open(HOSTS_FILE_PATH, 'r') as f:
            hosts_content = f.read()
        
        # Look for the hostname in the hosts file
        pattern = re.compile(rf'^\s*(\d+\.\d+\.\d+\.\d+)\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        match = pattern.search(hosts_content)
        
        if match:
            return match.group(1)
        
        return None
    
    except Exception as e:
        logger.error(f"Error reading hosts file: {e}")
        return None

def restart_network_service() -> bool:
    """
    Restart the Network Location Awareness (NLA) service to apply changes.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to restart network service")
        return False
    
    try:
        # Try restart instead of stop/start
        logger.info("Attempting to restart Network Location Awareness service...")
        restart_result = subprocess.run(
            ["net", "stop", "NlaSvc", "/y"], 
            check=False,  # Don't raise exception if command fails
            capture_output=True,
            timeout=TIMEOUT
        )
        
        if restart_result.returncode != 0:
            # If direct stop fails, try SC command to restart
            logger.info("Direct stop failed, trying SC to restart service...")
            sc_result = subprocess.run(
                ["sc", "stop", "NlaSvc"], 
                check=False,
                capture_output=True,
                timeout=TIMEOUT
            )
            
            # Even if SC fails, continue since we'll still flush DNS and renew IP
            if sc_result.returncode != 0:
                logger.warning("Could not stop NlaSvc service, changes may require a system restart to take effect")
        
        # Try to start the service again
        start_result = subprocess.run(
            ["net", "start", "NlaSvc"],
            check=False,
            capture_output=True,
            timeout=TIMEOUT
        )
        
        if start_result.returncode == 0:
            logger.info("Successfully restarted Network Location Awareness service")
        else:
            logger.warning("Could not start NlaSvc service, it may start automatically or require a system restart")
        
        # Return true even if we couldn't restart the service
        # The registry changes will still take effect eventually
        return True
    
    except Exception as e:
        logger.error(f"Error managing network service: {e}")
        # Continue with other network operations
        return False

def detect_wifi_adapters() -> List[str]:
    """
    Detect Wi-Fi adapters on the system.
    
    Returns:
        List[str]: List of Wi-Fi adapter names, or empty list if none found
    """
    try:
        # Method 1: Try using netsh (Windows-specific)
        result = subprocess.run(
            ["netsh", "wlan", "show", "interfaces"], 
            check=False,  # Don't raise exception if command fails
            capture_output=True, 
            text=True
        )
        
        # Extract adapter names
        adapters = []
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                if "Name" in line and ":" in line:
                    adapters.append(line.split(":", 1)[1].strip())
            
            if adapters:
                return adapters
        
        # Method 2: Try using WMI for more detailed information
        try:
            import wmi
            c = wmi.WMI()
            wifi_adapters = []
            
            # Look for wireless adapters
            for nic in c.Win32_NetworkAdapter():
                # Check various properties that might indicate wireless
                if any(wifi_term.lower() in nic.Name.lower() for wifi_term in 
                      ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                    wifi_adapters.append(nic.Name)
            
            return wifi_adapters
            
        except ImportError:
            # WMI module not available, try one more approach
            pass
            
        # Method 3: Try using ipconfig
        result = subprocess.run(
            ["ipconfig", "/all"], 
            check=False,
            capture_output=True, 
            text=True
        )
        
        if result.returncode == 0:
            wifi_sections = []
            current_section = []
            in_section = False
            
            for line in result.stdout.splitlines():
                if "adapter" in line.lower() and ":" in line:
                    if in_section and any(wifi_term.lower() in "\n".join(current_section).lower() 
                                         for wifi_term in ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                        wifi_name = current_section[0].split(":")[0].strip()
                        wifi_sections.append(wifi_name)
                    
                    current_section = [line]
                    in_section = True
                elif in_section:
                    current_section.append(line)
            
            # Check the last section
            if in_section and any(wifi_term.lower() in "\n".join(current_section).lower() 
                                for wifi_term in ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                wifi_name = current_section[0].split(":")[0].strip()
                wifi_sections.append(wifi_name)
            
            return wifi_sections
    
    except Exception as e:
        logger.warning(f"Error detecting Wi-Fi adapters: {e}")
    
    return []

def configure_wifi_adapter(skip_if_no_wifi: bool = True) -> bool:
    """
    Configure Wi-Fi adapter for optimal stability.
    
    Args:
        skip_if_no_wifi: Whether to skip silently if no Wi-Fi adapter is found
        
    Returns:
        bool: True if successful or skipped, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to configure network adapter")
        return False
    
    try:
        # Get list of wireless adapters using our detection function
        adapters = detect_wifi_adapters()
        
        if not adapters:
            if skip_if_no_wifi:
                logger.info("No wireless adapters found. Skipping Wi-Fi optimization.")
                return True  # Return success since we're skipping
            else:
                logger.warning("No wireless adapters found")
                return False
        
        logger.info(f"Found {len(adapters)} wireless adapters: {', '.join(adapters)}")
        
        # Configure each adapter
        for adapter in adapters:
            # Check if Intel adapter (common troublemakers)
            if "intel" in adapter.lower():
                logger.info(f"Configuring Intel adapter: {adapter}")
                
                # Lower the roaming aggressiveness
                subprocess.run([
                    "netsh", "wlan", "set", "profileparameter", 
                    f'name="{adapter}"', "roaming=1"
                ], check=False)
                
                # Prefer 5GHz band
                subprocess.run([
                    "netsh", "wlan", "set", "profileparameter", 
                    f'name="{adapter}"', "preferredband=5"
                ], check=False)
            
            # General settings for any adapter
            # Disable power saving
            try:
                subprocess.run([
                    "powercfg", "-setacvalueindex", "scheme_current", 
                    "19cbb8fa-5279-450e-9fac-8a3d5fedd0c1", 
                    "12bbebe6-58d6-4636-95bb-3217ef867c1a", "0"
                ], check=False)
                
                # Apply changes
                subprocess.run(["powercfg", "-setactive", "scheme_current"], check=False)
                
                logger.info(f"Configured power settings for {adapter}")
            except Exception as e:
                logger.warning(f"Failed to configure power settings: {e}")
        
        return True
    
    except Exception as e:
        logger.error(f"Error configuring Wi-Fi adapter: {e}")
        return False

def refresh_network() -> bool:
    """
    Refresh network settings and DNS cache.
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Flush DNS cache
        subprocess.run(["ipconfig", "/flushdns"], check=True, capture_output=True)
        logger.info("Flushed DNS cache")
        
        # Release and renew IP
        subprocess.run(["ipconfig", "/release"], check=False, capture_output=True)
        subprocess.run(["ipconfig", "/renew"], check=False, capture_output=True)
        logger.info("Released and renewed IP address")
        
        return True
    
    except Exception as e:
        logger.error(f"Error refreshing network: {e}")
        return False

def configure_system(probe_host: str = None, 
                     probe_path: str = "/ncsi.txt",
                     restart_services: bool = True,
                     configure_wifi: bool = True) -> bool:
    """
    Configure all system settings for NCSI Resolver.
    
    Args:
        probe_host: The hostname to use for NCSI probes (default: local IP)
        probe_path: The path to use for NCSI probes
        restart_services: Whether to restart network services
        configure_wifi: Whether to attempt Wi-Fi adapter configuration
        
    Returns:
        bool: True if all operations successful, False otherwise
    """
    if not is_admin():
        logger.warning("Administrative privileges required to configure system")
        return False
    
    # Use local IP if not specified
    if probe_host is None:
        probe_host = get_local_ip() or DEFAULT_NCSI_IP
    
    success = True
    
    # Update hosts file
    if not update_hosts_file(DEFAULT_NCSI_HOST, probe_host):
        success = False
    
    # Update registry
    if not update_ncsi_registry(probe_host, probe_path):
        success = False
    
    # Configure Wi-Fi adapter only if requested
    if configure_wifi:
        if not configure_wifi_adapter(skip_if_no_wifi=True):
            logger.warning("Failed to configure Wi-Fi adapter, continuing with other operations")
    
    # Restart services if requested
    if restart_services:
        if not restart_network_service():
            success = False
        
        if not refresh_network():
            logger.warning("Failed to refresh network, continuing with other operations")
    
    # Print summary of current configuration
    if success:
        logger.info("System configuration successful")
        
        # Show current settings
        registry_settings = check_ncsi_registry()
        hosts_redirect = check_hosts_file(DEFAULT_NCSI_HOST)
        
        logger.info("Current NCSI configuration:")
        logger.info(f"  Registry settings:")
        for key, value in registry_settings.items():
            logger.info(f"    {key}: {value}")
        
        logger.info(f"  Hosts file redirect: {DEFAULT_NCSI_HOST} -> {hosts_redirect or 'not set'}")
    else:
        logger.error("System configuration failed")
    
    return success

def check_configuration() -> Dict[str, Union[str, bool]]:
    """
    Check the current NCSI configuration status.
    
    Returns:
        Dict: A dictionary with configuration status
    """
    result = {
        "registry_settings": check_ncsi_registry(),
        "hosts_file_redirect": check_hosts_file(DEFAULT_NCSI_HOST),
        "is_configured": False
    }
    
    # Check if properly configured
    if (result["registry_settings"].get("ActiveWebProbeHost") != "default (not set)" and
        result["hosts_file_redirect"] is not None):
        result["is_configured"] = True
    
    return result

def reset_configuration() -> bool:
    """
    Reset NCSI configuration to default Windows settings.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.warning("Administrative privileges required to reset configuration")
        return False
    
    success = True
    
    # Try to restore hosts file from backup
    hosts_path = Path(HOSTS_FILE_PATH)
    backup_path = hosts_path.with_suffix('.bak')
    
    if backup_path.exists():
        try:
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            
            with open(hosts_path, 'w') as f:
                f.write(backup_content)
            
            logger.info("Restored hosts file from backup")
        except Exception as e:
            logger.error(f"Failed to restore hosts file from backup: {e}")
            success = False
    else:
        # No backup, try to remove the NCSI entry
        try:
            with open(hosts_path, 'r') as f:
                hosts_content = f.read()
            
            # Remove the NCSI host entry
            pattern = re.compile(rf'^\s*\d+\.\d+\.\d+\.\d+\s+{re.escape(DEFAULT_NCSI_HOST)}(?:\s|$).*$\n?', re.MULTILINE)
            hosts_content = pattern.sub('', hosts_content)
            
            with open(hosts_path, 'w') as f:
                f.write(hosts_content)
            
            logger.info(f"Removed {DEFAULT_NCSI_HOST} entry from hosts file")
        except Exception as e:
            logger.error(f"Failed to update hosts file: {e}")
            success = False
    
    # Reset registry settings
    try:
        # Open the registry key
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            NCSI_REGISTRY_KEY,
            0,
            winreg.KEY_WRITE
        )
        
        # Delete custom values to restore defaults
        try:
            winreg.DeleteValue(reg_key, "ActiveWebProbeHost")
            logger.info("Reset ActiveWebProbeHost registry setting")
        except FileNotFoundError:
            pass
        
        try:
            winreg.DeleteValue(reg_key, "ActiveWebProbePath")
            logger.info("Reset ActiveWebProbePath registry setting")
        except FileNotFoundError:
            pass
        
        # Close the key
        winreg.CloseKey(reg_key)
    except Exception as e:
        logger.error(f"Failed to reset registry settings: {e}")
        success = False
    
    # Restart network services
    if not restart_network_service():
        success = False
    
    if not refresh_network():
        logger.warning("Failed to refresh network")
    
    return success

def main():
    """Main entry point when running as a script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Configure Windows system for NCSI Resolver")
    parser.add_argument("--action", choices=["configure", "check", "reset"], default="check",
                       help="Action to perform: configure, check or reset (default: check)")
    parser.add_argument("--host", help="Host address to use (default: auto-detect)")
    parser.add_argument("--path", default="/ncsi.txt", help="Path to use for NCSI probe")
    parser.add_argument("--no-restart", action="store_true", help="Don't restart network services")
    parser.add_argument("--no-wifi", action="store_true", help="Skip Wi-Fi adapter configuration")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Check admin privileges
    if args.action in ["configure", "reset"] and not is_admin():
        logger.info("Administrative privileges required, requesting elevation...")
        run_as_admin(
            sys.argv[0],
            f"--action={args.action}",
            f"--host={args.host}" if args.host else "",
            f"--path={args.path}",
            "--no-restart" if args.no_restart else "",
            "--no-wifi" if args.no_wifi else "",
            "--debug" if args.debug else ""
        )
        return
    
    # Perform requested action
    if args.action == "configure":
        configure_system(
            probe_host=args.host,
            probe_path=args.path,
            restart_services=not args.no_restart,
            configure_wifi=not args.no_wifi
        )
    elif args.action == "check":
        config = check_configuration()
        
        print("\nNCSI Configuration Status:")
        print("-------------------------")
        print(f"Configuration Status: {'Configured' if config['is_configured'] else 'Not Configured'}")
        print("\nRegistry Settings:")
        for key, value in config["registry_settings"].items():
            print(f"  {key}: {value}")
        
        print(f"\nHosts File Redirect: {DEFAULT_NCSI_HOST} -> {config['hosts_file_redirect'] or 'not set'}")
    elif args.action == "reset":
        reset_configuration()

if __name__ == "__main__":
    main()