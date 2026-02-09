# Contributing to ShellPack

Thank you for your interest in contributing to ShellPack! This document provides guidelines and instructions for contributing.

## Code of Conduct

Please be respectful and constructive in all interactions. We welcome contributors of all experience levels.

## Getting Started

### Prerequisites

- Python 3.7 or higher
- Git
- A GitHub account

### Setup

1. **Fork the repository**
   
   Click the "Fork" button on GitHub to create your own copy.

2. **Clone your fork**
   
   ```bash
   git clone https://github.com/YOUR_USERNAME/shellpack.git
   cd shellpack
   ```

3. **Verify the setup**
   
   ```bash
   python3 -c "from shellpack import core, backup, restore, cli; print('Setup OK')"
   ```

## Project Structure

```
shellpack/
├── shellpack/
│   ├── __init__.py      # Package metadata
│   ├── core.py          # Shared utilities, config, UI, Git operations
│   ├── backup.py        # Backup functionality
│   ├── restore.py       # Restore functionality
│   └── cli.py           # Command-line interface
├── shellpack.py         # Main entry point
├── run.py               # One-liner launcher for curl execution
├── shellpack.ps1        # PowerShell wrapper (Windows)
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── IMPROVEMENTS.md
└── LICENSE
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-encryption` - New features
- `fix/ssh-key-permissions` - Bug fixes
- `docs/update-readme` - Documentation changes
- `refactor/simplify-backup` - Code refactoring

### Code Style

#### Python Guidelines

- Follow PEP 8 style guidelines
- Use type hints for function parameters and return values
- Keep functions focused and under 50 lines when possible
- Use descriptive variable names

#### Example

```python
def backup_shell_config(shell: str, dest_dir: Path) -> bool:
    """
    Backup shell configuration files.
    
    Args:
        shell: Shell name ('fish', 'bash', 'zsh')
        dest_dir: Destination directory for backup
    
    Returns:
        True if backup succeeded, False otherwise
    """
    config_path = get_shell_config_path(shell)
    if not config_path.exists():
        return False
    
    try:
        shutil.copy2(config_path, dest_dir / config_path.name)
        return True
    except OSError as e:
        log("ERROR", f"Failed to backup {shell}: {e}")
        return False
```

#### Imports

Organize imports in this order:

1. Standard library
2. Third-party packages (none currently)
3. Local imports

```python
import os
import sys
from pathlib import Path
from typing import Optional, List

from shellpack.core import config, print_status, run_command
```

### Testing

Before submitting, verify your changes:

1. **Import test**
   ```bash
   python3 -c "from shellpack import core, backup, restore, cli"
   ```

2. **Dry run test**
   ```bash
   python3 shellpack.py --dry-run backup
   python3 shellpack.py --dry-run restore
   ```

3. **Help and version**
   ```bash
   python3 shellpack.py help
   python3 shellpack.py version
   ```

4. **Syntax check**
   ```bash
   python3 -m py_compile shellpack/core.py
   python3 -m py_compile shellpack/backup.py
   python3 -m py_compile shellpack/restore.py
   python3 -m py_compile shellpack/cli.py
   ```

### Commit Messages

Write clear, concise commit messages:

```
feat: add GPG encryption for backups

- Add encrypt_backup() function using GPG
- Add --encrypt flag to CLI
- Update manifest to include encryption metadata
```

Format:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation only
- `refactor:` - Code change that neither fixes nor adds
- `test:` - Adding tests
- `chore:` - Maintenance tasks

## Submitting Changes

### Pull Request Process

1. **Update your fork**
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Push your branch**
   ```bash
   git push origin feature/your-feature
   ```

3. **Create a Pull Request**
   - Go to GitHub and click "New Pull Request"
   - Provide a clear description of your changes
   - Reference any related issues

### PR Checklist

- [ ] Code follows project style guidelines
- [ ] All imports work correctly
- [ ] Dry run tests pass
- [ ] Documentation updated if needed
- [ ] CHANGELOG.md updated for significant changes
- [ ] Commit messages are clear and descriptive

## Reporting Issues

### Bug Reports

Include:
- Operating system and version
- Python version (`python3 --version`)
- Steps to reproduce
- Expected behavior
- Actual behavior
- Log file contents (`~/.shellpack/shellpack.log`)

### Feature Requests

Include:
- Clear description of the feature
- Use case / motivation
- Proposed implementation (if any)

## Areas for Contribution

### Good First Issues

- Improve error messages with more context
- Add more shell detection (nushell, elvish, etc.)
- Improve documentation

### Larger Projects

- Add backup encryption (GPG/age)
- Implement incremental backups
- Add cloud storage backends (S3, GCS)
- Create test suite with pytest

## Questions?

Feel free to open an issue for any questions about contributing.

---

Thank you for contributing to ShellPack!
