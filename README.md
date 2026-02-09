<p align="center">
  <h1 align="center">ShellPack</h1>
  <p align="center">
    <strong>Cross-Platform Shell Environment Backup & Restore</strong>
  </p>
  <p align="center">
    Backup your shell environment on macOS, restore it on Linux. Or vice versa.<br>
    One command. Zero hassle.
  </p>
  <p align="center">
    <a href="#quick-start">Quick Start</a> &bull;
    <a href="#features">Features</a> &bull;
    <a href="#usage">Usage</a> &bull;
    <a href="#what-gets-backed-up">What's Backed Up</a> &bull;
    <a href="#faq">FAQ</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/version-2.0.0-blue.svg" alt="Version">
    <img src="https://img.shields.io/badge/python-3.7+-blue.svg" alt="Python">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20WSL-lightgrey.svg" alt="Platform">
    <img src="https://img.shields.io/badge/shells-Fish%20%7C%20Bash%20%7C%20Zsh-orange.svg" alt="Shells">
  </p>
</p>

---

> **Version 2.0.0 - Complete Python Rewrite**
> 
> ShellPack has been completely rewritten in Python for improved reliability, better error handling, and cross-platform consistency. See [CHANGELOG.md](CHANGELOG.md) for details.

---

## Quick Start

**No installation required!** Run directly with Python 3.7+:

### Backup (macOS / Linux / WSL)

```bash
curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/run.py | python3 - backup
```

### Restore (macOS / Linux / WSL)

```bash
curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/run.py | python3 - restore
```

### Windows PowerShell

```powershell
iex (irm https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.ps1)
```

### Local Installation (Optional)

```bash
git clone https://github.com/MoxForge/shellpack.git
cd shellpack
python3 shellpack.py backup
```

---

## Features

| Feature | Description |
|---------|-------------|
| **Cross-Platform** | Works on macOS, Linux (Ubuntu, Debian, Fedora, Arch), and Windows WSL |
| **Zero Installation** | Run directly from GitHub with a single command |
| **Pure Python** | No dependencies beyond Python 3.7+ standard library |
| **Bi-directional** | Backup from any OS, restore to any OS |
| **Complete Backup** | Shell configs, packages, conda, SSH keys, and more |
| **Shareable Mode** | Create backups safe to share publicly |
| **Safe Restore** | Creates NEW WSL instances, never touches existing ones |
| **Integrity Check** | SHA-256 checksums verify backup integrity |
| **Beautiful CLI** | Colored output, progress indicators, clear prompts |
| **Input Validation** | Comprehensive validation prevents injection attacks |
| **Auto-Retry** | Network operations retry with exponential backoff |
| **Rollback Support** | Automatic rollback on failed operations |
| **Disk Space Checks** | Verifies sufficient space before operations |
| **Git Credentials** | Automatic credential helper setup |

---

## Usage

### Backup Your Environment

```bash
python3 shellpack.py backup
```

The script will:

1. Verify dependencies (git, curl, tar)
2. Ask for your backup Git repository URL
3. Let you name your backup (default: `{shell}-{hostname}-{date}`)
4. Choose backup type:
   - **Full backup**: Personal use (includes SSH keys, Git config, history, Conda)
   - **Shareable backup**: Safe to share publicly (excludes sensitive data)
5. Select which data to include
6. Estimate backup size and verify disk space
7. Create the backup and push to your repository

### Restore Your Environment

```bash
python3 shellpack.py restore
```

The script will:

1. Ask for your backup repository URL
2. Show available backups - pick one
3. Verify backup integrity via checksums
4. Handle SSH keys (restore, generate new, or skip)
5. Install shells and tools automatically
6. Restore all configurations
7. Optionally set your default shell

### Command Line Options

```bash
python3 shellpack.py backup              # Backup environment
python3 shellpack.py restore             # Restore environment
python3 shellpack.py help                # Show help
python3 shellpack.py version             # Show version
python3 shellpack.py --verbose backup    # Verbose output
python3 shellpack.py --dry-run restore   # Preview without changes
```

