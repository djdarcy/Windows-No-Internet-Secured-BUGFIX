#!/usr/bin/env python3
"""
NCSI Resolver Firewall Helper

This module provides utilities to manage Windows Firewall rules for the NCSI Resolver.
"""

import logging
import os
import subprocess
import sys
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('firewall_helper')

# Constants
RULE_NAME = "NCSI Resolver"
RULE_DESCRIPTION = "Allow connections to NCSI Resolver service"

def is_admin() -> bool:
    """
    Check if the current process has administrative privileges.
    
    Returns:
        bool: True if running with admin privileges, False otherwise
    """
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def check_firewall_rule_exists(port: int = 80) -> bool:
    """
    Check if a firewall rule already exists for the NCSI Resolver.
    
    Args:
        port: Port number to check
        
    Returns:
        bool: True if rule exists, False otherwise
    """
    try:
        # Run netsh command to check for existing rule
        cmd = [
            "netsh", "advfirewall", "firewall", "show", "rule", 
            f"name={RULE_NAME}", "verbose"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Check if the rule exists and has the correct port
        rule_exists = RULE_NAME in result.stdout
        correct_port = f"LocalPort:    {port}" in result.stdout
        
        return rule_exists and correct_port
    except Exception as e:
        logger.error(f"Error checking firewall rule: {e}")
        return False

def add_firewall_rule(port: int, application_path: Optional[str] = None) -> bool:
    """
    Add a firewall rule to allow connections to the NCSI Resolver.
    
    Args:
        port: Port number to allow
        application_path: Optional path to the application executable
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to configure firewall")
        return False
    
    try:
        # First check if the rule already exists
        if check_firewall_rule_exists(port):
            logger.info(f"Firewall rule for port {port} already exists")
            return True
        
        # Prepare the command to add a firewall rule
        cmd = [
            "netsh", "advfirewall", "firewall", "add", "rule",
            f"name={RULE_NAME}",
            "dir=in",
            "action=allow",
            f"protocol=TCP",
            f"localport={port}",
            f"description={RULE_DESCRIPTION}"
        ]
        
        # Add application path if provided
        if application_path and os.path.exists(application_path):
            cmd.append(f"program={application_path}")
        
        # Execute the command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info(f"Successfully added firewall rule for port {port}")
            return True
        else:
            logger.error(f"Failed to add firewall rule: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error adding firewall rule: {e}")
        return False

def update_firewall_rule(old_port: int, new_port: int) -> bool:
    """
    Update an existing firewall rule with a new port number.
    
    Args:
        old_port: Existing port number
        new_port: New port number
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to configure firewall")
        return False
    
    try:
        # Remove existing rule if it exists
        if check_firewall_rule_exists(old_port):
            remove_firewall_rule()
        
        # Add new rule
        return add_firewall_rule(new_port)
    except Exception as e:
        logger.error(f"Error updating firewall rule: {e}")
        return False

def remove_firewall_rule() -> bool:
    """
    Remove the firewall rule for the NCSI Resolver.
    
    Returns:
        bool: True if successful, False otherwise
    """
    if not is_admin():
        logger.error("Administrative privileges required to configure firewall")
        return False
    
    try:
        # Run netsh command to remove the rule
        cmd = [
            "netsh", "advfirewall", "firewall", "delete", "rule",
            f"name={RULE_NAME}"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            logger.info("Successfully removed firewall rule")
            return True
        else:
            logger.error(f"Failed to remove firewall rule: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Error removing firewall rule: {e}")
        return False

def check_port_blocking(host: str = "127.0.0.1", port: int = 80) -> Tuple[bool, str]:
    """
    Check if a port is being blocked by the firewall.
    
    Args:
        host: Host address to check
        port: Port number to check
        
    Returns:
        Tuple[bool, str]: (is_blocked, reason)
    """
    try:
        # Try using netsh to test port accessibility
        cmd = [
            "netsh", "advfirewall", "firewall", "show", "rule", 
            "name=all", "dir=in", "verbose"
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Look for any rule that might be blocking the port
        for line in result.stdout.split('\n'):
            if "Block" in line and f"LocalPort:    {port}" in line:
                return True, f"Found blocking rule: {line}"
        
        # If no explicit blocking rule found, test with a socket connection
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        
        try:
            s.connect((host, port))
            s.close()
            return False, "Port is accessible"
        except socket.error as e:
            return True, f"Connection failed: {e}"
            
    except Exception as e:
        logger.error(f"Error checking port blocking: {e}")
        return True, f"Error checking: {e}"

def main():
    """Command-line interface for firewall configuration."""
    import argparse
    
    parser = argparse.ArgumentParser(description="NCSI Resolver Firewall Helper")
    action_group = parser.add_mutually_exclusive_group(required=True)
    action_group.add_argument("--add", action="store_true", help="Add firewall rule")
    action_group.add_argument("--remove", action="store_true", help="Remove firewall rule")
    action_group.add_argument("--check", action="store_true", help="Check if rule exists")
    action_group.add_argument("--update", action="store_true", help="Update rule to new port")
    action_group.add_argument("--test", action="store_true", help="Test if port is accessible")
    
    parser.add_argument("--port", type=int, default=80, help="Port number")
    parser.add_argument("--new-port", type=int, help="New port number (for update)")
    parser.add_argument("--app", help="Path to application executable")
    parser.add_argument("--host", default="127.0.0.1", help="Host to test (for test)")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Check admin privileges for operations that require them
    if (args.add or args.remove or args.update) and not is_admin():
        print("Administrative privileges required")
        return 1
    
    # Perform requested action
    if args.add:
        success = add_firewall_rule(args.port, args.app)
    elif args.remove:
        success = remove_firewall_rule()
    elif args.check:
        exists = check_firewall_rule_exists(args.port)
        print(f"Firewall rule for port {args.port}: {'EXISTS' if exists else 'NOT FOUND'}")
        return 0 if exists else 1
    elif args.update and args.new_port:
        success = update_firewall_rule(args.port, args.new_port)
    elif args.test:
        blocked, reason = check_port_blocking(args.host, args.port)
        print(f"Port {args.port} on {args.host}: {'BLOCKED' if blocked else 'ACCESSIBLE'}")
        print(f"Reason: {reason}")
        return 0 if not blocked else 1
    else:
        parser.print_help()
        return 1
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
