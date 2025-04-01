# Contributing to NCSI Resolver

Thank you for the interest in contributing to the "Windows (No Internet, Secured) BUGFIX" NCSI Resolver project! This document provides guidelines and instructions for contributing.

## How to Contribute

### Reporting Bugs

If you find a bug, please create an issue using the bug report template and include:

1. A clear, descriptive title
2. Steps to reproduce the issue
3. Expected behavior
4. Actual behavior
5. Screenshots if applicable
6. Your Windows version and other relevant system information
7. Any additional context that might help

### Suggesting Enhancements

For feature requests or enhancements:

1. Use the feature request template
2. Clearly describe the feature/enhancement and its benefits
3. Provide specific examples of how it would be used
4. Describe alternatives you've considered
5. Any additional context or screenshots

### Pull Requests

1. Fork the repository
2. Create a new branch from `main`
3. Make your changes
4. Ensure your code follows the project's style guidelines
5. Add tests if applicable
6. Update documentation as needed
7. Submit your pull request with a clear description of the changes

## Development Setup

1. Clone your fork of the repository
2. Set up a virtual environment:
   ```
   python -m venv venv
   venv\Scripts\activate  # Windows
   source venv/bin/activate  # Unix/MacOS
   ```
3. Install dependencies (dev or otherwise, currently there are none):
   ```
   pip install -r requirements-dev.txt
   ```

## Testing

Before submitting your changes, please test them thoroughly:

1. Test on multiple Windows versions if possible
2. Test with different network configurations
3. Test with and without admin privileges
4. Run any unit tests if available

## Style Guidelines

- Follow PEP 8 coding standards
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions focused on a single responsibility
- Document public functions with docstrings

## Commit Messages

- Use clear, descriptive commit messages
- Start with a short summary line (50 chars or less)
- Optionally, provide more detailed explanation after the summary, separated by a blank line
- Reference issue numbers when applicable: "Fixes #123" or "Related to #456"

## License

By contributing to this project, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).

## Questions?

If you have any questions or need help, feel free to open an issue or contact the project maintainers.

Thank you for contributing to NCSI Resolver!

## Code of Conduct

By participating, you agree to maintain a respectful environment for everyone. Contributors are expected to be:

- Welcoming and civil (empathy would be nice too)
- Accepting of constructive criticism
- Thoughtful and attempt to be respectful of alternate viewpoints and experiences
- Focus on what is best for the project and the community