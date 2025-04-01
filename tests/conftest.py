"""
Configuration for pytest.

This file contains pytest configuration hooks and shared fixtures.
"""

import os
import sys
import pytest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture
def mock_ncsi_server():
    """
    Create a mock NCSI server for testing.
    
    Returns a configured but not running server object.
    """
    try:
        from ncsi_server import create_server
        # Create a server on a non-standard port for testing
        server = create_server(host="127.0.0.1", port=8080, verify_connectivity=False)
        return server
    except ImportError:
        pytest.skip("ncsi_server.py not found")

@pytest.fixture
def temp_file_path(tmp_path):
    """
    Provide a temporary file path for testing.
    
    Args:
        tmp_path: pytest's built-in temporary directory fixture
        
    Returns:
        Path: Path to a temporary file
    """
    return tmp_path / "test_file.txt"
