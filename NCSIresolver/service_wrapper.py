#!/usr/bin/env python3
"""
NCSI Resolver Service Wrapper

This script is used to start the NCSI server as a Windows service.
It loads configuration at runtime instead of being generated during installation.
"""

import json
import logging
import os
import socket
import sys
import traceback
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Get the current directory (where this script is located)
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# Set up logging to file
LOGS_DIR = os.path.join(CURRENT_DIR, "Logs")
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR, exist_ok=True)

LOG_PATH = os.path.join(LOGS_DIR, "ncsi_resolver.log")
DEBUG_LOG_PATH = os.path.join(LOGS_DIR, "ncsi_debug.log")

# Set up enhanced logging with both normal and debug logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('ncsi_service')

# Add a separate debug logger
debug_handler = logging.FileHandler(DEBUG_LOG_PATH)
debug_handler.setLevel(logging.DEBUG)
debug_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(debug_handler)
logger.setLevel(logging.DEBUG)  # Set to DEBUG for more detailed logging

# Enhanced configuration loading
def load_config():
    """Load configuration from file or registry with detailed logging."""
    # Define search paths with priorities
    config_paths = [
        os.path.join(CURRENT_DIR, "config.json"),
        os.path.join(os.environ.get('PROGRAMFILES', r"C:\Program Files"), "NCSI Resolver", "config.json"),
        r"C:\NCSI_Resolver\config.json"
    ]
    
    # Log search process
    logger.debug(f"Current directory: {CURRENT_DIR}")
    logger.debug(f"Searching for configuration in: {', '.join(config_paths)}")
    
    # First try loading from config files
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    config = json.load(f)
                logger.info(f"Loaded configuration from {path}")
                logger.debug(f"Configuration contents: {config}")
                return config
            except Exception as e:
                logger.warning(f"Error loading config from {path}: {e}")
                logger.debug(f"Error details: {traceback.format_exc()}")
    
    # If no config file found, try to check registry
    try:
        logger.debug("Attempting to check registry for port configuration")
        import winreg
        registry_key = r"SYSTEM\CurrentControlSet\Services\NlaSvc\Parameters\Internet"
        reg_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            registry_key,
            0,
            winreg.KEY_READ
        )
        
        # Try to read ActiveWebProbeHost
        try:
            host_value, _ = winreg.QueryValueEx(reg_key, "ActiveWebProbeHost")
            logger.debug(f"Found registry ActiveWebProbeHost: {host_value}")
            
            # Check if port is specified in the host value
            if ':' in host_value:
                host, port_str = host_value.split(':', 1)
                if port_str.isdigit():
                    port = int(port_str)
                    logger.debug(f"Extracted port {port} from registry host value")
                    
                    # Return a config dictionary with the extracted port
                    return {
                        "server": {
                            "default_port": port,
                            "ncsi_text": "Microsoft Connect Test"
                        }
                    }
        except FileNotFoundError:
            logger.debug("Registry key ActiveWebProbeHost not found")
            pass
            
        winreg.CloseKey(reg_key)
    except Exception as e:
        logger.debug(f"Error checking registry: {e}")
        logger.debug(f"Error details: {traceback.format_exc()}")
    
    # Default configuration if nothing else worked
    logger.warning("No configuration found, using default values")
    return {
        "server": {
            "default_port": 80,
            "ncsi_text": "Microsoft Connect Test"
        }
    }

