# NCSI Resolver

<div align="center">
    
![NCSI Resolver Banner](docs/images/banner.png)
[![GitHub Workflow Status][workflow-badge]][workflow-url]
[![Version][version-badge]][version-url]
[![Python][python-badge]][python-url]
[![License][license-badge]][license-url]
[![GitHub Discussions][discussions-badge]][discussions-url]

</div>

A solution to fix the "No Internet, Secured" Windows connectivity detection issue when Windows incorrectly reports no internet connection despite having working connectivity.

[workflow-badge]: https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/actions/workflows/python.yml/badge.svg
[workflow-url]: https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/actions
[version-badge]: https://img.shields.io/github/v/release/djdarcy/Windows-No-Internet-Secured-BUGFIX?sort=semver&color=brightgreen
[version-url]: https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/releases
[python-badge]: https://img.shields.io/badge/python-3.8%2B-brightgreen
[python-url]: https://www.python.org/downloads/
[license-badge]: https://img.shields.io/badge/license-MIT-blue
[license-url]: https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/blob/main/LICENSE
[discussions-badge]: https://img.shields.io/github/discussions/djdarcy/Windows-No-Internet-Secured-BUGFIX
[discussions-url]: https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/discussions


## Overview

NCSI (Network Connectivity Status Indicator) Resolver addresses a common Windows networking frustration where the system incorrectly reports "No Internet" despite having actual connectivity. This affects applications that rely on Windows' connectivity status to function properly, such as Microsoft Store, OneDrive, and UWP apps.

The root causes typically involve:
- Intelligent firewalls or routers intercepting Windows connectivity checks
- Network security software scanning or interfering with NCSI probes
- Windows Wi-Fi adapter behavior causing connection instability
- Captive portal detection mechanisms behaving incorrectly

NCSI Resolver creates a lightweight HTTP server on your local machine to properly respond to the two key endpoints that Windows uses for connectivity checks:

1. `/connecttest.txt` - Must return exactly "Microsoft Connect Test"
2. `/redirect` - Used for captive portal detection