### PowerShell Options (Windows)

```powershell
# Interactive menu
iex (irm https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.ps1)

# Direct commands
.\shellpack.ps1 backup
.\shellpack.ps1 restore

# Custom Ubuntu version for new WSL instances
.\shellpack.ps1 restore -UbuntuVersion "22.04"

# Dry run mode
.\shellpack.ps1 backup -DryRun
```

---

## What Gets Backed Up

| Component | macOS | Linux | WSL | Notes |
|-----------|:-----:|:-----:|:---:|-------|
| **Fish Shell** | Yes | Yes | Yes | Config, functions, completions, themes |
| **Bash** | Yes | Yes | Yes | .bashrc, .bash_profile, .bash_aliases |
| **Zsh** | Yes | Yes | Yes | .zshrc, .zprofile + Oh-My-Zsh |
| **Starship** | Yes | Yes | Yes | starship.toml |
| **Packages** | brew | apt/dnf/pacman | apt | Package lists for reinstallation |
| **Conda** | Yes | Yes | Yes | All environments exported to YAML |
| **Git Config** | Yes | Yes | Yes | .gitconfig (optional) |
| **SSH Keys** | Yes | Yes | Yes | Full .ssh directory (optional) |
| **Cloud Creds** | Yes | Yes | Yes | AWS, Azure, GCP configs (optional) |
| **History** | Yes | Yes | Yes | Shell history files (optional) |

---

## Backup Types

### Full Backup (Personal Use)

Includes everything for complete environment restoration:

- All shell configurations
- SSH keys (private and public)
- Git configuration (name, email, settings)
- Conda environments
- Shell history
- Cloud credentials

> **Important**: Keep your backup repository **private** when using full backup mode.

### Shareable Backup (Safe to Share)

Safe for public repositories - automatically excludes:

- SSH keys
- Git identity (name/email)
- Cloud credentials (AWS, Azure, GCP)
- Shell history

Perfect for sharing your shell setup with colleagues or the community.

---

## Repository Structure

After backup, your repository will contain:

```
your-backup-repo/
├── backups/
│   └── fish-macbook-20260209/
│       ├── manifest.json           # Backup metadata + checksums
│       ├── shells/
│       │   ├── fish/
│       │   │   └── fish_config.tar.gz
│       │   ├── bash/
│       │   │   ├── .bashrc
│       │   │   └── .bash_profile
│       │   └── zsh/
│       │       ├── .zshrc
│       │       └── ohmyzsh.tar.gz
│       ├── packages/
│       │   ├── brew_formula.txt
│       │   └── brew_cask.txt
│       ├── conda/
│       │   ├── base.yml
│       │   └── myenv.yml
│       ├── config/
│       │   ├── starship.toml
│       │   └── .gitconfig
│       └── ssh/
│           └── ssh_backup.tar.gz
```

---

## Requirements

### All Platforms

- **Python 3.7+** (pre-installed on most systems)
- **Git** (for repository operations)
- **curl** (for one-liner installation)
- **tar** (for archive operations)

### macOS

```bash
# Git is included with Xcode Command Line Tools
xcode-select --install
```

### Linux

```bash
# Ubuntu/Debian
sudo apt install git curl python3

# Fedora
sudo dnf install git curl python3

# Arch
sudo pacman -S git curl python
```

### Windows

- **WSL2**: `wsl --install`
- **Git for Windows**: Optional, for direct Git operations

---

## Security

ShellPack is built with security as a priority:

### Input Validation

- **Git URL Validation**: All repository URLs are validated against injection attacks
- **Backup Name Sanitization**: Names are sanitized to prevent path traversal
- **Email Validation**: Email addresses are validated for SSH key generation

### SSH Key Security

- **Automatic Backup**: Existing SSH keys are backed up before generating new ones
- **Passphrase Support**: Optional passphrase protection for new keys
- **Proper Permissions**: Automatic permission setting (700 for .ssh, 600 for private keys)

### Network Security

