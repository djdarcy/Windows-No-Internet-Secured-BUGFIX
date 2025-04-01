#!/usr/bin/env python3
"""
NCSI Resolver Version Information

This module provides version information for all NCSI Resolver components.
"""

# Version information
__version__ = "0.5.2"
__author__ = "Dustin Darcy"
__copyright__ = "Copyright 2025"

# Component descriptions
DESCRIPTIONS = {
    "server": "Windows Network Connectivity Status Indicator Resolver Server",
    "installer": "Windows Network Connectivity Status Indicator Resolver Installer",
    "system_config": "Windows System Configuration for NCSI Resolver",
    "service_installer": "NCSI Resolver Service Installer",
}

def get_version_info(component=None):
    """
    Get version information for a specific component.
    
    Args:
        component: Component name (server, installer, system_config, service_installer)
        
    Returns:
        Dict: Version information
    """
    info = {
        "version": __version__,
        "author": __author__,
        "copyright": __copyright__,
    }
    
    if component and component in DESCRIPTIONS:
        info["description"] = DESCRIPTIONS[component]
    else:
        info["description"] = "Windows Network Connectivity Status Indicator Resolver"
        
    return info

def get_version_string(component=None):
    """
    Get formatted version string for a component.
    
    Args:
        component: Component name (server, installer, system_config, service_installer)
        
    Returns:
        str: Formatted version string
    """
    info = get_version_info(component)
    return f"{info['description']} v{info['version']}"