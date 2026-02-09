# Changelog

All notable changes to ShellPack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0] - 2026-02-09

### Changed

- **Complete Python Rewrite**: Entire codebase rewritten from Bash to Python 3.7+
  - Eliminates `set -e` silent exit bugs that plagued the Bash version
  - Proper exception handling and error propagation
  - Modular architecture with separate modules for core, backup, restore, and CLI
  - Consistent behavior across all platforms

### Added

- **Modular Architecture**:
  - `shellpack/core.py`: Shared utilities, configuration, UI helpers, Git operations
  - `shellpack/backup.py`: All backup functionality
  - `shellpack/restore.py`: All restore functionality
  - `shellpack/cli.py`: Command-line argument parsing

- **Improved Error Handling**:
  - Context-rich error messages with actionable suggestions
  - Proper exception handling throughout
  - Graceful degradation when optional features fail

- **Enhanced Input Validation**:
  - Git URL validation with regex patterns for SSH, HTTPS, and Git protocols
  - Backup name sanitization to prevent path traversal
  - Email validation for SSH key generation

- **Rollback Mechanism**:
  - Automatic rollback on failed operations
  - Rollback stack tracks all reversible actions
  - User confirmation before executing rollback

- **Network Reliability**:
  - Retry with exponential backoff for Git operations
  - SSH connection verification before push
  - Configurable timeouts for all network operations

- **Disk Space Management**:
  - Pre-operation disk space checks
  - Backup size estimation before creation
  - Warnings when space is low

- **One-Liner Launcher** (`run.py`):
  - Downloads and runs ShellPack from a temporary directory
  - No local installation required
  - Automatic cleanup after execution

### Fixed

- **`set -e` Silent Exits**: The Bash script would silently exit on various conditions:
  - `((var++))` when var is 0 (returns exit code 1)
  - `[[ -n "$VAR" ]]` evaluating "false" as truthy
  - Subshell failures not propagating correctly
  
- **Boolean Logic Bugs**: Fixed incorrect boolean checks throughout
- **Variable Scoping**: Proper variable scoping in Python eliminates Bash scoping issues
- **Arithmetic Operations**: No more exit code issues with arithmetic

### Deprecated

- `shellpack.sh`: The Bash script is deprecated in favor of the Python version
  - Will be removed in v3.0.0
  - Use `python3 shellpack.py` or the one-liner instead

### Security

- Input validation for all user-provided data
- SSH key permission management (700/600/644)
- Secure temporary directory handling with cleanup
- No shell injection vulnerabilities

---

## [1.0.0] - 2025-02-08

### Added

- Initial release of ShellPack
- Cross-platform support (macOS, Linux, Windows WSL)
- Backup and restore shell environments
- Support for Fish, Bash, and Zsh shells
- Oh-My-Zsh backup and restore
- Starship prompt configuration backup
- Package list backup (apt, brew, dnf, pacman)
- Conda/Miniconda environment export and restore
- SSH key backup and restore
- Cloud credentials backup (AWS, Azure, GCP)
- Shell history backup (optional)
- Git configuration backup
- Full backup mode (personal use)
- Shareable backup mode (excludes sensitive data)
- SHA-256 checksum verification
- Colored CLI output
- Progress indicators
- Verbose mode (`--verbose`)
- Dry-run mode (`--dry-run`)
- Windows PowerShell wrapper for WSL management
- Create new WSL instances during restore
- One-liner installation from GitHub

### Security

- Shareable backups automatically exclude sensitive data
- SSH keys are only included when explicitly requested
- Checksums verify backup integrity

---

## Future Plans

### [2.1.0] - Planned

- [ ] Homebrew formula for easy installation
- [ ] AUR package for Arch Linux
- [ ] PyPI package (`pip install shellpack`)
- [ ] Config file for default settings (~/.shellpackrc)

### [2.2.0] - Planned

- [ ] Backup encryption option (GPG/age)
- [ ] Automated backup scheduling (cron/launchd integration)
- [ ] Incremental backups
- [ ] Backup comparison/diff tool

### [3.0.0] - Planned

- [ ] Remove deprecated Bash script
- [ ] Plugin system for custom backup sources
- [ ] Cloud storage backends (S3, GCS, Azure Blob)
- [ ] Web-based backup browser
