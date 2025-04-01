#!/usr/bin/env python3
"""
Windows NCSI (Network Connectivity Status Indicator) Server

This module provides a server that responds to Windows Network Connectivity Status Indicator
requests, allowing Windows to correctly show internet connectivity even when network
equipment might be interfering with Microsoft's connectivity tests.

It handles both the /connecttest.txt and /redirect endpoints that Windows uses to verify
internet connectivity and detect captive portals.
"""

import argparse
import atexit
import logging
import os
import socket
import sys
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

try:
    from version import get_version_info
    
    # Get version information
    __version_info__ = get_version_info("server")
    __version__ = __version_info__["version"]
    __description__ = __version_info__["description"]
except ImportError:
    # Fallback version info if version.py is missing
    __version__ = "0.5.0"
    __description__ = "Windows Network Connectivity Status Indicator Resolver Server"


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ncsi_server')

# NCSI Constants
NCSI_TEXT = b"Microsoft Connect Test"
DEFAULT_PORT = 80
REDIRECT_HTML_CONTENT = b"""<!DOCTYPE html>
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
"""

class ConnectivityChecker:
    """Checks actual internet connectivity using multiple methods."""
    
    def __init__(self, ping_targets: List[str] = None, dns_targets: List[Tuple[str, str]] = None, 
                 http_targets: List[str] = None, timeout: float = 2.0):
        """
        Initialize the connectivity checker with configurable targets.
        
        Args:
            ping_targets: List of IP addresses to ping
            dns_targets: List of (hostname, expected_ip) pairs to resolve
            http_targets: List of URLs to fetch
            timeout: Timeout in seconds for connectivity checks
        """
        self.ping_targets = ping_targets or ["8.8.8.8", "1.1.1.1", "4.2.2.1"]
        self.dns_targets = dns_targets or [
            ("www.google.com", None),
            ("www.cloudflare.com", None)
        ]
        self.http_targets = http_targets or [
            "http://www.gstatic.com/generate_204",
            "http://connectivitycheck.platform.hicloud.com/generate_204"
        ]
        self.timeout = timeout
        self.last_check_time = 0
        self.is_connected = False
        self.lock = threading.Lock()
        self.check_interval = 15  # seconds between checks

    def ping(self, host: str) -> bool:
        """Check connectivity using ICMP echo (ping)."""
        try:
            # Create a socket for ICMP
            if sys.platform == "win32":
                sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
            
            sock.settimeout(self.timeout)
            sock.connect((host, 1))
            return True
        except (socket.error, OSError):
            return False
        finally:
            try:
                sock.close()
            except (socket.error, OSError, UnboundLocalError):
                pass

    def dns_lookup(self, hostname: str, expected_ip: Optional[str] = None) -> bool:
        """Check connectivity by performing a DNS lookup."""
        try:
            ip = socket.gethostbyname(hostname)
            if expected_ip and ip != expected_ip:
                logger.warning(f"DNS lookup for {hostname} returned {ip}, expected {expected_ip}")
                return False
            return True
        except socket.error:
            return False

    def http_check(self, url: str) -> bool:
        """Check connectivity by making an HTTP request."""
        try:
            import urllib.request
            with urllib.request.urlopen(url, timeout=self.timeout) as response:
                return response.status == 204 or response.status == 200
        except Exception as e:
            logger.debug(f"HTTP check failed for {url}: {e}")
            return False

    def check_connectivity(self, force: bool = False) -> bool:
        """
        Check internet connectivity using multiple methods.
        
        Returns:
            bool: True if connected, False otherwise
        """
        current_time = time.time()
        
        # Use cached result if it's recent enough
        if not force and current_time - self.last_check_time < self.check_interval:
            return self.is_connected
            
        with self.lock:
            self.last_check_time = current_time
            
            # Try ping first (fastest)
            for target in self.ping_targets:
                if self.ping(target):
                    logger.debug(f"Ping to {target} successful")
                    self.is_connected = True
                    return True
            
            # Try DNS lookup next
            for hostname, expected_ip in self.dns_targets:
                if self.dns_lookup(hostname, expected_ip):
                    logger.debug(f"DNS lookup for {hostname} successful")
                    self.is_connected = True
                    return True
            
            # Finally, try HTTP check
            for url in self.http_targets:
                if self.http_check(url):
                    logger.debug(f"HTTP check for {url} successful")
                    self.is_connected = True
                    return True
            
            logger.warning("All connectivity checks failed")
            self.is_connected = False
            return False


class NCSIHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler for NCSI requests.
    
    Handles the two endpoints that Windows uses to check connectivity:
    - /connecttest.txt: Returns "Microsoft Connect Test"
    - /redirect: Returns a simple HTML page
    """
    
    # Class attribute to store the connectivity checker
    connectivity_checker = None
    
    # Flag to control whether to check actual connectivity
    verify_real_connectivity = True
    
    # Request counter for tracking activity
    request_counter = 0
    
    def version_string(self):
        """Override the server identity."""
        return "NCSI-Resolver/1.0"
    
    def log_request(self, code='-', size='-'):
        """Log an accepted request."""
        NCSIHandler.request_counter += 1
        self.log_message(f'"{self.requestline}" {code} {size} (Request #{NCSIHandler.request_counter})')
    
    def do_GET(self):
        """Handle GET requests."""
        client_ip = self.client_address[0]
        
        # Log the source of the request
        if client_ip.startswith('127.') or client_ip == '::1':
            logger.info(f"Request from localhost ({client_ip}) for {self.path}")
        else:
            logger.info(f"Request from external client {client_ip} for {self.path}")
        
        # Handle NCSI connectivity test
        if self.path == "/connecttest.txt" or self.path == "/ncsi.txt":
            # Check actual connectivity if enabled
            if self.verify_real_connectivity and self.connectivity_checker:
                if not self.connectivity_checker.check_connectivity():
                    self.send_error(503, "Internet connectivity check failed")
                    return
            
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.send_header("Content-Length", str(len(NCSI_TEXT)))
            self.end_headers()
            self.wfile.write(NCSI_TEXT)
            
        # Handle NCSI redirect endpoint (used for captive portal detection)
        elif self.path == "/redirect":
            # Check actual connectivity if enabled
            if self.verify_real_connectivity and self.connectivity_checker:
                if not self.connectivity_checker.check_connectivity():
                    self.send_error(503, "Internet connectivity check failed")
                    return
            
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(len(REDIRECT_HTML_CONTENT)))
            self.end_headers()
            self.wfile.write(REDIRECT_HTML_CONTENT)
            
        # Return a 404 for any other paths
        else:
            self.send_error(404, "Not Found")
    
    def log_message(self, format, *args):
        """Log messages to the logger instead of stderr."""
        logger.info(format % args)


def get_local_ip() -> Optional[str]:
    """
    Get the local IP address of the machine.
    
    Returns:
        str: The local IP address, or None if it can't be determined
    """
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect but gets the route that would be used
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {e}")
        return None


def create_server(host: str = None, port: int = DEFAULT_PORT, 
                  verify_connectivity: bool = True) -> HTTPServer:
    """
    Create and configure the NCSI HTTP server.
    
    Args:
        host: Host address to bind to (None for all interfaces)
        port: Port to listen on
        verify_connectivity: Whether to verify actual connectivity
        
    Returns:
        HTTPServer: The configured server instance
    """
    # Create connectivity checker if enabled
    if verify_connectivity:
        checker = ConnectivityChecker()
        NCSIHandler.connectivity_checker = checker
    
    NCSIHandler.verify_real_connectivity = verify_connectivity
    
    # Determine host address if not specified
    if host is None:
        host = get_local_ip() or "0.0.0.0"
    
    # Create and return the server
    try:
        server = HTTPServer((host, port), NCSIHandler)
        logger.info(f"Server created on {host}:{port}")
        return server
    except Exception as e:
        logger.error(f"Failed to create server: {e}")
        raise


def run_server(server: HTTPServer, register_exit_handler: bool = True):
    """
    Run the NCSI server until interrupted.
    
    Args:
        server: The server instance to run
        register_exit_handler: Whether to register an exit handler
    """
    if register_exit_handler:
        def cleanup():
            logger.info("Shutting down server...")
            server.shutdown()
            logger.info("Server shutdown complete")
        
        atexit.register(cleanup)
    
    try:
        address, port = server.server_address
        logger.info(f"Starting NCSI server on {address}:{port}")
        
        # Start server in a separate thread
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        server_thread.start()
        
        # Return the thread instead of blocking
        return server_thread
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")


def main():
    """Main entry point when running as a script."""
    parser = argparse.ArgumentParser(description="Windows NCSI Resolver Server")
    parser.add_argument("--host", help="Host address to bind to (default: auto-detect)")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default: {DEFAULT_PORT})")
    parser.add_argument("--no-verify", action="store_true", help="Don't verify actual internet connectivity")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--foreground", action="store_true", help="Run in foreground (don't return after starting)")
    
    args = parser.parse_args()
    
    # Configure logging
    if args.debug:
        logger.setLevel(logging.DEBUG)
    
    # Create and run the server
    server = create_server(
        host=args.host,
        port=args.port,
        verify_connectivity=not args.no_verify
    )
    
    server_thread = run_server(server)
    
    # If running in foreground, keep the main thread alive
    if args.foreground:
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Server interrupted by user")


if __name__ == "__main__":
    main()
