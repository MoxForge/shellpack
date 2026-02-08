<p align="center">
  <h1 align="center">🔄 ShellPack</h1>
  <p align="center">
    <strong>Cross-Platform Shell Environment Backup & Restore</strong>
  </p>
  <p align="center">
    Backup your shell environment on macOS, restore it on Linux. Or vice versa.<br>
    One command. Zero hassle.
  </p>
  <p align="center">
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-features">Features</a> •
    <a href="#-usage">Usage</a> •
    <a href="#-what-gets-backed-up">What's Backed Up</a> •
    <a href="#-faq">FAQ</a>
  </p>
  <p align="center">
    <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version">
    <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
    <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20WSL-lightgrey.svg" alt="Platform">
    <img src="https://img.shields.io/badge/shells-Fish%20%7C%20Bash%20%7C%20Zsh-orange.svg" alt="Shells">
  </p>
</p>

---

> **🎉 Version 1.0.0 - Production Ready!**
> ShellPack has been enhanced with comprehensive security features, automatic rollback, retry logic, and improved error handling. See [IMPROVEMENTS.md](IMPROVEMENTS.md) for details.

---

## ⚡ Quick Start

**No installation required!** Run directly from GitHub:

### Backup (macOS / Linux / WSL)
```bash
bash <(curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.sh) backup
```

### Restore (macOS / Linux / WSL)
```bash
bash <(curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.sh) restore
```

### Windows PowerShell
```powershell
iex (irm https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.ps1)
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🌍 **Cross-Platform** | Works on macOS, Linux (Ubuntu, Debian, Fedora, Arch), and Windows WSL |
| 🚀 **Zero Installation** | Run directly from GitHub with a single command |
| 🔄 **Bi-directional** | Backup from any OS, restore to any OS |
| 📦 **Complete Backup** | Shell configs, packages, conda, SSH keys, and more |
| 🔒 **Shareable Mode** | Create backups safe to share publicly |
| 🆕 **Safe Restore** | Creates NEW WSL instances, never touches existing ones |
| ✅ **Integrity Check** | SHA-256 checksums verify backup integrity |
| 🎨 **Beautiful CLI** | Colored output, progress indicators, clear prompts |
| 🔐 **Security First** | Input validation, SSH key backup, secure password handling |
| 🔄 **Auto-Retry** | Network operations retry with exponential backoff |
| ↩️ **Rollback Support** | Automatic rollback on failed operations |
| 💾 **Smart Checks** | Disk space verification and backup size estimation |
| 🔑 **Git Credentials** | Automatic credential helper setup for seamless Git operations |

---

## 📖 Usage

### Backup Your Environment

```bash
shellpack backup
```

The script will:
1. Ask for your backup Git repository URL
2. Let you name your backup (default: `{shell}-{hostname}-{date}`)
3. Choose backup type (Full or Shareable)
4. Select which data to include
5. Push everything to your repository

### Restore Your Environment

```bash
shellpack restore
```

The script will:
1. Ask for your backup repository URL
2. Show available backups - pick one
3. Handle SSH keys (restore, generate new, or skip)
4. Install shells and tools automatically
5. Restore all configurations

### Command Line Options

```bash
shellpack backup              # Backup environment
shellpack restore             # Restore environment
shellpack --help              # Show help
shellpack --version           # Show version
shellpack --verbose backup    # Verbose output
shellpack --dry-run restore   # Preview without changes
```

### PowerShell Options

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

## 📦 What Gets Backed Up

| Component | macOS | Linux | WSL | Notes |
|-----------|:-----:|:-----:|:---:|-------|
| **Fish Shell** | ✅ | ✅ | ✅ | Config, functions, completions |
| **Bash** | ✅ | ✅ | ✅ | .bashrc, .bash_profile, aliases |
| **Zsh** | ✅ | ✅ | ✅ | .zshrc + Oh-My-Zsh |
| **Starship** | ✅ | ✅ | ✅ | starship.toml |
| **Packages** | brew | apt/dnf/pacman | apt | Package lists |
| **Conda** | ✅ | ✅ | ✅ | All environments |
| **Git Config** | ✅ | ✅ | ✅ | .gitconfig |
| **SSH Keys** | ✅ | ✅ | ✅ | Optional |
| **Cloud Creds** | ✅ | ✅ | ✅ | AWS/Azure/GCP (optional) |
| **History** | ✅ | ✅ | ✅ | Optional |

---

## 🔐 Backup Types

### Full Backup (Personal Use)
- Includes everything: SSH keys, credentials, history
- ⚠️ Keep your backup repository **private**

### Shareable Backup
- Safe to share publicly
- Automatically excludes:
  - SSH keys
  - Git identity (name/email)
  - Cloud credentials
  - Shell history
- Great for sharing your shell setup with others

---

## 💡 Example Workflows

### New Machine Setup

```bash
# On your new MacBook/Linux machine, just run:
bash <(curl -sL .../shellpack.sh) restore

# Enter your backup repo URL, pick a backup, done!
# All your tools, configs, and environments are restored.
```

### Sync Work and Home

```bash
# At work (Linux):
shellpack backup
# Creates: fish-work-pc-20250210

