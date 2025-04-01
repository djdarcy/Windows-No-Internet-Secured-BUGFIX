#!/usr/bin/env python3
"""
NCSI Resolver Enhanced Test Script

This script provides comprehensive testing for NCSI Resolver installation and functionality.
It uses the network_diagnostics module to test connectivity at multiple layers.
"""

import argparse
import logging
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ncsi_tester')

# Try to import our diagnostic module
try:
    from network_diagnostics import NetworkDiagnostics
    diagnostics_available = True
except ImportError:
    diagnostics_available = False
    logger.warning("Network diagnostics module not available, using basic tests")

def is_admin() -> bool:
    """Check if running with administrative privileges."""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of the machine.
    
    Returns:
        str: Local IP address, or None if it can't be determined
    """
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {e}")
        return None

def get_install_dir() -> Optional[str]:
    """
    Try to find the NCSI Resolver installation directory.
    
    Returns:
        str: Installation directory path, or None if not found
    """
    # Common installation paths
    paths_to_check = [
        r"C:\Program Files\NCSI Resolver",
        r"C:\NCSI_Resolver",
        os.path.join(os.environ.get('PROGRAMDATA', r"C:\ProgramData"), "NCSI Resolver")
    ]
    
    # Check each path
    for path in paths_to_check:
        if os.path.exists(path):
            logger.info(f"Found installation directory: {path}")
            return path
    
    logger.warning("Could not find NCSI Resolver installation directory")
    return None

def check_registry_settings() -> Dict[str, any]:
    """
    Check NCSI registry settings.
    
    Returns:
        Dict with registry settings information
    """
    result = {
        "configured": False,
        "settings": {}
    }
    
    try:
        import winreg
        
        # Open registry key
        registry_key = r"SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet"
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            registry_key,
            0,
            winreg.KEY_READ
        )
        
        # Try to read ActiveWebProbeHost
        try:
            value, _ = winreg.QueryValueEx(key, "ActiveWebProbeHost")
            result["settings"]["ActiveWebProbeHost"] = value
        except FileNotFoundError:
            result["settings"]["ActiveWebProbeHost"] = "default (not set)"
        
        # Try to read ActiveWebProbePath
        try:
            value, _ = winreg.QueryValueEx(key, "ActiveWebProbePath")
            result["settings"]["ActiveWebProbePath"] = value
        except FileNotFoundError:
            result["settings"]["ActiveWebProbePath"] = "default (not set)"
        
        # Check if both settings are configured
        if (result["settings"].get("ActiveWebProbeHost", "") != "default (not set)" and
            result["settings"].get("ActiveWebProbePath", "") != "default (not set)"):
            result["configured"] = True
        
        # Close the key
        winreg.CloseKey(key)
        
    except Exception as e:
        logger.error(f"Error checking registry: {e}")
    
    return result

def check_hosts_file(hostname: str = "www.msftconnecttest.com") -> Dict[str, any]:
    """
    Check if hosts file is configured.
    
    Args:
        hostname: Hostname to check for
        
    Returns:
        Dict with hosts file information
    """
    result = {
        "configured": False,
        "redirect_ip": None,
        "file_path": r"C:\Windows\System32\drivers\etc\hosts"
    }
    
    try:
        # Check if hosts file exists
        hosts_path = Path(result["file_path"])
        if not hosts_path.exists():
            logger.error(f"Hosts file not found at {result['file_path']}")
            return result
        
        # Read hosts file
        with open(hosts_path, 'r') as f:
            hosts_content = f.read()
        
        # Look for the hostname in the hosts file
        import re
        pattern = re.compile(rf'^\s*(\d+\.\d+\.\d+\.\d+)\s+{re.escape(hostname)}(?:\s|$)', re.MULTILINE)
        match = pattern.search(hosts_content)
        
        if match:
            result["redirect_ip"] = match.group(1)
            result["configured"] = True
        
    except Exception as e:
        logger.error(f"Error checking hosts file: {e}")
    
    return result

def check_service_status(service_name: str = "NCSIResolver") -> Dict[str, any]:
    """
    Check if the service is installed and running.
    
    Args:
        service_name: Name of the service
        
    Returns:
        Dict with service status information
    """
    result = {
        "installed": False,
        "running": False,
        "status": "Not installed"
    }
    
    try:
        # Check if service is installed using sc query
        cmd = ["sc", "query", service_name]
        sc_output = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )
        
        if sc_output.returncode == 0:
            result["installed"] = True
            
            # Check if service is running
            if "RUNNING" in sc_output.stdout:
                result["running"] = True
                result["status"] = "Running"
            elif "STOPPED" in sc_output.stdout:
                result["status"] = "Stopped"
            elif "STARTING" in sc_output.stdout:
                result["status"] = "Starting"
            elif "STOPPING" in sc_output.stdout:
                result["status"] = "Stopping"
            else:
                result["status"] = "Unknown"
        
    except Exception as e:
        logger.error(f"Error checking service status: {e}")
    
    return result

def test_connectivity(host: str = "127.0.0.1", port: int = 80, 
                     paths: Optional[List[str]] = None,
                     timeout: float = 2.0) -> Dict[str, any]:
    """
    Test connectivity to NCSI service.
    
    Args:
        host: Host to test
        port: Port to test
        paths: List of paths to test
        timeout: Timeout in seconds
        
    Returns:
        Dict with connectivity test results
    """
    if paths is None:
        paths = ["/connecttest.txt", "/ncsi.txt", "/redirect"]
    
    result = {
        "port_open": False,
        "paths": {}
    }
    
    # First check if port is open
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        
        # Try to connect
        connection_result = sock.connect_ex((host, port))
        sock.close()
        
        result["port_open"] = connection_result == 0
        
        if not result["port_open"]:
            result["error"] = f"Port {port} is not open on {host} (code: {connection_result})"
            return result
    except Exception as e:
        result["port_open"] = False
        result["error"] = str(e)
        return result
    
    # If port is open, test each path
    for path in paths:
        path_result = {
            "success": False,
            "response_code": None,
            "content": None,
            "error": None
        }
        
        try:
            import urllib.request
            
            # Build full URL
            full_url = f"http://{host}:{port}{path}"
            
            # Send request
            request = urllib.request.Request(full_url)
            response = urllib.request.urlopen(request, timeout=timeout)
            
            # Read content (limit to 1024 bytes)
            content = response.read(1024)
            
            # Get status code
            status_code = response.getcode()
            
            path_result["status_code"] = status_code
            
            # Check content for specific paths
            if path in ["/connecttest.txt", "/ncsi.txt"]:
                expected_content = b"Microsoft Connect Test"
                path_result["success"] = content == expected_content
                path_result["content"] = content.decode('utf-8', errors='replace')
                
                if not path_result["success"]:
                    path_result["error"] = "Unexpected content"
            else:
                # For other paths, just check for 200 status
                path_result["success"] = status_code == 200
                path_result["content_length"] = len(content)
                
                if not path_result["success"]:
                    path_result["error"] = f"Status code {status_code}"
            
        except urllib.error.URLError as e:
            path_result["error"] = f"URL error: {e.reason}"
        except urllib.error.HTTPError as e:
            path_result["status_code"] = e.code
            path_result["error"] = f"HTTP error: {e.reason}"
        except socket.timeout:
            path_result["error"] = "Request timed out"
        except Exception as e:
            path_result["error"] = str(e)
        
        result["paths"][path] = path_result
    
    # Check if any path succeeded
    result["success"] = any(path_result["success"] for path_result in result["paths"].values())
    
    return result

def check_network_adapters() -> Dict[str, any]:
    """
    Check network adapters for Wi-Fi configuration.
    
    Returns:
        Dict with network adapter information
    """
    result = {
        "adapters": [],
        "has_wifi": False
    }
    
    try:
        # Try using netsh
        netsh_output = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if netsh_output.returncode == 0:
            # Parse output
            lines = netsh_output.stdout.splitlines()
            
            # Skip header lines
            start_line = 0
            for i, line in enumerate(lines):
                if "---" in line:
                    start_line = i + 1
                    break
            
            # Process adapter lines
            for line in lines[start_line:]:
                if not line.strip():
                    continue
                
                parts = line.split()
                if len(parts) >= 4:
                    adapter_info = {
                        "name": parts[-1],
                        "type": parts[-2],
                        "state": parts[-3],
                        "admin_state": parts[-4]
                    }
                    
                    # Check if it's a Wi-Fi adapter
                    if any(wifi_term.lower() in adapter_info["name"].lower() for wifi_term in 
                          ["wireless", "wifi", "wi-fi", "wlan"]):
                        adapter_info["is_wifi"] = True
                        result["has_wifi"] = True
                    else:
                        adapter_info["is_wifi"] = False
                    
                    result["adapters"].append(adapter_info)
        
        # Try using wmi method if no Wi-Fi adapter found and WMI is available
        if not result["has_wifi"]:
            try:
                import wmi
                c = wmi.WMI()
                
                for nic in c.Win32_NetworkAdapter():
                    adapter_info = {
                        "name": nic.Name,
                        "device_id": nic.DeviceID,
                        "status": nic.Status,
                        "mac_address": nic.MACAddress
                    }
                    
                    # Check if it's a Wi-Fi adapter
                    if any(wifi_term.lower() in adapter_info["name"].lower() for wifi_term in 
                          ["wireless", "wifi", "wi-fi", "802.11", "wlan"]):
                        adapter_info["is_wifi"] = True
                        result["has_wifi"] = True
                    else:
                        adapter_info["is_wifi"] = False
                    
                    result["adapters"].append(adapter_info)
            except ImportError:
                # WMI not available
                pass
    
    except Exception as e:
        logger.error(f"Error checking network adapters: {e}")
    
    return result

def run_enhanced_diagnostics(hosts: List[str], ports: List[int]) -> Dict[str, any]:
    """
    Run enhanced network diagnostics if the module is available.
    
    Args:
        hosts: List of hosts to test
        ports: List of ports to test
        
    Returns:
        Dict with diagnostic results
    """
    if not diagnostics_available:
        return {"error": "Network diagnostics module not available"}
    
    results = {}
    
    for host in hosts:
        host_results = {}
        
        for port in ports:
            # Create diagnostics instance
            diagnostics = NetworkDiagnostics(timeout=2.0)
            
            # Run all tests
            logger.info(f"Running network diagnostics for {host}:{port}")
            diagnostics.run_all_tests(include_local_service=True, local_host=host, local_port=port)
            
            # Get test results
            host_results[str(port)] = {
                "summary": diagnostics.get_summary(),
                "full_results": diagnostics.results,
                "report": diagnostics.format_report(verbose=False)
            }
        
        results[host] = host_results
    
    return results

def run_comprehensive_tests() -> Dict[str, any]:
    """
    Run comprehensive tests of the NCSI Resolver installation and functionality.
    
    Returns:
        Dict with test results
    """
    results = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "system": {
            "is_admin": is_admin(),
            "python_version": sys.version,
            "platform": sys.platform
        },
        "installation": {
            "install_dir": get_install_dir()
        },
        "configuration": {
            "registry": check_registry_settings(),
            "hosts_file": check_hosts_file(),
            "service": check_service_status()
        }
    }
    
    # Get local IP
    local_ip = get_local_ip()
    results["network"] = {
        "local_ip": local_ip,
        "adapters": check_network_adapters()
    }
    
    # Test connectivity to different hosts
    hosts_to_test = ["127.0.0.1"]
    if local_ip:
        hosts_to_test.append(local_ip)
    
    # Add registry host if available
    registry_host = results["configuration"]["registry"]["settings"].get("ActiveWebProbeHost", "")
    if registry_host and registry_host != "default (not set)" and ":" in registry_host:
        registry_host = registry_host.split(":")[0]
        if registry_host not in hosts_to_test:
            hosts_to_test.append(registry_host)
    
    # Add hosts file redirect if available
    hosts_redirect = results["configuration"]["hosts_file"].get("redirect_ip")
    if hosts_redirect and hosts_redirect not in hosts_to_test:
        hosts_to_test.append(hosts_redirect)
    
    # Define ports to test
    ports_to_test = [80]
    
    # Add registry port if available
    if registry_host and ":" in registry_host:
        try:
            registry_port = int(registry_host.split(":")[1])
            if registry_port not in ports_to_test:
                ports_to_test.append(registry_port)
        except (ValueError, IndexError):
            pass
    
    # Test connectivity
    connectivity_results = {}
    for host in hosts_to_test:
        host_results = {}
        for port in ports_to_test:
            logger.info(f"Testing connectivity to {host}:{port}")
            host_results[str(port)] = test_connectivity(host, port)
        connectivity_results[host] = host_results
    
    results["connectivity"] = connectivity_results
    
    # Run enhanced diagnostics if available
    if diagnostics_available:
        results["diagnostics"] = run_enhanced_diagnostics(hosts_to_test, ports_to_test)
    
    # Overall assessment
    results["assessment"] = {}
    
    # Check configuration
    config_ok = (
        results["configuration"]["registry"]["configured"] and
        results["configuration"]["hosts_file"]["configured"] and
        results["configuration"]["service"]["installed"]
    )
    results["assessment"]["configuration_ok"] = config_ok
    
    # Check service
    service_ok = results["configuration"]["service"]["running"]
    results["assessment"]["service_ok"] = service_ok
    
    # Check connectivity
    connectivity_ok = False
    for host, host_results in connectivity_results.items():
        for port, port_results in host_results.items():
            if port_results.get("success", False):
                connectivity_ok = True
                break
    
    results["assessment"]["connectivity_ok"] = connectivity_ok
    
    # Overall success
    results["assessment"]["success"] = config_ok and service_ok and connectivity_ok
    
    return results

def format_test_results(results: Dict[str, any], verbose: bool = False) -> str:
    """
    Format test results for display.
    
    Args:
        results: Test results dictionary
        verbose: Whether to include detailed information
        
    Returns:
        Formatted string with test results
    """
    lines = []
    
    lines.append("NCSI Resolver Test Results")
    lines.append("=========================")
    lines.append(f"Time: {results['timestamp']}")
    
    # System information
    lines.append("\nSystem Information:")
    lines.append(f"  Administrator: {'Yes' if results['system']['is_admin'] else 'No'}")
    lines.append(f"  Python: {results['system']['python_version'].split()[0]}")
    lines.append(f"  Platform: {results['system']['platform']}")
    
    # Installation
    lines.append("\nInstallation:")
    install_dir = results['installation']['install_dir']
    if install_dir:
        lines.append(f"  Directory: {install_dir}")
    else:
        lines.append("  Directory: Not found")
    
    # Configuration
    lines.append("\nConfiguration:")
    
    # Registry
    registry = results['configuration']['registry']
    lines.append(f"  Registry: {'Configured' if registry['configured'] else 'Not configured'}")
    for key, value in registry['settings'].items():
        lines.append(f"    {key}: {value}")
    
    # Hosts file
    hosts_file = results['configuration']['hosts_file']
    lines.append(f"  Hosts File: {'Configured' if hosts_file['configured'] else 'Not configured'}")
    if hosts_file.get('redirect_ip'):
        lines.append(f"    Redirect: www.msftconnecttest.com -> {hosts_file['redirect_ip']}")
    
    # Service
    service = results['configuration']['service']
    lines.append(f"  Service: {service['status']}")
    lines.append(f"    Installed: {'Yes' if service['installed'] else 'No'}")
    lines.append(f"    Running: {'Yes' if service['running'] else 'No'}")
    
    # Network
    lines.append("\nNetwork:")
    lines.append(f"  Local IP: {results['network']['local_ip']}")
    
    # Adapters
    adapters = results['network']['adapters']
    lines.append(f"  Wi-Fi Adapters: {'Present' if adapters['has_wifi'] else 'None detected'}")
    if verbose:
        for i, adapter in enumerate(adapters['adapters']):
            lines.append(f"    Adapter {i+1}: {adapter['name']} "
                        f"({'Wi-Fi' if adapter.get('is_wifi', False) else 'Wired'})")
    
    # Connectivity
    lines.append("\nConnectivity Tests:")
    connectivity_success = False
    
    for host, host_results in results['connectivity'].items():
        for port, port_result in host_results.items():
            status = "SUCCESS" if port_result.get("success", False) else "FAILED"
            if port_result.get("success", False):
                connectivity_success = True
            
            lines.append(f"  {host}:{port} - {status}")
            
            if verbose:
                if not port_result.get("port_open", False):
                    lines.append(f"    Port not open: {port_result.get('error', 'Unknown error')}")
                else:
                    for path, path_result in port_result.get("paths", {}).items():
                        path_status = "SUCCESS" if path_result.get("success", False) else "FAILED"
                        lines.append(f"    {path}: {path_status}")
                        
                        if path_result.get("error"):
                            lines.append(f"      Error: {path_result['error']}")
                        
                        if path_result.get("content") and len(path_result.get("content", "")) < 100:
                            lines.append(f"      Content: {path_result['content']}")
    
    # Diagnostics summary (if available)
    if "diagnostics" in results:
        lines.append("\nNetwork Diagnostics Summary:")
        
        for host, host_results in results['diagnostics'].items():
            for port, port_result in host_results.items():
                summary = port_result.get("summary", {})
                
                lines.append(f"  {host}:{port}:")
                lines.append(f"    Internet Connectivity: "
                            f"{'AVAILABLE' if summary.get('internet_connectivity', False) else 'NOT AVAILABLE'}")
                lines.append(f"    ICMP (Ping): {'SUCCESS' if summary.get('icmp', False) else 'FAILED'}")
                lines.append(f"    DNS: {'SUCCESS' if summary.get('dns', False) else 'FAILED'}")
                lines.append(f"    HTTP: {'SUCCESS' if summary.get('http', False) else 'FAILED'}")
                lines.append(f"    HTTPS: {'SUCCESS' if summary.get('https', False) else 'FAILED'}")
                lines.append(f"    Local Service: {'SUCCESS' if summary.get('local_service', False) else 'FAILED'}")
    
    # Overall assessment
    lines.append("\nOverall Assessment:")
    lines.append(f"  Configuration: {'OK' if results['assessment']['configuration_ok'] else 'ISSUES DETECTED'}")
    lines.append(f"  Service: {'RUNNING' if results['assessment']['service_ok'] else 'NOT RUNNING'}")
    lines.append(f"  Connectivity: {'OK' if results['assessment']['connectivity_ok'] else 'ISSUES DETECTED'}")
    lines.append(f"  Overall Status: {'SUCCESS' if results['assessment']['success'] else 'ISSUES DETECTED'}")
    
    # Recommendations
    lines.append("\nRecommendations:")
    
    if not results['assessment']['success']:
        if not results['assessment']['configuration_ok']:
            lines.append("  - Configuration issues detected. Run the installer again.")
            
            if not results['configuration']['registry']['configured']:
                lines.append("    - Registry is not properly configured.")
            
            if not results['configuration']['hosts_file']['configured']:
                lines.append("    - Hosts file is not properly configured.")
            
            if not results['configuration']['service']['installed']:
                lines.append("    - Service is not installed.")
        
        if not results['assessment']['service_ok']:
            lines.append("  - Service is not running. Start it with: net start NCSIResolver")
        
        if not results['assessment']['connectivity_ok']:
            lines.append("  - Connectivity issues detected:")
            
            # Check if any host has port not open
            port_not_open = False
            for host, host_results in results['connectivity'].items():
                for port, port_result in host_results.items():
                    if not port_result.get("port_open", False):
                        port_not_open = True
                        lines.append(f"    - Port {port} is not accessible on {host}.")
            
            if port_not_open:
                lines.append("    - Check firewall settings and make sure no other application is using the port.")
                lines.append("    - Try installing with a different port (e.g., --port=8080).")
    else:
        lines.append("  All tests passed! NCSI Resolver is working correctly.")
    
    return "\n".join(lines)

def main():
    """Main entry point when running as a script."""
    parser = argparse.ArgumentParser(description="NCSI Resolver Test Script")
    parser.add_argument("--verbose", action="store_true", help="Show detailed test results")
    parser.add_argument("--output", help="Save results to file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--host", help="Specific host to test")
    parser.add_argument("--port", type=int, default=80, help="Specific port to test")
    parser.add_argument("--diagnostics-only", action="store_true", help="Run only network diagnostics")
    
    args = parser.parse_args()
    
    if args.diagnostics_only:
        if not diagnostics_available:
            print("Network diagnostics module not available")
            return 1
        
        host = args.host or "127.0.0.1"
        diagnostics = NetworkDiagnostics(timeout=2.0)
        diagnostics.run_all_tests(local_host=host, local_port=args.port)
        print(diagnostics.format_report(verbose=args.verbose))
        return 0
    
    # Run comprehensive tests
    print("Running NCSI Resolver tests...")
    results = run_comprehensive_tests()
    
    # Output results
    if args.json:
        import json
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"Results saved to {args.output}")
        else:
            print(json.dumps(results, indent=2))
    else:
        formatted_results = format_test_results(results, verbose=args.verbose)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(formatted_results)
            print(f"Results saved to {args.output}")
        else:
            print(formatted_results)
    
    # Return exit code based on test results
    return 0 if results["assessment"]["success"] else 1

if __name__ == "__main__":
    sys.exit(main())