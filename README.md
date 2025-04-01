# NCSI Resolver

![NCSI Resolver Banner](docs/images/banner.png)

A solution to fix the "No Internet, Secured" Windows connectivity detection issue when Windows incorrectly reports no internet connection despite having working connectivity.

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

## Installation

### Prerequisites

- Windows 10 or 11
- Administrator privileges
- Python 3.6 or higher

### Quick Install

1. Download the latest release from the [Releases page](https://github.com/djdarcy/Windows-No-Internet-Secured-BUGFIX/releases)
2. Extract the ZIP file to a temporary location
3. Right-click on `install.bat` and select "Run as administrator"

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

## Usage

Once installed, the NCSI Resolver runs automatically in the background. There's no user interface needed as it works silently to ensure Windows correctly detects internet connectivity.

### Checking Status

To check the current status:

```cmd
python installer.py --check
```

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

## Troubleshooting

### Common Issues

- **Service won't start**: Ensure port 80 is not in use by other applications
- **"No Internet" still showing**: Restart the Network Location Awareness service (`net stop NlaSvc && net start NlaSvc`)
- **Applications still offline**: Some applications may need to be restarted to recognize the new connectivity status

### Logs

Check logs at:
- Service logs: `C:\Program Files\NCSI Resolver\ncsi_resolver.log`
- Service output: `C:\Program Files\NCSI Resolver\service_output.log`

## Contribution

Contributions are welcome! Please feel free to submit a Pull Request.

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

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- Inspired by numerous community discussions about Windows NCSI issues
- Uses [NSSM](https://nssm.cc/) for service management
