# Changelog

All notable changes to the "Windows (No Internet, Secured) BUGFIX" NCSI Resolver project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.7.3-alpha] - 2025-10-26

### Added
- Future-proof Python detection in NSIS installer (supports Python 3.8-3.13+)
- Python validation step to ensure executable actually works (not just exists)
- New `--diagnose` mode with 9 pre-installation checks
- Start Menu shortcut for "Run Diagnostics"
- Dynamic version detection loop for future Python releases

### Fixed
- NSIS installer now detects Python versions 3.11, 3.12, 3.13 and beyond
- Unicode encoding issues in diagnostic output on Windows console
- Python detection no longer requires hardcoded version updates

### Changed
- Enhanced FindPython function with multiple detection strategies
- Improved error messages with specific troubleshooting guidance
- Diagnostic mode uses ASCII-safe output for Windows compatibility

## [0.7.2-alpha] - 2025-10-25

### Added
- Initial NSIS (Nullsoft Scriptable Install System) installer implementation
- One-click installation with `NCSI_Resolver_v0.7.2_setup.exe`
- Automated Python detection for versions 3.8-3.10
- Automatic service installation and startup via NSIS installer
- Minimal installer build script (`build_installer.py`)

## [0.7.1-alpha] - 2025-04-01
- First major release
- Minor bug fixes (CI/CD, flake8, and other CI/CD related issues)
- Documentation updates
- Improved error handling and logging

## [0.7.0-alpha] - 2025-04-01

### Added
- Network Diagnostics module with layered testing (ICMP, DNS, HTTP, HTTPS)
- Security Monitoring feature to detect and log suspicious connection attempts
- Enhanced interactive HTML redirect page with diagnostics and more
- Detailed installation test script (test_installation.py)
- Windows default registry settings file for easier recovery
- Service start verification with connection testing

### Fixed
- Socket binding issue by using all interfaces (0.0.0.0) instead of specific IP
- Better error handling during socket binding with enhanced logging
- Enhanced service logging with debug information for troubleshooting
- Scope issues with TIMEOUT variable in service_installer.py (fixes Flake8 error)

### Changed
- Deprecated test_connectivity.py in favor of new modular network_diagnostics.py
- Improved redirect.html page with interactive features and modern design
- Enhanced installation process with better error detection and reporting
- Updated version to 0.7.0-alpha

## [0.6.0-alpha] - 2025-04-01

### Added
- Modular code structure with dedicated NCSIresolver package
- Configuration file (config.json) to replace hardcoded values
- Firewall helper module for managing Windows Firewall rules
- Improved service wrapper with enhanced error handling
- Static file handling instead of code-generated content
- Junction points between installation and backup directories
- Support for non-WiFi systems with better detection
- Documentation on Wi-Fi power management settings

### Fixed
- Service installation bugs and reliability issues
- Better handling of paths with spaces
- Improved port conflict detection and handling

## [0.5.4-alpha] - 2025-04-01

### Added
- Enhanced logging for service_installer.py to track installation issues

## [0.5.3-alpha] - 2025-03-31

### Added
- Improved port handling and conflict detection
- Documentation on Wi-Fi Power Management Settings
- Junction points between installation and backup directories

## [0.5.2-alpha] - 2025-03-31

### Fixed
- Enhanced registry backup and restoration process

## [0.5.1-alpha] - 2025-03-31

### Fixed
- Path handling for files with spaces
- Simplified service wrapper
- Modified default installation directory to C:\NCSI_Resolver
- Improved NSSM download with caching

## [0.5.0-alpha] - 2025-03-31

### Added
- Initial release of NCSI Resolver
- Core NCSI server with both `/connecttest.txt` and `/redirect` endpoint support
- Actual internet connectivity verification (ICMP, DNS, HTTP methods)
- System configuration utilities for registry and hosts file
- Windows service installer using NSSM (see: https://nssm.cc/)
- Wi-Fi adapter optimization for Intel chipsets
- Full installer and uninstaller scripts
- Batch files for easy installation
- Complete documentation
- Installer banner
- Robuster error handling and timeouts

### Fixed
- Windows incorrectly reporting "No Internet" despite working connectivity
- Applications failing to sync due to reliance on NCSI
- Handling of captive portal detection via `/redirect` endpoint
- Wi-Fi connection stability issues
- Desktop/non-wireless system detection and handling