# At home (macOS):
shellpack restore
# Select the work backup
# Your work environment is now on your Mac!
```

### Share Your Setup

```bash
# Create a shareable backup:
shellpack backup
# Choose "Shareable backup"

# Share the repo URL with colleagues
# They run restore and get your shell setup (without your secrets)
```

---

## 🗂️ Repository Structure

After backup, your repository will contain:

```
your-backup-repo/
├── backups/
│   ├── fish-macbook-20250210/
│   │   ├── manifest.json           # Backup metadata + checksum
│   │   ├── shells/
│   │   │   ├── fish/
│   │   │   │   └── fish_config.tar.gz
│   │   │   ├── bash/
│   │   │   │   ├── .bashrc
│   │   │   │   └── .bash_profile
│   │   │   └── zsh/
│   │   │       ├── .zshrc
│   │   │       └── ohmyzsh.tar.gz
│   │   ├── packages/
│   │   │   ├── brew_formula.txt
│   │   │   └── brew_cask.txt
│   │   ├── conda/
│   │   │   ├── base.yml
│   │   │   └── ml.yml
│   │   ├── config/
│   │   │   ├── starship.toml
│   │   │   └── .gitconfig
│   │   └── ssh/
│   │       └── ssh_backup.tar.gz
│   └── fish-wsl-20250115/
│       └── ...
```

---

## 🛠️ Requirements

### macOS
- Git (install with `xcode-select --install`)
- curl (pre-installed)

### Linux
```bash
sudo apt install git curl  # Ubuntu/Debian
sudo dnf install git curl  # Fedora
sudo pacman -S git curl    # Arch
```

### Windows
- WSL2 (`wsl --install`)
- Git for Windows (optional, for direct Git operations)

---

## ❓ FAQ

<details>
<summary><strong>Will restore overwrite my existing WSL?</strong></summary>

**No!** On Windows, restore creates a NEW WSL instance with a name you choose. Your existing distributions are never touched.
</details>

<details>
<summary><strong>Can I backup from Mac and restore on Linux?</strong></summary>

**Yes!** That's the whole point. Shell configs are compatible. Package managers differ (brew vs apt), but ShellPack handles that by storing package lists for each platform.
</details>

<details>
<summary><strong>Is my data safe?</strong></summary>

- **Full backups** contain sensitive data → Keep your repo **private**
- **Shareable backups** exclude all secrets → Safe to make **public**
- All backups include SHA-256 checksums for integrity verification
</details>

<details>
<summary><strong>What if I don't have Fish/Zsh installed on the new machine?</strong></summary>

ShellPack automatically installs any shells that were in your backup. It detects your package manager (apt, brew, dnf, pacman) and installs appropriately.
</details>

<details>
<summary><strong>Can I have multiple backups?</strong></summary>

ShellPack automatically installs any shells that were in your backup. It detects your package manager (apt, brew, dnf, pacman) and installs appropriately.
</details>

---

## 🔒 Security Features

ShellPack is built with security as a priority:

### Input Validation
- **Git URL Validation**: All repository URLs are validated to prevent injection attacks
- **Backup Name Sanitization**: Backup names are sanitized to prevent path traversal attacks
- **Email Validation**: Email addresses are validated for SSH key generation

### SSH Key Security
- **Automatic Backup**: Existing SSH keys are backed up before generating new ones
- **Passphrase Protection**: Optional passphrase support for SSH keys
- **Proper Permissions**: Automatic permission setting (700 for .ssh, 600 for private keys, 644 for public keys)

### Secure Password Handling (PowerShell)
- **SecureString**: Passwords are handled as SecureString objects
- **Memory Cleanup**: Passwords are cleared from memory after use
- **No Plain Text Storage**: Passwords are never stored in plain text

### Network Security
- **Retry Logic**: Network operations retry with exponential backoff
- **Error Handling**: Comprehensive error checking for all operations
- **Rollback Support**: Failed operations can be automatically rolled back

### Git Credential Management
- **Platform-Specific Helpers**: Automatic detection and setup of credential helpers
  - macOS: osxkeychain
  - Linux: libsecret, pass, or cache
  - WSL: Git Credential Manager (Windows) or cache

---

## 🤝 Contributing

**Yes!** Each backup has a unique name (default: `shell-hostname-date`). You can keep as many as you want in your repository.
</details>

<details>
<summary><strong>How do I update ShellPack?</strong></summary>

No update needed! The one-liner always fetches the latest version from GitHub.
</details>

<details>
<summary><strong>What security measures are in place?</strong></summary>

ShellPack includes comprehensive security features:
- Input validation for all user inputs (URLs, backup names, emails)
- Automatic SSH key backup before generating new keys
- Secure password handling with memory cleanup (PowerShell)
- Proper file permissions for SSH keys
- Git credential helper support for secure authentication
- Rollback mechanism for failed operations

See the [Security Features](#-security-features) section for details.
</details>

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- Inspired by the need to sync development environments across machines
- Built with love for the terminal community

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/MoxForge">MoxForge</a>
</p>
