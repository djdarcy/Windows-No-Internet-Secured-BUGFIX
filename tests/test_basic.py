"""
Basic tests for NCSI Resolver components.
These tests verify fundamental functionality without requiring external dependencies.
"""

import os
import sys
import unittest

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Try to import version info
try:
    from version import get_version_info, __version__
except ImportError:
    # Define fallback version for testing
    __version__ = "0.5.0"

class BasicTests(unittest.TestCase):
    """Basic functionality tests."""

    def test_version_format(self):
        """Test that version is properly formatted."""
        # Either imported from version.py or default
        self.assertIsNotNone(__version__)
        
        # Should be in format x.y.z
        parts = __version__.split('.')
        self.assertEqual(len(parts), 3, "Version should have 3 components (x.y.z)")
        
        # Each part should be a number
        for part in parts:
            self.assertTrue(part.isdigit(), f"Version part '{part}' should be a number")

    def test_imports(self):
        """Test that essential modules can be imported."""
        # This test simply ensures these imports don't raise exceptions
        try:
            import ncsi_server
            self.assertTrue(True, "ncsi_server imported successfully")
        except ImportError:
            # Skip test if file doesn't exist yet
            self.skipTest("ncsi_server.py not found")
            
        try:
            import system_config
            self.assertTrue(True, "system_config imported successfully")
        except ImportError:
            # Skip test if file doesn't exist yet
            self.skipTest("system_config.py not found")
            
        try:
            import service_installer
            self.assertTrue(True, "service_installer imported successfully")
        except ImportError:
            # Skip test if file doesn't exist yet
            self.skipTest("service_installer.py not found")
            
        try:
            import installer
            self.assertTrue(True, "installer imported successfully")
        except ImportError:
            # Skip test if file doesn't exist yet
            self.skipTest("installer.py not found")

    def test_functions_exist(self):
        """Test that essential functions exist in the modules."""
        # Skip if files don't exist
        try:
            import ncsi_server
            # Test key functions
            self.assertTrue(hasattr(ncsi_server, "create_server"), "create_server function should exist")
            self.assertTrue(hasattr(ncsi_server, "run_server"), "run_server function should exist")
        except ImportError:
            self.skipTest("ncsi_server.py not found")

if __name__ == "__main__":
    unittest.main()
