# NCSIresolver Directory

This directory contains the core files that get installed to the target system as part of the NCSI Resolver package.

## Purpose

The purpose of this directory is to clearly separate installable files from development/build files, making it easier to:
1. Understand which files get installed to the user's system
2. Maintain and update the installable components
3. Organize the repository in a more structured way

## Contents

The following files are included in this directory:

| File | Description |
|------|-------------|
| `config.json` | Configuration settings for the NCSI Resolver |
| `config_manager.py` | Module for loading and managing configuration |
| `directory_manager.py` | Utility for managing directories and junction points |
| `logger.py` | Enhanced logging functionality |
| `ncsi_server.py` | Core HTTP server implementation for handling NCSI requests |
| `README.md` | This file |
| `redirect.html` | HTML content returned for the /redirect endpoint |
| `service_wrapper.py` | Windows service wrapper for running the NCSI server |
| `Windows_Default.reg` | Registry file for setting default values for the NCSI Resolver |

## Installation

These files are automatically copied to the installation directory by the installer.py script, which is located in the root directory of the repository.

## Development

When making changes to these files, be sure to test them in the context of a complete installation. The installer copies these files to the target system, so changes made here will be reflected in new installations.