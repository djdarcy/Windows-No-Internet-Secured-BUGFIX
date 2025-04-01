#!/usr/bin/env python3
"""
NCSI Resolver Security Monitoring

This module adds security monitoring capabilities to the NCSI Resolver service,
tracking connection attempts and detecting potential scanning or probing.
"""

import logging
import os
import socket
import time
import json
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

# Set up logging
logger = logging.getLogger('security_monitor')

class SecurityMonitor:
    """Security monitoring for NCSI Resolver service."""
    
    def __init__(self, log_dir: str, max_connections_per_ip: int = 20, 
                 time_window: int = 60, scan_threshold: int = 5,
                 excluded_ips: Optional[List[str]] = None):
        """
        Initialize the security monitor.
        
        Args:
            log_dir: Directory for security logs
            max_connections_per_ip: Maximum connections per IP in time window before flagging
            time_window: Time window in seconds for rate limiting
            scan_threshold: Number of different paths to flag as scanning
            excluded_ips: IPs to exclude from monitoring (e.g., localhost)
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        
        # Configure security log file
        self.security_log_path = os.path.join(log_dir, "security.log")
        self.detailed_log_path = os.path.join(log_dir, "connections.json")
        
        # Security parameters
        self.max_connections_per_ip = max_connections_per_ip
        self.time_window = time_window
        self.scan_threshold = scan_threshold
        self.excluded_ips = excluded_ips or ["127.0.0.1", "::1", "localhost"]
        
        # Connection tracking
        self.connections = defaultdict(list)  # IP -> list of connection timestamps
        self.paths_accessed = defaultdict(set)  # IP -> set of paths accessed
        self.detailed_logs = []  # List of connection details
        self.max_detailed_logs = 1000  # Maximum number of detailed logs to keep in memory
        
        # Load existing logs if available
        self._load_logs()
        
        # Set up logging
        self._setup_logging()
        
        logger.info(f"Security monitoring initialized (max: {max_connections_per_ip} conn/IP/{time_window}s, "
                   f"scan threshold: {scan_threshold} paths)")
    
    def _setup_logging(self):
        """Set up security logging."""
        # Configure file handler for security log
        file_handler = logging.FileHandler(self.security_log_path)
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        
        # Add handler to logger
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.setLevel(logging.INFO)
    
    def _load_logs(self):
        """Load existing detailed logs if available."""
        try:
            if os.path.exists(self.detailed_log_path):
                with open(self.detailed_log_path, 'r') as f:
                    self.detailed_logs = json.load(f)
                logger.info(f"Loaded {len(self.detailed_logs)} detailed connection logs")
        except Exception as e:
            logger.warning(f"Error loading detailed logs: {e}")
    
    def _save_logs(self):
        """Save detailed logs to file."""
        try:
            # Trim logs if exceeding max size
            if len(self.detailed_logs) > self.max_detailed_logs:
                self.detailed_logs = self.detailed_logs[-self.max_detailed_logs:]
                
            with open(self.detailed_log_path, 'w') as f:
                json.dump(self.detailed_logs, f, indent=2)
        except Exception as e:
            logger.warning(f"Error saving detailed logs: {e}")
    
    def _clean_old_connections(self):
        """Remove connection records older than time window."""
        current_time = time.time()
        for ip, timestamps in list(self.connections.items()):
            # Filter out timestamps older than time window
            self.connections[ip] = [t for t in timestamps if current_time - t <= self.time_window]
            
            # Remove empty entries
            if not self.connections[ip]:
                del self.connections[ip]
    
    def _is_scanning(self, ip: str) -> bool:
        """
        Determine if an IP is scanning based on number of different paths accessed.
        
        Args:
            ip: IP address to check
            
        Returns:
            bool: True if scanning behavior detected
        """
        return len(self.paths_accessed.get(ip, set())) >= self.scan_threshold
    
    def _is_rate_limited(self, ip: str) -> bool:
        """
        Check if an IP has exceeded the maximum connection rate.
        
        Args:
            ip: IP address to check
            
        Returns:
            bool: True if rate limited
        """
        return len(self.connections.get(ip, [])) >= self.max_connections_per_ip
    
    def log_connection(self, ip: str, path: str, method: str, 
                      headers: Dict[str, str], response_code: int) -> Dict[str, any]:
        """
        Log a connection and check for suspicious activity.
        
        Args:
            ip: Client IP address
            path: Requested path
            method: HTTP method (GET, POST, etc.)
            headers: HTTP headers
            response_code: HTTP response code
            
        Returns:
            Dict containing security check results
        """
        # Skip excluded IPs
        if ip in self.excluded_ips:
            return {"excluded": True}
        
        # Clean old connections first
        self._clean_old_connections()
        
        # Record connection
        current_time = time.time()
        self.connections[ip].append(current_time)
        self.paths_accessed[ip].add(path)
        
        # Check for rate limiting
        rate_limited = self._is_rate_limited(ip)
        
        # Check for scanning behavior
        scanning = self._is_scanning(ip)
        
        # Create log entry
        timestamp = datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M:%S')
        log_entry = {
            "timestamp": timestamp,
            "ip": ip,
            "path": path,
            "method": method,
            "headers": dict(headers),
            "response_code": response_code,
            "rate_limited": rate_limited,
            "scanning": scanning,
            "connection_count": len(self.connections[ip]),
            "unique_paths": list(self.paths_accessed[ip])
        }
        
        # Add to detailed logs
        self.detailed_logs.append(log_entry)
        
        # Save logs periodically (every 20 entries)
        if len(self.detailed_logs) % 20 == 0:
            self._save_logs()
        
        # Log suspicious activity
        if rate_limited or scanning:
            alert_level = logging.WARNING
            alert_type = []
            
            if rate_limited:
                alert_type.append("RATE LIMITED")
            if scanning:
                alert_type.append("SCANNING")
                
            alert_msg = f"{', '.join(alert_type)} - {ip} - {method} {path} - " \
                       f"{len(self.connections[ip])} req/{self.time_window}s, " \
                       f"{len(self.paths_accessed[ip])} unique paths"
                       
            logger.log(alert_level, alert_msg)
        
        # Return check results
        return {
            "rate_limited": rate_limited,
            "scanning": scanning,
            "connection_count": len(self.connections[ip]),
            "unique_paths": len(self.paths_accessed[ip])
        }
    
    def get_connection_stats(self) -> Dict[str, any]:
        """
        Get connection statistics.
        
        Returns:
            Dict containing connection stats
        """
        # Clean old connections first
        self._clean_old_connections()
        
        return {
            "active_ips": len(self.connections),
            "total_connections": sum(len(timestamps) for timestamps in self.connections.values()),
            "suspicious_ips": [
                {
                    "ip": ip,
                    "connection_count": len(timestamps),
                    "unique_paths": len(self.paths_accessed.get(ip, set())),
                    "rate_limited": len(timestamps) >= self.max_connections_per_ip,
                    "scanning": len(self.paths_accessed.get(ip, set())) >= self.scan_threshold
                }
                for ip, timestamps in self.connections.items()
                if (len(timestamps) >= self.max_connections_per_ip or 
                    len(self.paths_accessed.get(ip, set())) >= self.scan_threshold)
            ],
            "excluded_ips": self.excluded_ips
        }
    
    def get_recent_connections(self, limit: int = 50) -> List[Dict[str, any]]:
        """
        Get recent connection logs.
        
        Args:
            limit: Maximum number of logs to return
            
        Returns:
            List of recent connection logs
        """
        return self.detailed_logs[-limit:] if self.detailed_logs else []

# Create function to integrate with NCSIHandler
def enhance_with_security_monitoring(handler_class, logs_dir):
    """
    Enhance an HTTPRequestHandler class with security monitoring.
    
    Args:
        handler_class: The HTTPRequestHandler class to enhance
        logs_dir: Directory for security logs
        
    Returns:
        Enhanced handler class
    """
    # Create security monitor instance
    security_monitor = SecurityMonitor(logs_dir)
    
    # Store original do_GET method
    original_do_GET = handler_class.do_GET
    
    # Define enhanced do_GET method
    def enhanced_do_GET(self):
        # Call original method
        original_do_GET(self)
        
        # Log connection for security monitoring
        client_ip = self.client_address[0]
        path = self.path
        method = self.command
        
        # Extract headers
        headers = {k: v for k, v in self.headers.items()}
        
        # Get response code (if available)
        response_code = getattr(self, 'send_response_only', lambda x: x)(200)
        
        # Log the connection
        security_result = security_monitor.log_connection(
            ip=client_ip,
            path=path,
            method=method,
            headers=headers,
            response_code=response_code
        )
        
        # Add security headers to response if needed
        if security_result.get("rate_limited", False):
            # If we detect rate limiting, we could add headers or modify response
            # but for now we just log it
            pass
    
    # Replace original method with enhanced one
    handler_class.do_GET = enhanced_do_GET
    
    # Add security monitor as class attribute
    handler_class.security_monitor = security_monitor
    
    return handler_class

# Example usage
if __name__ == "__main__":
    # Create a test security monitor
    monitor = SecurityMonitor("./logs")
    
    # Simulate some connections
    monitor.log_connection("192.168.1.100", "/connecttest.txt", "GET", {"User-Agent": "Test"}, 200)
    monitor.log_connection("192.168.1.100", "/ncsi.txt", "GET", {"User-Agent": "Test"}, 200)
    monitor.log_connection("192.168.1.101", "/connecttest.txt", "GET", {"User-Agent": "Test"}, 200)
    
    # Simulate scanning behavior
    for i in range(10):
        monitor.log_connection("192.168.1.200", f"/test{i}.txt", "GET", {"User-Agent": "Scanner"}, 404)
    
    # Get and print stats
    stats = monitor.get_connection_stats()
    print(json.dumps(stats, indent=2))