- **Retry Logic**: Network operations retry with exponential backoff
- **SSH Verification**: SSH connections are verified before Git operations
- **Timeout Protection**: All network operations have sensible timeouts

### Credential Management

Platform-specific credential helpers are automatically configured:

| Platform | Credential Helper |
|----------|-------------------|
| macOS | osxkeychain |
| Linux | libsecret, pass, or cache |
| WSL | Git Credential Manager or cache |

---

## FAQ

<details>
<summary><strong>Will restore overwrite my existing WSL?</strong></summary>

**No.** On Windows, restore creates a NEW WSL instance with a name you choose. Your existing distributions are never touched.
</details>

<details>
<summary><strong>Can I backup from Mac and restore on Linux?</strong></summary>

**Yes.** That's the whole point. Shell configs are compatible across platforms. Package managers differ (brew vs apt), but ShellPack stores package lists for each platform separately.
</details>

<details>
<summary><strong>Is my data safe?</strong></summary>

- **Full backups** contain sensitive data - keep your repo **private**
- **Shareable backups** exclude all secrets - safe to make **public**
- All backups include SHA-256 checksums for integrity verification
</details>

<details>
<summary><strong>What if I don't have Fish/Zsh installed on the new machine?</strong></summary>

ShellPack automatically detects missing shells and offers to install them. It detects your package manager (apt, brew, dnf, pacman) and installs appropriately.
</details>

<details>
<summary><strong>Can I have multiple backups?</strong></summary>

**Yes.** Each backup has a unique name (default: `shell-hostname-date`). You can keep as many as you want in your repository and select which one to restore.
</details>

<details>
<summary><strong>How do I update ShellPack?</strong></summary>

No update needed when using the one-liner - it always fetches the latest version from GitHub. For local installations, just `git pull`.
</details>

<details>
<summary><strong>What if the backup/restore fails?</strong></summary>

ShellPack includes automatic rollback support. If an operation fails, it will offer to revert any changes made. You can also check the log file at `~/.shellpack/shellpack.log` for detailed error information.
</details>

<details>
<summary><strong>Why Python instead of Bash?</strong></summary>

The v2.0.0 rewrite to Python provides:
- **Better error handling**: No more silent failures from `set -e`
- **Cross-platform consistency**: Same code runs everywhere
- **Easier maintenance**: Modular code structure
- **Improved reliability**: Proper exception handling and cleanup
</details>

---

## Troubleshooting

### Backup stops or hangs

1. **Check SSH authentication**:
   ```bash
   ssh -T git@github.com
   ```

2. **View detailed logs**:
   ```bash
   cat ~/.shellpack/shellpack.log
   ```

3. **Run with verbose mode**:
   ```bash
   python3 shellpack.py --verbose backup
   ```

4. **Manual push** (if backup completes but push fails):
   ```bash
   cd ~/.shellpack/temp/git
   git push -u origin main
   ```

### Common Issues

| Issue | Solution |
|-------|----------|
| SSH authentication failed | Add your SSH key to GitHub/GitLab |
| Permission denied | Check file permissions, run with appropriate privileges |
| Conda timeout | Large environments may take time - check logs |
| Git push rejected | Ensure you have write access to the repository |

---

## Project Structure

```
shellpack/
├── shellpack/
│   ├── __init__.py      # Package metadata
│   ├── core.py          # Utilities, config, UI, Git operations
│   ├── backup.py        # Backup functionality
│   ├── restore.py       # Restore functionality
│   └── cli.py           # Command-line interface
├── shellpack.py         # Main entry point
├── run.py               # One-liner launcher
├── shellpack.sh         # Legacy Bash script (deprecated)
├── shellpack.ps1        # PowerShell wrapper for Windows
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
└── LICENSE
```

---

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests: `python3 -c "from shellpack import core, backup, restore, cli"`
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Acknowledgments

- Inspired by the need to sync development environments across machines
- Built with love for the terminal community

---

<p align="center">
  Made with care by <a href="https://github.com/MoxForge">MoxForge</a>
</p>
