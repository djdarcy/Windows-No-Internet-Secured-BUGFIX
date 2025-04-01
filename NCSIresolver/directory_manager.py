#!/usr/bin/env python3
"""
NCSI Resolver Directory Manager

This module provides utilities for managing directories and junction points
to improve navigation between related directories (e.g., installation and backup).
"""

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

# Configure logging
logger = logging.getLogger('directory_manager')

class DirectoryManager:
    """
    Manages directories and junction points for easier navigation.
    """
    
    def __init__(self, base_dir: str = None):
        """
        Initialize the directory manager.
        
        Args:
            base_dir: Base directory for operations (defaults to current directory)
        """
        self.base_dir = base_dir or os.getcwd()
        
        # Ensure base directory exists
        os.makedirs(self.base_dir, exist_ok=True)
        
        # Track created directories and junction points
        self.directories = []
        self.junctions = []
    
    def create_directory(self, path: str, description: str = None) -> str:
        """
        Create a directory if it doesn't exist.
        
        Args:
            path: Directory path (absolute or relative to base_dir)
            description: Optional description of the directory purpose
            
        Returns:
            str: Full path to the created directory
        """
        # Resolve full path
        if os.path.isabs(path):
            full_path = path
        else:
            full_path = os.path.join(self.base_dir, path)
            
        # Create directory if it doesn't exist
        if not os.path.exists(full_path):
            try:
                os.makedirs(full_path, exist_ok=True)
                logger.info(f"Created directory: {full_path}")
            except Exception as e:
                logger.error(f"Failed to create directory {full_path}: {e}")
                return None
        
        # Track the directory
        self.directories.append({
            'path': full_path,
            'description': description
        })
            
        return full_path
    
    def create_junction_pair(self, dir1: str, dir2: str, 
                            link1_name: str = None, link2_name: str = None) -> bool:
        """
        Create junction points between two directories for easy navigation.
        
        Args:
            dir1: First directory path
            dir2: Second directory path
            link1_name: Name for the junction in dir1 pointing to dir2
            link2_name: Name for the junction in dir2 pointing to dir1
            
        Returns:
            bool: True if both junctions were created successfully
        """
        # Ensure both directories exist
        dir1 = self.create_directory(dir1)
        dir2 = self.create_directory(dir2)
        
        if not dir1 or not dir2:
            return False
        
        # Use directory names if link names not specified
        if not link1_name:
            link1_name = os.path.basename(dir2)
        if not link2_name:
            link2_name = os.path.basename(dir1)
        
        # Create junction points in both directions
        success1 = self.create_junction(dir1, dir2, link1_name)
        success2 = self.create_junction(dir2, dir1, link2_name)
        
        return success1 and success2
    
    def create_junction(self, source_dir: str, target_dir: str, link_name: str = None) -> bool:
        """
        Create a junction point (symbolic link on Windows).
        
        Args:
            source_dir: Directory containing the junction
            target_dir: Directory the junction points to
            link_name: Name for the junction (defaults to target's basename)
            
        Returns:
            bool: True if junction was created successfully
        """
        # Resolve full paths
        if not os.path.isabs(source_dir):
            source_dir = os.path.join(self.base_dir, source_dir)
        if not os.path.isabs(target_dir):
            target_dir = os.path.join(self.base_dir, target_dir)
            
        # Use target's basename if link_name not specified
        if not link_name:
            link_name = os.path.basename(target_dir)
            
        # Full path for the junction
        junction_path = os.path.join(source_dir, link_name)
        
        # Check if junction already exists
        if os.path.exists(junction_path):
            logger.info(f"Junction already exists: {junction_path}")
            
            # Track existing junction
            self.junctions.append({
                'source': source_dir,
                'target': target_dir,
                'name': link_name,
                'path': junction_path
            })
            
            return True
            
        try:
            # Create the junction using mklink command
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", junction_path, target_dir],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logger.info(f"Created junction from {junction_path} to {target_dir}")
                
                # Track created junction
                self.junctions.append({
                    'source': source_dir,
                    'target': target_dir,
                    'name': link_name,
                    'path': junction_path
                })
                
                return True
            else:
                logger.error(f"Failed to create junction: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating junction: {e}")
            return False
    
    def setup_standard_directories(self, app_name: str) -> Dict[str, str]:
        """
        Create a standard set of directories with junction points.
        
        Args:
            app_name: Application name for directory naming
            
        Returns:
            Dict[str, str]: Dictionary of created directories
        """
        # Create application directories
        install_dir = self.create_directory(
            self.base_dir, 
            f"{app_name} installation directory"
        )
        
        # Create local app data directory for backups
        local_app_data = os.environ.get('LOCALAPPDATA', os.path.expanduser('~'))
        backup_dir = self.create_directory(
            os.path.join(local_app_data, app_name, "Backups"),
            f"{app_name} backup directory"
        )
        
        # Create logs directory
        logs_dir = self.create_directory(
            os.path.join(local_app_data, app_name, "Logs"),
            f"{app_name} log files"
        )
        
        # Create config directory
        config_dir = self.create_directory(
            os.path.join(local_app_data, app_name, "Config"),
            f"{app_name} configuration files"
        )
        
        # Create junction points for easy navigation
        self.create_junction_pair(install_dir, backup_dir, "Backups", "Installation")
        self.create_junction_pair(install_dir, logs_dir, "Logs", "Installation")
        self.create_junction_pair(install_dir, config_dir, "Config", "Installation")
        self.create_junction_pair(backup_dir, logs_dir, "Logs", "Backups")
        self.create_junction_pair(backup_dir, config_dir, "Config", "Backups")
        
        # Return the directory mapping
        return {
            'install_dir': install_dir,
            'backup_dir': backup_dir,
            'logs_dir': logs_dir,
            'config_dir': config_dir
        }
    
    def check_junction(self, junction_path: str) -> Optional[str]:
        """
        Check if a path is a junction point and where it points to.
        
        Args:
            junction_path: Path to check
            
        Returns:
            Optional[str]: Target path if it's a junction, None otherwise
        """
        if not os.path.exists(junction_path):
            return None
            
        try:
            # On Windows, use fsutil to check if it's a junction
            result = subprocess.run(
                ["fsutil", "reparsepoint", "query", junction_path],
                check=False,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0 and "Mount Point" in result.stdout:
                # Extract the target from the output
                for line in result.stdout.splitlines():
                    if "Substitute Name:" in line:
                        target = line.split(":", 1)[1].strip()
                        return target.strip("\\?\\")
            
            return None
                
        except Exception as e:
            logger.error(f"Error checking junction: {e}")
            return None
    
    def list_directories(self) -> List[Dict[str, str]]:
        """
        List all tracked directories.
        
        Returns:
            List[Dict[str, str]]: List of directory information
        """
        return self.directories
    
    def list_junctions(self) -> List[Dict[str, str]]:
        """
        List all tracked junction points.
        
        Returns:
            List[Dict[str, str]]: List of junction information
        """
        return self.junctions
    
    def remove_junction(self, junction_path: str) -> bool:
        """
        Remove a junction point.
        
        Args:
            junction_path: Path to the junction
            
        Returns:
            bool: True if junction was removed successfully
        """
        if not os.path.exists(junction_path):
            logger.warning(f"Junction not found: {junction_path}")
            return False
            
        try:
            # Check if it's actually a junction
            target = self.check_junction(junction_path)
            if not target:
                logger.warning(f"Not a junction point: {junction_path}")
                return False
                
            # Remove the junction - use rmdir to remove just the link, not the target
            os.rmdir(junction_path)
            logger.info(f"Removed junction: {junction_path} -> {target}")
            
            # Update tracked junctions
            self.junctions = [j for j in self.junctions if j['path'] != junction_path]
            
            return True
                
        except Exception as e:
            logger.error(f"Error removing junction: {e}")
            return False

# Create a simple test function
def test_directory_manager():
    """Test the directory manager functionality."""
    import tempfile
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Testing in temporary directory: {temp_dir}")
        
        # Initialize the directory manager
        manager = DirectoryManager(temp_dir)
        
        # Create test directories
        test_dir1 = manager.create_directory("test_dir1", "Test directory 1")
        test_dir2 = manager.create_directory("test_dir2", "Test directory 2")
        
        print(f"Created test directories: {test_dir1}, {test_dir2}")
        
        # Create junction points
        result = manager.create_junction_pair(test_dir1, test_dir2)
        print(f"Created junction pair: {result}")
        
        # List all directories and junctions
        print("Directories:")
        for d in manager.list_directories():
            print(f"  {d['path']} - {d['description']}")
        
        print("Junctions:")
        for j in manager.list_junctions():
            print(f"  {j['path']} -> {j['target']}")
        
        # Check a junction
        junction_path = os.path.join(test_dir1, os.path.basename(test_dir2))
        target = manager.check_junction(junction_path)
        print(f"Junction {junction_path} points to: {target}")
        
        # Remove a junction
        result = manager.remove_junction(junction_path)
        print(f"Removed junction: {result}")

if __name__ == "__main__":
    # Setup logging for standalone testing
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run the test
    test_directory_manager()
