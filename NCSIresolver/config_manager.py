#!/usr/bin/env python3
"""
NCSI Resolver Configuration Manager

This module handles loading, accessing, and validating configuration settings
for all NCSI Resolver components.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('config_manager')

# Default configuration file paths to check
DEFAULT_CONFIG_PATHS = [
    # Current directory
    "config.json",
    # Script directory
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json"),
    # NCSIresolver subdirectory (used for install)
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "NCSIresolver", "config.json"),
    # Parent directory (repository root)
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config.json"),
    # Installation directory (if different from script directory)
    os.path.join(os.environ.get('PROGRAMFILES', r"C:\Program Files"), "NCSI Resolver", "config.json"),
    # Custom installation directory 
    r"C:\NCSI_Resolver\config.json"
]

# Default configuration values if no config file is found
DEFAULT_CONFIG = {
    "version": "0.7.2",
    "description": "Windows Network Connectivity Status Indicator Resolver",
    "installation": {
        "default_dir": "C:\\Program Files\\NCSI Resolver",
        "service_name": "NCSIResolver",
        "service_display_name": "NCSI Resolver Service",
        "service_description": "Resolves Windows Network Connectivity Status Indicator issues by serving local NCSI test endpoints."
    },
    "server": {
        "default_port": 80,
        "ncsi_text": "Microsoft Connect Test",
        "hosts_file_path": "C:\\Windows\\System32\\drivers\\etc\\hosts",
        "default_ncsi_host": "www.msftconnecttest.com",
        "backup_dir": "%LOCALAPPDATA%\\NCSI_Resolver\\Backups"
    },
    "registry": {
        "ncsi_key": "SYSTEM\\CurrentControlSet\\Services\\NlaSvc\\Parameters\\Internet",
        "values": {
            "ActiveWebProbeHost": {
                "type": "REG_SZ",
                "description": "Host for NCSI connectivity test"
            },
            "ActiveWebProbePath": {
                "type": "REG_SZ",
                "description": "Path for NCSI connectivity test",
                "default": "/ncsi.txt"
            }
        }
    },
    "connectivity_checks": {
        "ping_targets": ["8.8.8.8", "1.1.1.1", "4.2.2.1"],
        "dns_targets": [
            {"hostname": "www.google.com", "expected_ip": None},
            {"hostname": "www.cloudflare.com", "expected_ip": None}
        ],
        "http_targets": [
            "http://www.gstatic.com/generate_204",
            "http://connectivitycheck.platform.hicloud.com/generate_204"
        ],
        "timeout": 2.0,
        "check_interval": 15
    },
    "logging": {
        "default_level": "INFO",
        "log_file": "ncsi_resolver.log",
        "max_size": 5242880,
        "backup_count": 3
    }
}

class ConfigManager:
    """Configuration manager for NCSI Resolver."""
    
    _instance = None
    _config = None
    _config_path = None
    
    def __new__(cls):
        """Singleton pattern to ensure only one configuration manager exists."""
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _expand_path(self, path: str) -> str:
        """Expand environment variables in a path."""
        # Replace %VAR% style variables
        for env_var, value in os.environ.items():
            var_placeholder = f"%{env_var}%"
            if var_placeholder in path:
                path = path.replace(var_placeholder, value)
        
        # Use os.path.expandvars for $VAR style variables
        path = os.path.expandvars(path)
        
        return path
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file or use defaults.
        
        Returns:
            Dict: Configuration dictionary
        """
        # Try to find and load a configuration file
        for path in DEFAULT_CONFIG_PATHS:
            expanded_path = self._expand_path(path)
            if os.path.exists(expanded_path):
                try:
                    with open(expanded_path, 'r') as f:
                        self._config = json.load(f)
                    self._config_path = expanded_path
                    logger.info(f"Loaded configuration from {expanded_path}")
                    return self._config
                except Exception as e:
                    logger.warning(f"Error loading config from {expanded_path}: {e}")
        
        # If no config file found, use defaults
        logger.warning("No configuration file found, using default values")
        self._config = DEFAULT_CONFIG
        self._config_path = None
        return self._config
    
    def save_config(self, path: Optional[str] = None) -> bool:
        """
        Save the current configuration to a file.
        
        Args:
            path: Path to save the configuration file
            
        Returns:
            bool: True if successful, False otherwise
        """
        if path is None:
            if self._config_path is not None:
                path = self._config_path
            else:
                # Use the first default path as a fallback
                path = DEFAULT_CONFIG_PATHS[0]
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            
            with open(path, 'w') as f:
                json.dump(self._config, f, indent=2)
            
            self._config_path = path
            logger.info(f"Saved configuration to {path}")
            return True
        except Exception as e:
            logger.error(f"Error saving config to {path}: {e}")
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Get a configuration value using a dot-separated path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            default: Default value to return if the key is not found
            
        Returns:
            Value from the configuration, or default if not found
        """
        if self._config is None:
            self._load_config()
            
        # Split the path into components
        keys = key_path.split('.')
        
        # Start at the root of the config
        value = self._config
        
        # Navigate through the keys
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.debug(f"Configuration key '{key_path}' not found, using default: {default}")
            return default
    
    def update(self, key_path: str, value: Any, save: bool = False) -> bool:
        """
        Update a configuration value using a dot-separated path.
        
        Args:
            key_path: Dot-separated path to the configuration value
            value: New value to set
            save: Whether to save the configuration to file after updating
            
        Returns:
            bool: True if successful, False otherwise
        """
        if self._config is None:
            self._load_config()
            
        # Split the path into components
        keys = key_path.split('.')
        
        # Navigate to the parent object
        parent = self._config
        try:
            for key in keys[:-1]:
                parent = parent[key]
            
            # Update the value
            parent[keys[-1]] = value
            
            # Save if requested
            if save and self._config_path is not None:
                return self.save_config()
            
            return True
        except (KeyError, TypeError) as e:
            logger.error(f"Error updating config key '{key_path}': {e}")
            return False
    
    def get_all(self) -> Dict[str, Any]:
        """
        Get the entire configuration dictionary.
        
        Returns:
            Dict: The complete configuration
        """
        if self._config is None:
            self._load_config()
        
        return self._config
    
    def get_path(self) -> Optional[str]:
        """
        Get the path to the loaded configuration file.
        
        Returns:
            str: Path to the configuration file, or None if using defaults
        """
        return self._config_path

# Create a global instance
config = ConfigManager()

# Function to get the configuration manager
def get_config() -> ConfigManager:
    """
    Get the configuration manager instance.
    
    Returns:
        ConfigManager: Configuration manager instance
    """
    return config

if __name__ == "__main__":
    # If run directly, print the current configuration
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="NCSI Resolver Configuration Manager")
    parser.add_argument("--get", help="Get a configuration value (dot-separated path)")
    parser.add_argument("--set", help="Set a configuration value (dot-separated path)")
    parser.add_argument("--value", help="Value to set")
    parser.add_argument("--save", help="Save configuration to the specified path")
    parser.add_argument("--dump", action="store_true", help="Dump the entire configuration")
    
    args = parser.parse_args()
    
    if args.get:
        value = config.get(args.get)
        print(f"{args.get} = {value}")
    elif args.set and args.value:
        # Try to convert value to appropriate type
        try:
            # Try as number
            if args.value.isdigit():
                value = int(args.value)
            elif args.value.replace('.', '', 1).isdigit():
                value = float(args.value)
            # Try as boolean
            elif args.value.lower() in ('true', 'false'):
                value = args.value.lower() == 'true'
            # Try as null/None
            elif args.value.lower() in ('null', 'none'):
                value = None
            # Default to string
            else:
                value = args.value
                
            success = config.update(args.set, value, save=bool(args.save))
            if success:
                print(f"Updated {args.set} = {value}")
            else:
                print(f"Failed to update {args.set}")
                sys.exit(1)
        except Exception as e:
            print(f"Error setting value: {e}")
            sys.exit(1)
    elif args.save:
        success = config.save_config(args.save)
        if success:
            print(f"Configuration saved to {args.save}")
        else:
            print("Failed to save configuration")
            sys.exit(1)
    elif args.dump:
        import json
        print(json.dumps(config.get_all(), indent=2))
    else:
        parser.print_help()