# Enhanced HTML content loading with detailed logging
def load_html_content():
    """Load HTML content from file with detailed logging."""
    html_path = os.path.join(CURRENT_DIR, "redirect.html")
    logger.debug(f"Looking for HTML content at: {html_path}")
    
    if os.path.exists(html_path):
        try:
            with open(html_path, 'rb') as f:
                content = f.read()
            logger.info(f"Loaded HTML content from {html_path}")
            logger.debug(f"HTML content size: {len(content)} bytes")
            return content
        except Exception as e:
            logger.warning(f"Error loading HTML from {html_path}: {e}")
            logger.debug(f"Error details: {traceback.format_exc()}")
    
    # Default HTML content if file not found
    logger.warning("No HTML file found, using default content")
    return b"""<!DOCTYPE html>
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

# Load configuration and content
logger.debug("Starting configuration loading process")
config = load_config()
REDIRECT_HTML = load_html_content()
NCSI_TEXT = config.get("server", {}).get("ncsi_text", "Microsoft Connect Test").encode('utf-8')

class NCSIHandler(BaseHTTPRequestHandler):
    """HTTP request handler for NCSI requests."""
    
    def log_message(self, format, *args):
        """Log messages to our logger instead of stderr."""
        logger.info(format % args)
        
    def do_GET(self):
        """Handle GET requests."""
        client_ip = self.client_address[0]
        logger.info(f"Request from {client_ip} for {self.path}")
        
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
    """Get the local IP address of the machine."""
    try:
        # Create a socket to determine the local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        logger.debug(f"Detected local IP: {local_ip}")
        return local_ip
    except Exception as e:
        logger.error(f"Failed to get local IP: {e}")
        logger.debug(f"IP detection error details: {traceback.format_exc()}")
        return "0.0.0.0"  # Fall back to all interfaces

# Enhanced port binding with retries and detailed error reporting
def bind_server(host, port, max_retries=3):
    """
    Attempt to bind the server to the specified host and port with retries.
    
    Returns:
        HTTPServer or None if all attempts fail
    """
    # FIX: Always try to bind to all interfaces first
    logger.debug(f"Attempting to bind server to 0.0.0.0:{port} (all interfaces)")
    
    for attempt in range(max_retries):
        try:
            # FIX: Always bind to 0.0.0.0 (all interfaces) for maximum compatibility
            server = HTTPServer(("0.0.0.0", port), NCSIHandler)
            logger.info(f"Successfully bound server to 0.0.0.0:{port} on attempt {attempt+1}")
            return server
        except Exception as e:
            logger.error(f"Failed to bind to 0.0.0.0:{port} on attempt {attempt+1}: {e}")
            logger.debug(f"Binding error details: {traceback.format_exc()}")
            
            # If binding to all interfaces fails, try the specific host
            if attempt == max_retries - 1 and host != "0.0.0.0":
                try:
                    logger.debug(f"Trying to bind to specific interface {host}:{port} as fallback")
                    server = HTTPServer((host, port), NCSIHandler)
                    logger.info(f"Successfully bound server to {host}:{port} as fallback")
                    return server
                except Exception as e2:
                    logger.error(f"Failed to bind to fallback {host}:{port}: {e2}")
                    logger.debug(f"Fallback binding error details: {traceback.format_exc()}")
            
            # Add delay between attempts
            if attempt < max_retries - 1:
                time.sleep(1)
    
    return None

# Main service code with enhanced error handling
try:
    logger.info("Starting NCSI Resolver service...")
    
    # Get local IP or use all interfaces
    host = get_local_ip()
    
    # Get port from configuration
    port = config.get("server", {}).get("default_port", 80)
    
    # Ensure port is valid
    if not isinstance(port, int) or port <= 0 or port > 65535:
        logger.warning(f"Port value '{port}' is not valid, using default port 80")
        port = 80
    
    # FIX: Log both binding options for transparency
    logger.info(f"Will attempt to bind to all interfaces (0.0.0.0:{port}) first")
    logger.info(f"Detected local IP {host}:{port} will be used as fallback if needed")
    
    # Try to bind the server with retries
    httpd = bind_server(host, port)
    
    if httpd:
        # Server bound successfully
        server_host, server_port = httpd.server_address
        logger.info(f"NCSI Resolver server running on {server_host}:{server_port}")
        
        # Test socket is actually listening
        try:
            # FIX: Try to connect to both localhost and the specific IP
            logger.debug("Verifying connection to server via localhost")
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_socket.connect(("127.0.0.1", port))
            test_socket.close()
            logger.debug(f"Successfully verified socket is listening on localhost:{port}")
            
            logger.debug(f"Verifying connection to server via local IP {host}")
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.settimeout(1)
            test_socket.connect((host, port))
            test_socket.close()
            logger.debug(f"Successfully verified socket is listening on {host}:{port}")
        except Exception as e:
            logger.warning(f"Socket verification failed: {e}")
            logger.debug(f"Socket verification error details: {traceback.format_exc()}")
            logger.info("Socket verification failed but continuing anyway, service may still work")
        
        # Run the server
        httpd.serve_forever()
    else:
        # Failed to bind server
        logger.error(f"Failed to bind server after multiple attempts")
        sys.exit(1)
    
except Exception as e:
    logger.error(f"Error starting NCSI Resolver service: {e}")
    logger.debug(f"Service error details: {traceback.format_exc()}")
    sys.exit(1)
