#!/usr/bin/env python3
import shutil
import tarfile
from pathlib import Path
from typing import List

from shellpack.core import (
    config, Colors, log,
    print_banner, print_header, print_section, print_status, print_item,
    print_error,
    read_input, read_yes_no, read_choice,
    run_command, command_exists,
    detect_os, detect_package_manager,
    check_dependencies, read_manifest,
    clone_repo, verify_ssh_connection,
    set_ssh_permissions, generate_ssh_key,
    copy_file,
)


def restore_fish(src_dir: Path) -> None:
    archive = src_dir / "shells" / "fish" / "fish_config.tar.gz"
    if not archive.is_file():
        print_status("Fish config not in backup", "skip")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would restore Fish config", "info")
        return
    dest = config.home / ".config"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(path=str(dest))
        print_status("Fish config", "ok")
    except Exception as e:
        print_error(f"Fish restore failed: {e}")


def restore_bash(src_dir: Path) -> None:
    files = [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"]
    found = 0
    for f in files:
        src = src_dir / "shells" / "bash" / f
        if src.is_file():
            if not config.dry_run:
                copy_file(src, config.home / f)
            found += 1
    if found > 0:
        print_status(f"Bash config ({found} files)", "ok")
    else:
        print_status("Bash config not in backup", "skip")


def restore_zsh(src_dir: Path) -> None:
    files = [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"]
    found = 0
    for f in files:
        src = src_dir / "shells" / "zsh" / f
        if src.is_file():
            if not config.dry_run:
                copy_file(src, config.home / f)
            found += 1
    omz_archive = src_dir / "shells" / "zsh" / "ohmyzsh.tar.gz"
    if omz_archive.is_file():
        if not config.dry_run:
            try:
                with tarfile.open(omz_archive, "r:gz") as tar:
                    tar.extractall(path=str(config.home))
            except Exception as e:
                log("WARN", f"Oh-My-Zsh restore failed: {e}")
        print_status("Zsh config + Oh-My-Zsh", "ok")
    elif found > 0:
        print_status(f"Zsh config ({found} files)", "ok")
    else:
        print_status("Zsh config not in backup", "skip")


def restore_starship(src_dir: Path) -> None:
    src = src_dir / "config" / "starship.toml"
    if not src.is_file():
        print_status("Starship config not in backup", "skip")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would restore Starship config", "info")
        return
    dest = config.home / ".config"
    dest.mkdir(parents=True, exist_ok=True)
    copy_file(src, dest / "starship.toml")
    print_status("Starship config", "ok")


def restore_git_config(src_dir: Path) -> None:
    src = src_dir / "config" / ".gitconfig"
    if not src.is_file():
        print_status("Git config not in backup", "skip")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would restore Git config", "info")
        return
    copy_file(src, config.home / ".gitconfig")
    print_status("Git config", "ok")


def setup_git_credential_helper(os_name: str) -> None:
    print_section("Git Credential Helper")
    print()
    print(f"  Git credential helpers securely store your credentials.")
    print()

    helper = ""
    if os_name == "macos":
        helper = "osxkeychain"
        print(f"  {Colors.GREEN}\u2713{Colors.NC} macOS Keychain available")
    elif os_name == "linux":
        if command_exists("gnome-keyring-daemon"):
            helper = "libsecret"
            print(f"  {Colors.GREEN}\u2713{Colors.NC} GNOME Keyring available")
        elif command_exists("pass"):
            helper = "pass"
            print(f"  {Colors.GREEN}\u2713{Colors.NC} pass (password store) available")
        else:
            helper = "cache --timeout=3600"
            print(f"  {Colors.YELLOW}!{Colors.NC} Using cache helper (1 hour timeout)")
            print(f"  {Colors.GRAY}Install gnome-keyring or pass for persistent storage{Colors.NC}")
    elif os_name == "wsl":
        gcm = Path("/mnt/c/Program Files/Git/mingw64/bin/git-credential-manager.exe")
        if gcm.is_file():
            helper = "manager"
            print(f"  {Colors.GREEN}\u2713{Colors.NC} Git Credential Manager (Windows) available")
        else:
            helper = "cache --timeout=3600"
            print(f"  {Colors.YELLOW}!{Colors.NC} Using cache helper (1 hour timeout)")
    else:
        helper = "cache --timeout=3600"
        print(f"  {Colors.YELLOW}!{Colors.NC} Using cache helper (1 hour timeout)")

    print()
    if read_yes_no(f"Configure Git credential helper ({helper})?", True):
        if not config.dry_run:
            run_command(["git", "config", "--global", "credential.helper", helper], check=False)
            print_status("Git credential helper configured", "ok")
        else:
            print_status("[DRY RUN] Would configure credential helper", "info")
    else:
        print_status("Git credential helper skipped", "skip")


def restore_ssh(src_dir: Path) -> bool:
    archive = src_dir / "ssh" / "ssh_backup.tar.gz"
    if not archive.is_file():
        return False
    if config.dry_run:
        print_status("[DRY RUN] Would restore SSH keys", "info")
        return True
    try:
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(path=str(config.home))
        set_ssh_permissions()
        print_status("SSH keys", "ok")
        return True
    except Exception as e:
        print_error(f"SSH restore failed: {e}")
        return False


def restore_conda(src_dir: Path, os_name: str, arch: str) -> None:
    conda_dir = src_dir / "conda"
    if not conda_dir.is_dir():
        print_status("Conda environments not in backup", "skip")
        return
    yml_files = list(conda_dir.glob("*.yml"))
    if not yml_files:
        print_status("Conda environments not in backup", "skip")
        return

    miniconda = config.home / "miniconda3"
    if not miniconda.is_dir():
        print()
        print(f"  {Colors.GRAY}Installing Miniconda...{Colors.NC}")
        if not config.dry_run:
            if os_name == "macos":
                suffix = "MacOSX-arm64" if arch == "arm64" else "MacOSX-x86_64"
            else:
                suffix = "Linux-x86_64"
            url = f"https://repo.anaconda.com/miniconda/Miniconda3-latest-{suffix}.sh"
            rc, _, _ = run_command(["curl", "-sL", url, "-o", "/tmp/miniconda.sh"], check=False, timeout=120)
            if rc == 0:
                run_command(["bash", "/tmp/miniconda.sh", "-b", "-p", str(miniconda)], check=False, timeout=300)
                Path("/tmp/miniconda.sh").unlink(missing_ok=True)
        print_status("Miniconda installed", "ok")

    conda_bin = str(miniconda / "bin" / "conda")
    if not config.dry_run and Path(conda_bin).is_file():
        for shell in ("bash", "fish", "zsh"):
            run_command([conda_bin, "init", shell], check=False, timeout=10)

    count = 0
    for yml in yml_files:
        env_name = yml.stem
        if env_name == "base":
            continue
        if not config.dry_run:
            run_command([conda_bin, "env", "create", "-f", str(yml), "-n", env_name], check=False, timeout=300)
        count += 1

    print_status(f"Conda environments ({count})", "ok")


def restore_history(src_dir: Path) -> None:
    history_dir = src_dir / "history"
    if not history_dir.is_dir():
        print_status("Shell history not in backup", "skip")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would restore shell history", "info")
        return
    found = False
    for name, dest in [
        (".bash_history", config.home / ".bash_history"),
        (".zsh_history", config.home / ".zsh_history"),
    ]:
        src = history_dir / name
        if src.is_file():
            copy_file(src, dest)
            found = True
    fish_src = history_dir / "fish"
    if fish_src.is_dir():
        fish_dest = config.home / ".local" / "share" / "fish"
        fish_dest.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copytree(str(fish_src), str(fish_dest), dirs_exist_ok=True)
            found = True
        except Exception:
            pass
    if found:
        print_status("Shell history", "ok")
    else:
        print_status("Shell history (nothing to restore)", "skip")


def restore_cloud_creds(src_dir: Path) -> None:
    cloud_dir = src_dir / "config" / "cloud"
    if not cloud_dir.is_dir():
        print_status("Cloud credentials not in backup", "skip")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would restore cloud credentials", "info")
        return
    found = 0
    for name, extract_to in [
        ("aws.tar.gz", config.home),
        ("azure.tar.gz", config.home),
        ("gcloud.tar.gz", config.home / ".config"),
    ]:
        archive = cloud_dir / name
        if archive.is_file():
            try:
                extract_to.mkdir(parents=True, exist_ok=True)
                with tarfile.open(archive, "r:gz") as tar:
                    tar.extractall(path=str(extract_to))
                found += 1
            except Exception as e:
                log("WARN", f"Cloud creds restore failed for {name}: {e}")
    if found > 0:
        print_status(f"Cloud credentials ({found})", "ok")


def install_shell(shell: str, pm: str) -> None:
    if command_exists(shell):
        print_status(f"{shell} (already installed)", "ok")
        return
    if config.dry_run:
        print_status(f"[DRY RUN] Would install {shell}", "info")
        return
    install_cmds = {
        "fish": {
            "apt": ["sudo", "apt", "install", "-y", "fish"],
            "brew": ["brew", "install", "fish"],
            "dnf": ["sudo", "dnf", "install", "-y", "fish"],
            "pacman": ["sudo", "pacman", "-S", "--noconfirm", "fish"],
        },
        "zsh": {
            "apt": ["sudo", "apt", "install", "-y", "zsh"],
            "brew": ["brew", "install", "zsh"],
            "dnf": ["sudo", "dnf", "install", "-y", "zsh"],
            "pacman": ["sudo", "pacman", "-S", "--noconfirm", "zsh"],
        },
    }
    cmd = install_cmds.get(shell, {}).get(pm)
    if cmd:
        if pm == "apt":
            run_command(["sudo", "apt-get", "update", "-qq"], check=False, timeout=120)
        run_command(cmd, check=False, timeout=120)
    if command_exists(shell):
        print_status(shell, "ok")
    else:
        print_status(f"{shell} installation failed", "error")


def install_starship() -> None:
    if command_exists("starship"):
        print_status("Starship (already installed)", "ok")
        return
    if config.dry_run:
        print_status("[DRY RUN] Would install Starship", "info")
        return
    run_command(
        ["sh", "-c", "curl -sS https://starship.rs/install.sh | sh -s -- -y"],
        check=False, timeout=120,
    )
    if command_exists("starship"):
        print_status("Starship", "ok")
    else:
        print_status("Starship installation failed", "warn")


def set_default_shell(shell: str) -> None:
    shell_path = shutil.which(shell)
    if not shell_path:
        print_status(f"Cannot find {shell} path", "error")
        return
    if config.dry_run:
        print_status(f"[DRY RUN] Would set default shell to {shell}", "info")
        return
    rc, _, _ = run_command(["grep", "-q", shell_path, "/etc/shells"], check=False)
    if rc != 0:
        run_command(["sudo", "tee", "-a", "/etc/shells"], check=False)
    rc, _, _ = run_command(["chsh", "-s", shell_path], check=False)
    if rc == 0:
        print_status(f"Default shell set to {shell}", "ok")
    else:
        import os as _os
        user = _os.environ.get("USER", "")
        rc2, _, _ = run_command(["sudo", "chsh", "-s", shell_path, user], check=False)
        if rc2 == 0:
            print_status(f"Default shell set to {shell}", "ok")
        else:
            print_status(f"Could not set default shell (try manually: chsh -s {shell_path})", "warn")


def do_restore() -> None:
    print_banner()
    print_header("Restore Shell Environment")

    if not check_dependencies():
        raise SystemExit(1)

    os_name, arch = detect_os()
    pm = detect_package_manager(os_name)

    print()
    print_status(f"Operating System: {os_name} ({arch})", "info")
    print_status(f"Package Manager: {pm}", "info")

    print_section("Backup Repository")
    print()
    print(f"  Enter the Git repository URL where your backups are stored.")
    print()

    repo_url = read_input("Repository URL")
    if not repo_url:
        print_error("Repository URL is required")
        raise SystemExit(1)

    print_section("Fetching Backups")
    print()

    config.setup()
    git_dir = config.temp_dir / "git"

    if repo_url.startswith("git@"):
        if not verify_ssh_connection(repo_url):
            raise SystemExit(1)

    print(f"  {Colors.GRAY}Cloning repository...{Colors.NC}")
    if not clone_repo(repo_url, git_dir):
        print_error("Failed to clone repository")
        raise SystemExit(1)

    backups: List[str] = []
    backups_dir = git_dir / "backups"
    if backups_dir.is_dir():
        backups = sorted([d.name for d in backups_dir.iterdir() if d.is_dir()])

    if not backups:
        print_error("No backups found in repository")
        raise SystemExit(1)

    print_status(f"Found {len(backups)} backup(s)", "ok")

    print_section("Select Backup")
    print()

    backup_choice = read_choice("Choose backup to restore", backups)
    backup_name = backups[backup_choice - 1]
    backup_dir = backups_dir / backup_name

    print_status(f"Selected: {backup_name}", "info")

    manifest_path = backup_dir / config.manifest_file
    if manifest_path.is_file():
        manifest = read_manifest(manifest_path)
        if manifest:
            print()
            print(f"  {Colors.GRAY}Backup details:{Colors.NC}")
            print_item(f"Created: {manifest.get('created', 'unknown')}")
            source = manifest.get("source", {})
            print_item(f"Source: {source.get('hostname', 'unknown')} ({source.get('os', 'unknown')})")

    print()
    if not read_yes_no("Continue with restore?", True):
        print(f"  {Colors.YELLOW}Restore cancelled.{Colors.NC}")
        raise SystemExit(0)

    print_section("SSH Keys")
    print()

    has_ssh_backup = (backup_dir / "ssh" / "ssh_backup.tar.gz").is_file()
    if has_ssh_backup:
        print(f"  Found SSH keys in backup.")
        print()
        ssh_choice = read_choice("What do you want to do?", [
            "Restore SSH keys from backup",
            "Generate new SSH keys",
            "Skip SSH setup",
        ])
        if ssh_choice == 1:
            restore_ssh(backup_dir)
        elif ssh_choice == 2:
            email = read_input("Enter email for SSH key")
            if email:
                generate_ssh_key(email)
        else:
            print_status("SSH setup skipped", "skip")
    else:
        print(f"  No SSH keys in backup.")
        if read_yes_no("Generate new SSH keys?", True):
            email = read_input("Enter email for SSH key")
            if email:
                (config.home / ".ssh").mkdir(mode=0o700, parents=True, exist_ok=True)
                generate_ssh_key(email)

    print_section("Shell Selection")
    print()

    available_shells: List[str] = []
    for s in ("fish", "bash", "zsh"):
        if (backup_dir / "shells" / s).is_dir():
            available_shells.append(s)
    if not available_shells:
        available_shells = ["bash"]

    print(f"  Shells available in backup:")
    for s in available_shells:
        print_item(s)
    print()

    shell_choice = read_choice("Select default shell", available_shells)
    default_shell = available_shells[shell_choice - 1]

    print_section("Installing Components")
    print()

    for shell in available_shells:
        install_shell(shell, pm)
    install_starship()

    print_section("Restoring Configurations")
    print()

    for shell in available_shells:
        if shell == "fish":
            restore_fish(backup_dir)
        elif shell == "bash":
            restore_bash(backup_dir)
        elif shell == "zsh":
            restore_zsh(backup_dir)

    restore_starship(backup_dir)
    restore_git_config(backup_dir)
    setup_git_credential_helper(os_name)
    restore_conda(backup_dir, os_name, arch)
    restore_history(backup_dir)
    restore_cloud_creds(backup_dir)

    print_section("Setting Default Shell")
    print()
    set_default_shell(default_shell)

    print()
    print(f"{Colors.GREEN}\u2554{'═' * 62}\u2557{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   {Colors.BOLD}RESTORE COMPLETE!{Colors.NC}{' ' * 42}{Colors.GREEN}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   Your shell environment has been restored.{' ' * 17}{Colors.GREEN}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   {Colors.YELLOW}Restart your terminal or run:{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   {Colors.CYAN}exec {default_shell}{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u255a{'═' * 62}\u255d{Colors.NC}")
    print()
