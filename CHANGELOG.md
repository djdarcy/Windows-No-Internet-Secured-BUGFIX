# Changelog

All notable changes to the "Windows (No Internet, Secured) BUGFIX" NCSI Resolver project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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