#!/usr/bin/env python3
"""
NCSI Resolver Log Cleanup Utility

This script moves any log files from the installation directory to the Logs directory.
"""

import os
import shutil
import sys
from pathlib import Path

def cleanup_logs(install_dir=None):
    """
    Move log files from installation directory to Logs directory.
    
    Args:
        install_dir: Installation directory (default: auto-detect)
    """
    # Determine installation directory if not specified
    if not install_dir:
        if os.path.exists(r"C:\NCSI_Resolver"):
            install_dir = r"C:\NCSI_Resolver"
        elif os.path.exists(r"C:\Program Files\NCSI Resolver"):
            install_dir = r"C:\Program Files\NCSI Resolver"
        else:
            print("NCSI Resolver installation directory not found.")
            return False
    
    # Ensure install_dir exists
    if not os.path.exists(install_dir):
        print(f"Installation directory {install_dir} does not exist.")
        return False
    
    # Create Logs directory if it doesn't exist
    logs_dir = os.path.join(install_dir, "Logs")
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir, exist_ok=True)
        print(f"Created Logs directory: {logs_dir}")
    
    # Find log files in installation directory
    log_files = []
    for filename in os.listdir(install_dir):
        if filename.endswith(".log"):
            log_files.append(filename)
    
    if not log_files:
        print("No log files found in installation directory.")
        return True
    
    # Move log files to Logs directory
    moved_files = 0
    for filename in log_files:
        src_path = os.path.join(install_dir, filename)
        dst_path = os.path.join(logs_dir, filename)
        
        try:
            shutil.move(src_path, dst_path)
            print(f"Moved {filename} to Logs directory")
            moved_files += 1
        except Exception as e:
            print(f"Error moving {filename}: {e}")
    
    print(f"Moved {moved_files} of {len(log_files)} log files to Logs directory.")
    return True

if __name__ == "__main__":
    # Get installation directory from command line if provided
    install_dir = sys.argv[1] if len(sys.argv) > 1 else None
    
    print("NCSI Resolver Log Cleanup Utility")
    print("=================================")
    
    if cleanup_logs(install_dir):
        print("Log cleanup completed successfully.")
    else:
        print("Log cleanup failed.")
        sys.exit(1)
