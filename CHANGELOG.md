# Changelog

All notable changes to ShellPack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

### [1.1.0] - Planned
- [ ] Homebrew formula for easy installation
- [ ] AUR package for Arch Linux
- [ ] Automated backup scheduling
- [ ] Backup encryption option
- [ ] Config file for default settings

### [1.2.0] - Planned
- [ ] GUI application (optional)
- [ ] Cloud storage backends (S3, GCS, Azure Blob)
- [ ] Incremental backups
- [ ] Backup comparison/diff tool
