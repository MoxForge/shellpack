# Contributing to ShellPack

First off, thank you for considering contributing to ShellPack! 🎉

## How Can I Contribute?

### Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates.

When creating a bug report, include:
- **OS and version** (macOS 14.0, Ubuntu 24.04, Windows 11 + WSL2, etc.)
- **Shell** (Fish 3.6, Bash 5.2, Zsh 5.9, etc.)
- **Steps to reproduce** the issue
- **Expected behavior** vs **actual behavior**
- **Error messages** (if any)
- **Verbose output** (`shellsync --verbose backup`)

### Suggesting Features

Feature requests are welcome! Please include:
- **Use case**: Why is this feature needed?
- **Proposed solution**: How should it work?
- **Alternatives considered**: Other ways to solve the problem

### Pull Requests

1. **Fork** the repository
2. **Create a branch** for your feature (`git checkout -b feature/my-feature`)
3. **Make your changes**
4. **Test** on at least one platform (macOS, Linux, or WSL)
5. **Commit** with a clear message
6. **Push** to your fork
7. **Open a Pull Request**

## Development Setup

```bash
# Clone your fork
git clone git@github.com:YOUR_USERNAME/shellsync.git
cd shellsync

# Make the script executable
chmod +x shellsync.sh

# Test locally
./shellsync.sh --help
./shellsync.sh --dry-run backup
```

## Code Style

### Bash (shellsync.sh)
- Use `shellcheck` to lint: `shellcheck shellsync.sh`
- Use `set -euo pipefail` for safety
- Quote all variables: `"$var"` not `$var`
- Use `[[ ]]` instead of `[ ]` for tests
- Use meaningful function and variable names
- Add comments for complex logic

### PowerShell (shellsync.ps1)
- Follow [PowerShell Best Practices](https://docs.microsoft.com/en-us/powershell/scripting/developer/cmdlet/strongly-encouraged-development-guidelines)
- Use approved verbs (Get-, Set-, New-, etc.)
- Use PascalCase for function names
- Add comment-based help for functions

## Testing

Before submitting a PR, please test:

### Backup
- [ ] Full backup works
- [ ] Shareable backup excludes sensitive data
- [ ] All selected shells are backed up
- [ ] Manifest is created correctly

### Restore
- [ ] Restore from backup works
- [ ] Shells are installed correctly
- [ ] Configs are restored to correct locations
- [ ] SSH key options work (restore, generate, skip)

### Platforms (test on at least one)
- [ ] macOS
- [ ] Linux (Ubuntu/Debian)
- [ ] Linux (Fedora/RHEL)
- [ ] Linux (Arch)
- [ ] Windows WSL

## Questions?

Feel free to open an issue with the "question" label if you need help!
