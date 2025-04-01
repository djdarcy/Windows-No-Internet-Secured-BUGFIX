#!/usr/bin/env python3
"""
NCSI Resolver Connectivity Test

This script tests connectivity to the NCSI Resolver service and helps diagnose issues.
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('test_connectivity')

def is_admin() -> bool:
    """Check if running with administrative privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def check_port_open(host: str, port: int, timeout: float = 2.0) -> Tuple[bool, str]:
    """
    Check if a port is open on the specified host.
    
    Args:
        host: Host address to check
        port: Port number to check
        timeout: Connection timeout in seconds
        
    Returns:
        Tuple[bool, str]: (is_open, reason)
    """
    try:
        # Create a socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(timeout)
        
        # Try to connect
        s.connect((host, port))
        s.close()
        return True, "Connection established successfully"
    except socket.timeout:
        return False, "Connection timed out"
    except socket.error as e:
        return False, f"Socket error: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def check_socket_state(port: int) -> Tuple[bool, str]:
    """
    Check the socket state on Windows.
    
    Args:
        port: Port number to check
        
    Returns:
        Tuple[bool, str]: (in_use, info)
    """
    try:
        # Run netstat to check port usage
        cmd = ["netstat", "-ano"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        # Look for the port in the output
        port_found = False
        pid = None
        state = None
        
        for line in result.stdout.split('\n'):
            if f":{port}" in line:
                port_found = True
                parts = line.split()
                if len(parts) >= 5:
                    state = parts[3] if len(parts) > 3 else "Unknown"
                    pid = parts[4] if len(parts) > 4 else "Unknown"
                break
        
        if port_found:
            # Try to get process name from PID
            process_name = "Unknown"
            if pid and pid.isdigit():
                try:
                    cmd = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
                    proc_result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    
                    if proc_result.stdout.strip():
                        # Parse CSV output
                        parts = proc_result.stdout.strip().split(',')
                        if len(parts) > 0:
                            process_name = parts[0].strip('"')
                except Exception:
                    pass
            
            return True, f"Port {port} is being used by {process_name} (PID {pid}), state: {state}"
        else:
            return False, f"Port {port} is not in use according to netstat"
    except Exception as e:
        return False, f"Error checking socket state: {e}"

def check_tcp_parameters() -> Dict[str, int]:
    """
    Check TCP parameters that might affect socket binding.
    
    Returns:
        Dict[str, int]: TCP parameters
    """
    params = {}
    
    try:
        # Check TCP TIME_WAIT parameter
        cmd = ["netsh", "int", "tcp", "show", "global"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        for line in result.stdout.split('\n'):
            if "Time Wait Delay" in line:
                parts = line.split(':')
                if len(parts) > 1:
                    params["time_wait_delay"] = int(parts[1].strip().split()[0])
            elif "Reuse Time Wait" in line:
                parts = line.split(':')
                if len(parts) > 1:
                    params["reuse_time_wait"] = 1 if "enabled" in parts[1].lower() else 0
    except Exception:
        pass
    
    return params

def check_firewall(port: int) -> Tuple[bool, str]:
    """
    Check if Windows Firewall is blocking the port.
    
    Args:
        port: Port number to check
        
    Returns:
        Tuple[bool, str]: (is_blocked, reason)
    """
    try:
        # Check if firewall helper is available
        try:
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from firewall_helper import check_port_blocking
            return check_port_blocking("127.0.0.1", port)
        except ImportError:
            # Fall back to netsh
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
            
            return False, "No blocking rules found"
    except Exception as e:
        return False, f"Error checking firewall: {e}"

def test_ncsi_connections(host: str = "127.0.0.1", port: int = 80) -> Dict[str, bool]:
    """
    Test NCSI connections to verify the service is working.
    
    Args:
        host: Host address to check
        port: Port number to check
        
    Returns:
        Dict[str, bool]: Connection test results
    """
    results = {
        "connecttest.txt": False,
        "ncsi.txt": False,
        "redirect": False
    }
    
    try:
        import http.client
        
        # Test connecttest.txt
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", "/connecttest.txt")
            response = conn.getresponse()
            data = response.read()
            
            if response.status == 200 and data == b"Microsoft Connect Test":
                results["connecttest.txt"] = True
            
            conn.close()
        except Exception:
            pass
        
        # Test ncsi.txt
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", "/ncsi.txt")
            response = conn.getresponse()
            data = response.read()
            
            if response.status == 200 and data == b"Microsoft Connect Test":
                results["ncsi.txt"] = True
            
            conn.close()
        except Exception:
            pass
        
        # Test redirect
        try:
            conn = http.client.HTTPConnection(host, port, timeout=2)
            conn.request("GET", "/redirect")
            response = conn.getresponse()
            
            if response.status == 200:
                results["redirect"] = True
            
            conn.close()
        except Exception:
            pass
    except Exception:
        pass
    
    return results

def check_service_status(service_name: str = "NCSIResolver") -> Dict[str, bool]:
    """
    Check if the service is running.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Dict[str, bool]: Service status information
    """
    status = {
        "exists": False,
        "running": False,
        "status": "Unknown"
    }
    
    try:
        # Check service status using sc
        cmd = ["sc", "query", service_name]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            status["exists"] = True
            
            if "RUNNING" in result.stdout:
                status["running"] = True
                status["status"] = "Running"
            elif "STOPPED" in result.stdout:
                status["status"] = "Stopped"
            elif "STARTING" in result.stdout:
                status["status"] = "Starting"
            elif "STOPPING" in result.stdout:
                status["status"] = "Stopping"
        else:
            status["status"] = "Service not found"
    except Exception:
        pass
    
    return status

def run_diagnostic_tests(host: str = "127.0.0.1", port: int = 80) -> Dict[str, any]:
    """
    Run a comprehensive set of diagnostic tests.
    
    Args:
        host: Host address to check
        port: Port number to check
        
    Returns:
        Dict[str, any]: Diagnostic test results
    """
    results = {
        "port_open": None,
        "socket_state": None,
        "firewall": None,
        "tcp_params": None,
        "service_status": None,
        "ncsi_tests": None
    }
    
    # Check if port is open
    is_open, reason = check_port_open(host, port)
    results["port_open"] = {
        "result": is_open,
        "details": reason
    }
    
    # Check socket state
    in_use, info = check_socket_state(port)
    results["socket_state"] = {
        "result": in_use,
        "details": info
    }
    
    # Check firewall
    is_blocked, reason = check_firewall(port)
    results["firewall"] = {
        "result": is_blocked,
        "details": reason
    }
    
    # Check TCP parameters
    results["tcp_params"] = check_tcp_parameters()
    
    # Check service status
    results["service_status"] = check_service_status()
    
    # Test NCSI connections
    results["ncsi_tests"] = test_ncsi_connections(host, port)
    
    return results

def main():
    """Command-line interface for connectivity testing."""
    parser = argparse.ArgumentParser(description="NCSI Resolver Connectivity Test")
    parser.add_argument("--host", default="127.0.0.1", help="Host to test")
    parser.add_argument("--port", type=int, default=80, help="Port to test")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--timeout", type=float, default=2.0, help="Connection timeout in seconds")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    print(f"Testing connectivity to {args.host}:{args.port}...")
    
    # Check admin privileges
    if not is_admin():
        print("Warning: Some tests may require administrative privileges.")
    
    # Run diagnostic tests
    results = run_diagnostic_tests(args.host, args.port)
    
    # Print results
    print("\nDiagnostic Test Results:")
    print("-" * 50)
    
    # Port open test
    port_open = results["port_open"]
    print(f"Port {args.port} Open: {'YES' if port_open['result'] else 'NO'}")
    print(f"  {port_open['details']}")
    
    # Socket state
    socket_state = results["socket_state"]
    print(f"\nSocket State: {'IN USE' if socket_state['result'] else 'FREE'}")
    print(f"  {socket_state['details']}")
    
    # Firewall
    firewall = results["firewall"]
    print(f"\nFirewall Blocking: {'YES' if firewall['result'] else 'NO'}")
    print(f"  {firewall['details']}")
    
    # TCP parameters
    tcp_params = results["tcp_params"]
    print("\nTCP Parameters:")
    for key, value in tcp_params.items():
        print(f"  {key}: {value}")
    
    # Service status
    service_status = results["service_status"]
    print(f"\nService Status: {service_status['status']}")
    print(f"  Installed: {'YES' if service_status['exists'] else 'NO'}")
    print(f"  Running: {'YES' if service_status['running'] else 'NO'}")
    
    # NCSI tests
    ncsi_tests = results["ncsi_tests"]
    print("\nNCSI Endpoint Tests:")
    for endpoint, success in ncsi_tests.items():
        print(f"  {endpoint}: {'SUCCESS' if success else 'FAILED'}")
    
    # Overall assessment
    print("\nOverall Assessment:")
    if service_status["running"] and any(ncsi_tests.values()):
        print("  Service is operational but may have limited functionality.")
    elif service_status["running"] and not any(ncsi_tests.values()):
        if port_open["result"]:
            print("  Service is running but not responding to NCSI requests.")
        else:
            print("  Service is running but port is not accessible.")
            if firewall["result"]:
                print("  Firewall may be blocking connections.")
    elif not service_status["running"]:
        print("  Service is not running.")
    else:
        print("  Could not determine status.")
    
    # Recommendations
    print("\nRecommendations:")
    if not service_status["running"]:
        print("  - Start the service with: net start NCSIResolver")
    if firewall["result"]:
        print("  - Configure Windows Firewall to allow connections to port {args.port}")
    if socket_state["result"]:
        print(f"  - The port is being used by another process. Try using a different port.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
