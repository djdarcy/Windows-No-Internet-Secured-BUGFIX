#!/usr/bin/env python3
"""
NCSI Resolver Logging Module

This module provides enhanced logging functionality with verbosity levels
for all NCSI Resolver components.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Dict, List, Optional, Union

def setup_logger(name: str, 
                 verbosity: int = 0, 
                 log_file: Optional[str] = None,
                 max_size: int = 5242880,  # 5MB
                 backup_count: int = 3) -> logging.Logger:
    """
    Set up a logger with configurable verbosity levels.
    
    Args:
        name: Logger name
        verbosity: Verbosity level (0=ERROR, 1=INFO, 2=WARNING, 3=DEBUG)
        log_file: Path to log file (if None, no file logging)
        max_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        logging.Logger: Configured logger
    """
    # Map verbosity level to logging level
    level_map = {
        0: logging.ERROR,     # Default, minimal output
        1: logging.INFO,      # -v, standard information
        2: logging.WARNING,   # -vv, include warnings
        3: logging.DEBUG      # -vvv, include debug info
    }
    
    # Get the appropriate logging level
    log_level = level_map.get(verbosity, logging.INFO)
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)
    
    # Remove any existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    
    # Add console handler to logger
    logger.addHandler(console_handler)
    
    # Add file handler if log file specified
    if log_file:
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
            
            # Create file handler
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_size, 
                backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            
            # Add file handler to logger
            logger.addHandler(file_handler)
        except Exception as e:
            # Log to console only if file handler fails
            logger.error(f"Failed to set up log file {log_file}: {e}")
    
    return logger

class VerbosityAction(logging.Logger):
    """Logger class with verbosity-aware methods."""
    
    def __init__(self, name, level=logging.NOTSET):
        super().__init__(name, level)
        self.verbosity = 0
    
    def set_verbosity(self, verbosity: int) -> None:
        """Set the verbosity level."""
        self.verbosity = verbosity
    
    def v(self, msg, *args, **kwargs):
        """Log at verbosity level 1 (-v)."""
        if self.verbosity >= 1:
            self.info(msg, *args, **kwargs)
    
    def vv(self, msg, *args, **kwargs):
        """Log at verbosity level 2 (-vv)."""
        if self.verbosity >= 2:
            self.warning(msg, *args, **kwargs)
    
    def vvv(self, msg, *args, **kwargs):
        """Log at verbosity level 3 (-vvv)."""
        if self.verbosity >= 3:
            self.debug(msg, *args, **kwargs)

# Register the custom logger class
logging.setLoggerClass(VerbosityAction)

def get_logger(name: str, 
              verbosity: int = 0, 
              log_file: Optional[str] = None,
              max_size: int = 5242880,
              backup_count: int = 3) -> logging.Logger:
    """
    Get a logger with the specified configuration.
    
    Args:
        name: Logger name
        verbosity: Verbosity level (0=ERROR, 1=INFO, 2=WARNING, 3=DEBUG)
        log_file: Path to log file (if None, no file logging)
        max_size: Maximum size of log file before rotation
        backup_count: Number of backup log files to keep
        
    Returns:
        logging.Logger: Configured logger
    """
    logger = setup_logger(name, verbosity, log_file, max_size, backup_count)
    
    # Set verbosity if it's our custom class
    if isinstance(logger, VerbosityAction):
        logger.set_verbosity(verbosity)
    
    return logger

# Example usage
if __name__ == "__main__":
    # Test the logger
    verbosity = 3  # Very verbose
    test_logger = get_logger("test", verbosity, "test.log")
    
    test_logger.error("This is an error message (always shown)")
    test_logger.info("This is an info message (shown at -v)")
    test_logger.warning("This is a warning message (shown at -vv)")
    test_logger.debug("This is a debug message (shown at -vvv)")
    
    # Test the verbosity-specific methods
    if isinstance(test_logger, VerbosityAction):
        test_logger.v("This is a verbosity level 1 message (-v)")
        test_logger.vv("This is a verbosity level 2 message (-vv)")
        test_logger.vvv("This is a verbosity level 3 message (-vvv)")
