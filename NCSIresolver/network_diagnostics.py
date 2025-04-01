#!/usr/bin/env python3
"""
NCSI Resolver Network Diagnostics Module

This module provides layered network diagnostic capabilities for testing connectivity
at different network stack levels (ICMP, DNS, HTTP, HTTPS).
"""

import logging
import socket
import subprocess
import sys
import time
import platform
from typing import Dict, List, Optional, Tuple, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('network_diagnostics')

class NetworkDiagnostics:
    """
    Provides layered network diagnostics to identify connectivity issues.
    Tests connectivity at different layers of the network stack.
    """
    
    def __init__(self, timeout: float = 2.0):
        """
        Initialize the network diagnostics.
        
        Args:
            timeout: Timeout in seconds for tests
        """
        self.timeout = timeout
        self.results = {
            "icmp": {"success": False, "details": {}},
            "dns": {"success": False, "details": {}},
            "http": {"success": False, "details": {}},
            "https": {"success": False, "details": {}},
            "local_service": {"success": False, "details": {}}
        }
        
        # Default test targets - can be customized
        self.icmp_targets = ["8.8.8.8", "1.1.1.1"]
        self.dns_targets = [
            ("www.google.com", None),
            ("www.cloudflare.com", None)
        ]
        self.http_targets = [
            "http://www.gstatic.com/generate_204",
            "http://connectivitycheck.platform.hicloud.com/generate_204"
        ]
        self.https_targets = [
            "https://www.google.com",
            "https://www.cloudflare.com"
        ]
    
    def test_icmp(self, targets: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Test ICMP connectivity (ping).
        
        Args:
            targets: List of IP addresses to ping
            
        Returns:
            Dict containing test results
        """
        targets = targets or self.icmp_targets
        results = {"success": False, "targets": {}}
        
        for target in targets:
            target_result = {"success": False, "latency": None, "error": None}
            
            try:
                if platform.system().lower() == "windows":
                    # Windows-specific ping command
                    cmd = ["ping", "-n", "1", "-w", str(int(self.timeout * 1000)), target]
                    ping_output = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=self.timeout + 1
                    )
                    success = ping_output.returncode == 0
                    
                    # Extract latency if successful
                    if success:
                        for line in ping_output.stdout.splitlines():
                            if "time=" in line.lower() or "time<" in line.lower():
                                # Try to extract latency value
                                time_parts = line.split("time=")
                                if len(time_parts) > 1:
                                    latency_str = time_parts[1].split()[0].strip("ms")
                                    try:
                                        target_result["latency"] = float(latency_str)
                                    except ValueError:
                                        pass
                                break
                else:
                    # Unix-like systems
                    cmd = ["ping", "-c", "1", "-W", str(int(self.timeout)), target]
                    ping_output = subprocess.run(
                        cmd, 
                        capture_output=True, 
                        text=True,
                        timeout=self.timeout + 1
                    )
                    success = ping_output.returncode == 0
                    
                    # Extract latency if successful
                    if success:
                        for line in ping_output.stdout.splitlines():
                            if "time=" in line:
                                time_parts = line.split("time=")
                                if len(time_parts) > 1:
                                    latency_str = time_parts[1].split()[0].strip("ms")
                                    try:
                                        target_result["latency"] = float(latency_str)
                                    except ValueError:
                                        pass
                                break
                
                target_result["success"] = success
                if not success:
                    target_result["error"] = "Ping failed"
                
            except subprocess.TimeoutExpired:
                target_result["error"] = "Ping timed out"
            except Exception as e:
                target_result["error"] = str(e)
            
            results["targets"][target] = target_result
            if target_result["success"]:
                results["success"] = True
        
        # Save results
        self.results["icmp"] = results
        return results
    
    def test_dns(self, targets: Optional[List[Tuple[str, Optional[str]]]] = None) -> Dict[str, any]:
        """
        Test DNS resolution.
        
        Args:
            targets: List of (hostname, expected_ip) pairs
            
        Returns:
            Dict containing test results
        """
        targets = targets or self.dns_targets
        results = {"success": False, "targets": {}}
        
        for hostname, expected_ip in targets:
            target_result = {"success": False, "resolved_ip": None, "error": None}
            
            try:
                # Set socket timeout
                socket.setdefaulttimeout(self.timeout)
                
                # Resolve hostname
                ip_address = socket.gethostbyname(hostname)
                target_result["resolved_ip"] = ip_address
                
                # Check if IP matches expected (if specified)
                if expected_ip is not None and ip_address != expected_ip:
                    target_result["error"] = f"IP mismatch: got {ip_address}, expected {expected_ip}"
                else:
                    target_result["success"] = True
                
            except socket.gaierror as e:
                target_result["error"] = f"DNS resolution error: {e}"
            except socket.timeout:
                target_result["error"] = "DNS resolution timed out"
            except Exception as e:
                target_result["error"] = str(e)
            
            results["targets"][hostname] = target_result
            if target_result["success"]:
                results["success"] = True
        
        # Save results
        self.results["dns"] = results
        return results
    
    def test_http(self, targets: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Test HTTP connectivity.
        
        Args:
            targets: List of HTTP URLs to test
            
        Returns:
            Dict containing test results
        """
        targets = targets or self.http_targets
        results = {"success": False, "targets": {}}
        
        for url in targets:
            target_result = {"success": False, "status_code": None, "latency": None, "error": None}
            
            try:
                import urllib.request
                
                # Measure request time
                start_time = time.time()
                
                # Send request
                request = urllib.request.Request(url)
                response = urllib.request.urlopen(request, timeout=self.timeout)
                
                # Calculate latency
                latency = time.time() - start_time
                
                # Get status code
                status_code = response.getcode()
                
                target_result["status_code"] = status_code
                target_result["latency"] = latency * 1000  # Convert to milliseconds
                
                # Success if status code is 2xx or 3xx
                target_result["success"] = 200 <= status_code < 400
                if not target_result["success"]:
                    target_result["error"] = f"HTTP status code {status_code}"
                
            except urllib.error.URLError as e:
                target_result["error"] = f"URL error: {e.reason}"
            except urllib.error.HTTPError as e:
                target_result["status_code"] = e.code
                target_result["error"] = f"HTTP error: {e.reason}"
            except socket.timeout:
                target_result["error"] = "HTTP request timed out"
            except Exception as e:
                target_result["error"] = str(e)
            
            results["targets"][url] = target_result
            if target_result["success"]:
                results["success"] = True
        
        # Save results
        self.results["http"] = results
        return results
    
    def test_https(self, targets: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Test HTTPS connectivity.
        
        Args:
            targets: List of HTTPS URLs to test
            
        Returns:
            Dict containing test results
        """
        targets = targets or self.https_targets
        results = {"success": False, "targets": {}}
        
        for url in targets:
            target_result = {"success": False, "status_code": None, "latency": None, "error": None}
            
            try:
                import urllib.request
                import ssl
                
                # Create SSL context
                context = ssl.create_default_context()
                
                # Measure request time
                start_time = time.time()
                
                # Send request
                request = urllib.request.Request(url)
                response = urllib.request.urlopen(request, timeout=self.timeout, context=context)
                
                # Calculate latency
                latency = time.time() - start_time
                
                # Get status code
                status_code = response.getcode()
                
                target_result["status_code"] = status_code
                target_result["latency"] = latency * 1000  # Convert to milliseconds
                
                # Success if status code is 2xx or 3xx
                target_result["success"] = 200 <= status_code < 400
                if not target_result["success"]:
                    target_result["error"] = f"HTTPS status code {status_code}"
                
            except urllib.error.URLError as e:
                if isinstance(e.reason, ssl.SSLError):
                    target_result["error"] = f"SSL error: {str(e.reason)}"
                else:
                    target_result["error"] = f"URL error: {e.reason}"
            except urllib.error.HTTPError as e:
                target_result["status_code"] = e.code
                target_result["error"] = f"HTTP error: {e.reason}"
            except ssl.SSLError as e:
                target_result["error"] = f"SSL error: {str(e)}"
            except socket.timeout:
                target_result["error"] = "HTTPS request timed out"
            except Exception as e:
                target_result["error"] = str(e)
            
            results["targets"][url] = target_result
            if target_result["success"]:
                results["success"] = True
        
        # Save results
        self.results["https"] = results
        return results
    
    def test_local_service(self, host: str = "127.0.0.1", port: int = 80, urls: Optional[List[str]] = None) -> Dict[str, any]:
        """
        Test local NCSI service connectivity.
        
        Args:
            host: Host to test
            port: Port to test
            urls: List of paths to test (e.g., ["/connecttest.txt", "/ncsi.txt", "/redirect"])
            
        Returns:
            Dict containing test results
        """
        if urls is None:
            urls = ["/connecttest.txt", "/ncsi.txt", "/redirect"]
        
        results = {"success": False, "host": host, "port": port, "paths": {}}
        
        # First test if port is open
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            
            # Try to connect
            socket_result = sock.connect_ex((host, port))
            sock.close()
            
            results["port_open"] = socket_result == 0
            
            if not results["port_open"]:
                results["error"] = f"Port {port} is not open on {host}"
        except Exception as e:
            results["port_open"] = False
            results["error"] = str(e)
        
        # If port is open, test each path
        if results.get("port_open", False):
            for url in urls:
                path_result = {"success": False, "content": None, "error": None}
                
                try:
                    import urllib.request
                    
                    # Build full URL
                    full_url = f"http://{host}:{port}{url}"
                    
                    # Send request
                    request = urllib.request.Request(full_url)
                    response = urllib.request.urlopen(request, timeout=self.timeout)
                    
                    # Read content (limit to 1024 bytes)
                    content = response.read(1024)
                    
                    # Get status code
                    status_code = response.getcode()
                    
                    path_result["status_code"] = status_code
                    path_result["content_length"] = len(content)
                    
                    # Check content for specific paths
                    if url == "/connecttest.txt" or url == "/ncsi.txt":
                        expected_content = b"Microsoft Connect Test"
                        if content == expected_content:
                            path_result["success"] = True
                        else:
                            path_result["error"] = "Unexpected content"
                            # Show content preview for debugging
                            if isinstance(content, bytes):
                                path_result["content_preview"] = content.decode('utf-8', errors='replace')[:50]
                            else:
                                path_result["content_preview"] = str(content)[:50]
                    else:
                        # For other paths, just check for 200 status
                        path_result["success"] = status_code == 200
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
                
                results["paths"][url] = path_result
                if path_result["success"]:
                    results["success"] = True
        
        # Save results
        self.results["local_service"] = results
        return results
    
    def run_all_tests(self, include_local_service: bool = True, local_host: str = "127.0.0.1", local_port: int = 80) -> Dict[str, any]:
        """
        Run all diagnostic tests in sequence.
        
        Args:
            include_local_service: Whether to include local service tests
            local_host: Host for local service tests
            local_port: Port for local service tests
            
        Returns:
            Dict containing all test results
        """
        # Run tests in order
        self.test_icmp()
        self.test_dns()
        self.test_http()
        self.test_https()
        
        if include_local_service:
            self.test_local_service(host=local_host, port=local_port)
        
        return self.results
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get a summary of test results.
        
        Returns:
            Dict with summary information
        """
        return {
            "icmp": self.results["icmp"]["success"],
            "dns": self.results["dns"]["success"],
            "http": self.results["http"]["success"],
            "https": self.results["https"]["success"],
            "local_service": self.results["local_service"]["success"],
            "all_tests_success": (
                self.results["icmp"]["success"] and
                self.results["dns"]["success"] and
                self.results["http"]["success"] and
                self.results["https"]["success"] and
                self.results["local_service"]["success"]
            ),
            "internet_connectivity": (
                self.results["icmp"]["success"] or
                self.results["dns"]["success"] or
                (self.results["http"]["success"] and self.results["https"]["success"])
            )
        }
    
    def format_report(self, verbose: bool = False) -> str:
        """
        Generate a formatted report of test results.
        
        Args:
            verbose: Whether to include detailed information
            
        Returns:
            Formatted string with test results
        """
        summary = self.get_summary()
        lines = []
        
        lines.append("Network Diagnostics Report")
        lines.append("=========================")
        
        # Internet connectivity summary
        lines.append(f"\nInternet Connectivity: {'AVAILABLE' if summary['internet_connectivity'] else 'NOT AVAILABLE'}")
        
        # ICMP (Ping)
        lines.append(f"\nICMP (Ping): {'SUCCESS' if summary['icmp'] else 'FAILED'}")
        if verbose:
            for target, result in self.results["icmp"]["targets"].items():
                status = "SUCCESS" if result["success"] else "FAILED"
                latency = f"{result['latency']:.1f} ms" if result["latency"] else "N/A"
                error = f" - {result['error']}" if result["error"] else ""
                lines.append(f"  {target}: {status} (Latency: {latency}){error}")
        
        # DNS
        lines.append(f"\nDNS Resolution: {'SUCCESS' if summary['dns'] else 'FAILED'}")
        if verbose:
            for hostname, result in self.results["dns"]["targets"].items():
                status = "SUCCESS" if result["success"] else "FAILED"
                ip = result["resolved_ip"] or "N/A"
                error = f" - {result['error']}" if result["error"] else ""
                lines.append(f"  {hostname}: {status} (Resolved to: {ip}){error}")
        
        # HTTP
        lines.append(f"\nHTTP Connectivity: {'SUCCESS' if summary['http'] else 'FAILED'}")
        if verbose:
            for url, result in self.results["http"]["targets"].items():
                status = "SUCCESS" if result["success"] else "FAILED"
                code = f"Status {result['status_code']}" if result["status_code"] else "N/A"
                latency = f"{result['latency']:.1f} ms" if result["latency"] else "N/A"
                error = f" - {result['error']}" if result["error"] else ""
                lines.append(f"  {url}: {status} ({code}, Latency: {latency}){error}")
        
        # HTTPS
        lines.append(f"\nHTTPS Connectivity: {'SUCCESS' if summary['https'] else 'FAILED'}")
        if verbose:
            for url, result in self.results["https"]["targets"].items():
                status = "SUCCESS" if result["success"] else "FAILED"
                code = f"Status {result['status_code']}" if result["status_code"] else "N/A"
                latency = f"{result['latency']:.1f} ms" if result["latency"] else "N/A"
                error = f" - {result['error']}" if result["error"] else ""
                lines.append(f"  {url}: {status} ({code}, Latency: {latency}){error}")
        
        # Local Service
        local_service = self.results["local_service"]
        if "host" in local_service:
            host = local_service["host"]
            port = local_service["port"]
            lines.append(f"\nLocal NCSI Service ({host}:{port}): {'SUCCESS' if summary['local_service'] else 'FAILED'}")
            
            if "port_open" in local_service:
                lines.append(f"  Port Open: {'YES' if local_service['port_open'] else 'NO'}")
                
                if verbose and local_service["port_open"]:
                    for path, result in local_service["paths"].items():
                        status = "SUCCESS" if result["success"] else "FAILED"
                        error = f" - {result['error']}" if result["error"] else ""
                        lines.append(f"  {path}: {status}{error}")
                        
                        if "content_preview" in result:
                            lines.append(f"    Content Preview: {result['content_preview']}")
            
            if "error" in local_service:
                lines.append(f"  Error: {local_service['error']}")
        
        # Overall assessment
        lines.append("\nAnalysis & Recommendations:")
        if summary["all_tests_success"]:
            lines.append("  All tests passed! Your network connectivity is excellent.")
        else:
            if summary["internet_connectivity"]:
                lines.append("  You have internet connectivity, but some tests failed.")
                
                # Specific recommendations based on failures
                if not summary["icmp"]:
                    lines.append("  - ICMP/Ping is blocked. This is common in some networks and not critical.")
                
                if not summary["dns"]:
                    lines.append("  - DNS resolution issues detected. Check your DNS settings or try alternative DNS servers.")
                
                if not summary["http"] or not summary["https"]:
                    lines.append("  - HTTP/HTTPS connectivity issues. Check for proxy settings or firewall restrictions.")
                
                if not summary["local_service"]:
                    if local_service.get("port_open", False):
                        lines.append("  - Local NCSI service is running but not responding correctly. Check service configuration.")
                    else:
                        lines.append("  - Local NCSI service port is not accessible. Check service status and firewall settings.")
            else:
                lines.append("  No internet connectivity detected. Please check your network connection.")
                
                if not summary["icmp"] and not summary["dns"]:
                    lines.append("  - Basic network connectivity is failing. Check physical connection and router.")
        
        return "\n".join(lines)

# Example usage
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NCSI Resolver Network Diagnostics")
    parser.add_argument("--host", default="127.0.0.1", help="Host for local service tests")
    parser.add_argument("--port", type=int, default=80, help="Port for local service tests")
    parser.add_argument("--timeout", type=float, default=2.0, help="Timeout in seconds")
    parser.add_argument("--verbose", action="store_true", help="Show detailed results")
    
    args = parser.parse_args()
    
    # Set up diagnostics
    diagnostics = NetworkDiagnostics(timeout=args.timeout)
    
    # Run all tests
    diagnostics.run_all_tests(local_host=args.host, local_port=args.port)
    
    # Print report
    print(diagnostics.format_report(verbose=args.verbose))
