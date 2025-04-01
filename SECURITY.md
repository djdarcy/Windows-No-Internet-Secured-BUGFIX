# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |

## Reporting a Vulnerability

The NCSI Resolver project takes security seriously. We appreciate your efforts to responsibly disclose your findings.

To report a security vulnerability, please follow these steps:

1. **Do not disclose the vulnerability publicly**
2. **Create a security advisory** by going to the Security tab in the GitHub repository
3. **Provide details** about the vulnerability, including:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested remediation if available

The project maintainers will:

1. Acknowledge receipt of your vulnerability report as soon as possible
2. Assess the impact and determine a fix
3. Release a patch and acknowledge your contribution if applicable

## Security Considerations

NCSI Resolver is designed to run with administrative privileges on Windows systems as it:

- Modifies system registry entries
- Changes the hosts file
- Runs a web server on port 80
- Installs a Windows service

### Mitigations

The project implements the following security measures:

1. The web server only responds to specific NCSI endpoints
2. All network operations use proper error handling
3. The server verifies actual internet connectivity before responding
4. No user data is collected or transmitted
5. The code is open source and can be audited

### Best Practices

When using NCSI Resolver:

1. Always download from the official GitHub repository
2. Check release signatures when available
3. Review the code before installation if you have security concerns
4. Run the latest version to ensure you have the most recent security fixes