For those curious about the innerworkings of NCSI, the official documentation can be found [here](https://learn.microsoft.com/en-us/windows-server/networking/ncsi/ncsi-overview). There is an article on Medium that gives a detailed explanation of how this bug was discovered and the steps taken to resolve it. You can read all about it here, "[When Windows Says 'No Internet' But You Know Better: A Technical Walkthrough](https://medium.com/technical-curious/when-windows-says-no-internet-but-you-know-better-a-technical-walkthrough-4710f541fc35)".

## Features

- 🌐 **Local NCSI server** that responds to Windows connectivity tests
- 🔍 **Actual connectivity verification** ensuring internet is actually available
- 🛠️ **System configuration tools** for registry and hosts file setup
- 💻 **Windows service** for automatic operation on startup
- 📊 **Diagnostic logging** for understanding connectivity issues
- ⚡ **Wi-Fi adapter optimization** for connection stability
- 🔒 **Security monitoring** for tracking and detecting suspicious connection attempts
- 🔬 **Advanced network diagnostics** with layered testing (ICMP, DNS, HTTP, HTTPS)
- 🧪 **Comprehensive installation verification** to ensure proper setup
- 🖥️ **Interactive diagnostic page** when accessing the server directly

## Installation

### Prerequisites

- Windows 10 or 11
- Administrator privileges
- Python 3.6 or higher

### Quick Install

1. Download the latest release from the [Releases page](https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/releases)
2. Extract the ZIP file to a temporary location
3. Right-click on `_install.bat` and select "Run as administrator"

The installer will:
- Configure Windows system settings
- Install the NCSI Resolver service
- Start the service automatically

### Manual Installation

If you prefer to install manually or want more control:

```cmd
# Clone the repository
git clone https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX.git
cd Windows-No-Internet-Secured-BUGFIX

# Install using the Python script
python installer.py --install
```

### Installation Options

You can customize the installation with various options:

```cmd
# Install to a custom directory
python installer.py --install --install-dir="C:\Custom Path\NCSI Resolver"

# Use a different port (if port 80 is in use)
python installer.py --install --port=8080

# Enable debug logging
python installer.py --install --debug
```

## Usage

Once installed, the NCSI Resolver runs automatically in the background. There's no user interface needed as it works silently to ensure Windows correctly detects internet connectivity.

### Checking Status

To check the current status:

```cmd
python installer.py --check
```

### Advanced Diagnostics

To run advanced network diagnostics:

```cmd
python test_installation.py --verbose
```

This comprehensive test will check:
- System configuration (registry, hosts file)
- Service installation and status
- Network connectivity at multiple layers
- Troubleshoot any detected issues

### Service Management

The service can be managed like any other Windows service:

- Start: `net start NCSIResolver`
- Stop: `net stop NCSIResolver`
- Restart: Stop and then start the service

### Testing Connectivity

You can test if the resolver is working by:

1. Opening Command Prompt
2. Running `curl http://localhost/ncsi.txt`

If you see "Microsoft Connect Test", the server is running correctly.

You can also visit `http://localhost/redirect` in your browser to see an interactive diagnostic page.

## Security Features

NCSI Resolver now includes basic security monitoring that:

- Tracks connection attempts to the service
- Detects potential scanning or probing activity
- Logs suspicious connection patterns
- Provides a simple IDS-like capability

Security logs are stored in the `Logs` directory of your installation.

## Uninstallation

To completely remove NCSI Resolver:

1. Run `python installer.py --uninstall` or
2. Run `uninstall.bat` as administrator

## How It Works

NCSI Resolver functions by:

1. Redirecting Windows NCSI test domains to your local machine via hosts file
2. Running a local HTTP server to respond to connectivity test requests
3. Verifying actual internet connectivity using multiple methods (ICMP, DNS, HTTP)
4. Updating the Windows registry to reference the local server
5. Running as a Windows service to ensure continuous operation
6. Monitoring and logging connection attempts for security purposes
7. Providing diagnostics to help troubleshoot connectivity issues

## Troubleshooting

### Common Issues

- **Service won't start**: Ensure port 80 is not in use by other applications
- **"No Internet" still showing**: Restart the Network Location Awareness service (`net stop NlaSvc && net start NlaSvc`)
- **Applications still offline**: Some applications may need to be restarted to recognize the new connectivity status
- **Port conflict**: Use the `--port` option during installation to specify an alternative port

### Advanced Troubleshooting

For more in-depth troubleshooting, run the comprehensive test script:

```cmd
python test_installation.py --verbose
```

This will check all aspects of the installation and provide specific recommendations for fixing issues.

### Logs

Check logs at:
- Service logs: `C:\Program Files\NCSI Resolver\Logs\ncsi_resolver.log`
- Service output: `C:\Program Files\NCSI Resolver\Logs\service_output.log`
- Security logs: `C:\Program Files\NCSI Resolver\Logs\security.log`
- Detailed debug: `C:\Program Files\NCSI Resolver\Logs\ncsi_debug.log`

### Development Setup

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate it: `venv\Scripts\activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Make your changes
6. Test thoroughly on different Windows versions and network configurations

### Building

To build a distributable package:

```cmd
python -m pip install pyinstaller
pyinstaller --onefile installer.py
```

## Contributions

Contributions are welcome! Issues, suggestions, and bug reports are all appreciated. Please open an [issue](https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/issues) if you find something that can be improved. Or feel free to submit a Pull Request: 

1. Make a fork and clone the repository
2. Setup a new branch and add your new feature (e.g., `feature/MORE_fixes`).
3. Submit a pull request describing your changes.

Like the project?

[!["Buy Me A Coffee"](https://camo.githubusercontent.com/0b448aabee402aaf7b3b256ae471e7dc66bcf174fad7d6bb52b27138b2364e47/68747470733a2f2f7777772e6275796d6561636f666665652e636f6d2f6173736574732f696d672f637573746f6d5f696d616765732f6f72616e67655f696d672e706e67)](https://www.buymeacoffee.com/djdarcy)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Inspired by:
  - My onerous Surface 7 refusing to sync with OneNote while using my virtual KVM
  - And [*numerous*](https://answers.microsoft.com/en-us/windows/forum/windows_10-networking/windows-shows-no-internet-access-but-my-internet/2e9b593f-c31c-4448-b5d9-6e6b2bd8560c?page=2) [community](https://www.youtube.com/watch?v=v3CkXHgj6Ig&lc=UgwCfOeDQI7vPPsX0lN4AaABAg) [discussions](https://www.quora.com/Why-does-my-WiFi-keep-saying-no-internet-secured-even-no-matter-what-I-do-to-fix-it) about Windows NCSI issues
- Uses [NSSM](https://nssm.cc/) for service management
