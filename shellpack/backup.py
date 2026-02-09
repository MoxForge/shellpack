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
    sanitize_name,
    run_command, command_exists,
    detect_os, detect_package_manager, detect_shell, get_hostname,
    check_dependencies,
    clone_repo, init_repo, push_to_repo, verify_ssh_connection,
    create_manifest, dir_size_kb, copy_file,
)


def backup_fish(dest_dir: Path) -> None:
    fish_dir = config.home / ".config" / "fish"
    if not fish_dir.is_dir():
        print_status("Fish config not found", "skip")
        return
    shells_dir = dest_dir / "shells" / "fish"
    shells_dir.mkdir(parents=True, exist_ok=True)
    if config.dry_run:
        print_status("[DRY RUN] Would backup Fish config", "info")
        return
    try:
        with tarfile.open(shells_dir / "fish_config.tar.gz", "w:gz") as tar:
            tar.add(str(fish_dir), arcname="fish")
        print_status("Fish config", "ok")
    except Exception as e:
        print_error(f"Fish backup failed: {e}")


def backup_bash(dest_dir: Path) -> None:
    files = [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"]
    shells_dir = dest_dir / "shells" / "bash"
    shells_dir.mkdir(parents=True, exist_ok=True)
    found = 0
    for f in files:
        src = config.home / f
        if src.is_file():
            if not config.dry_run:
                copy_file(src, shells_dir / f)
            found += 1
    if found > 0:
        print_status(f"Bash config ({found} files)", "ok")
    else:
        print_status("Bash config not found", "skip")


def backup_zsh(dest_dir: Path) -> None:
    files = [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"]
    shells_dir = dest_dir / "shells" / "zsh"
    shells_dir.mkdir(parents=True, exist_ok=True)
    found = 0
    for f in files:
        src = config.home / f
        if src.is_file():
            if not config.dry_run:
                copy_file(src, shells_dir / f)
            found += 1
    omz_dir = config.home / ".oh-my-zsh"
    if omz_dir.is_dir():
        if not config.dry_run:
            try:
                with tarfile.open(shells_dir / "ohmyzsh.tar.gz", "w:gz") as tar:
                    tar.add(str(omz_dir), arcname=".oh-my-zsh")
            except Exception as e:
                log("WARN", f"Oh-My-Zsh backup failed: {e}")
        print_status("Zsh config + Oh-My-Zsh", "ok")
    elif found > 0:
        print_status(f"Zsh config ({found} files)", "ok")
    else:
        print_status("Zsh config not found", "skip")


def backup_packages(dest_dir: Path, pm: str) -> None:
    pkg_dir = dest_dir / "packages"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    if config.dry_run:
        print_status(f"[DRY RUN] Would backup package list ({pm})", "info")
        return
    if pm == "apt":
        rc, out, _ = run_command(["apt", "list", "--installed"], check=False)
        if rc == 0:
            lines = [l for l in out.splitlines() if "Listing..." not in l]
            (pkg_dir / "apt_packages.txt").write_text("\n".join(lines) + "\n")
        rc, out, _ = run_command(["apt-mark", "showmanual"], check=False)
        if rc == 0:
            (pkg_dir / "apt_manual.txt").write_text(out)
        print_status("APT packages", "ok")
    elif pm == "brew":
        for sub, fname in [("list --formula", "brew_formula.txt"), ("list --cask", "brew_cask.txt"), ("leaves", "brew_leaves.txt")]:
            rc, out, _ = run_command(["brew"] + sub.split(), check=False)
            if rc == 0:
                (pkg_dir / fname).write_text(out)
        print_status("Homebrew packages", "ok")
    elif pm in ("dnf", "yum"):
        rc, out, _ = run_command(["rpm", "-qa"], check=False)
        if rc == 0:
            (pkg_dir / "rpm_packages.txt").write_text(out)
        print_status("RPM packages", "ok")
    elif pm == "pacman":
        rc, out, _ = run_command(["pacman", "-Qe"], check=False)
        if rc == 0:
            (pkg_dir / "pacman_packages.txt").write_text(out)
        rc, out, _ = run_command(["pacman", "-Qm"], check=False)
        if rc == 0:
            (pkg_dir / "pacman_aur.txt").write_text(out)
        print_status("Pacman packages", "ok")
    else:
        print_status(f"Package manager not supported: {pm}", "skip")


def backup_starship(dest_dir: Path) -> None:
    src = config.home / ".config" / "starship.toml"
    if not src.is_file():
        print_status("Starship config not found", "skip")
        return
    cfg_dir = dest_dir / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    if not config.dry_run:
        copy_file(src, cfg_dir / "starship.toml")
    print_status("Starship config", "ok")


def backup_git_config(dest_dir: Path) -> None:
    src = config.home / ".gitconfig"
    if not src.is_file():
        print_status("Git config not found", "skip")
        return
    cfg_dir = dest_dir / "config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    if not config.dry_run:
        copy_file(src, cfg_dir / ".gitconfig")
    print_status("Git config", "ok")


def backup_ssh(dest_dir: Path) -> bool:
    ssh_dir = config.home / ".ssh"
    if not ssh_dir.is_dir():
        print_status("SSH directory not found", "skip")
        return True
    out_dir = dest_dir / "ssh"
    out_dir.mkdir(parents=True, exist_ok=True)
    if config.dry_run:
        print_status("[DRY RUN] Would backup SSH keys", "info")
        return True
    try:
        with tarfile.open(out_dir / "ssh_backup.tar.gz", "w:gz") as tar:
            tar.add(str(ssh_dir), arcname=".ssh")
        print_status("SSH keys", "ok")
        return True
    except Exception as e:
        print_status("SSH keys backup failed", "error")
        log("ERROR", f"SSH backup error: {e}")
        return False


def backup_conda(dest_dir: Path) -> bool:
    conda_paths = [
        config.home / "miniconda3",
        config.home / "anaconda3",
        config.home / "miniforge3",
        Path("/opt/homebrew/Caskroom/miniconda/base"),
        Path("/usr/local/miniconda3"),
    ]
    conda_path = None
    for p in conda_paths:
        if (p / "bin" / "conda").is_file():
            conda_path = p
            break
    if conda_path is None:
        print_status("Conda not found", "skip")
        return True
    conda_dir = dest_dir / "conda"
    conda_dir.mkdir(parents=True, exist_ok=True)
    if config.dry_run:
        print_status("[DRY RUN] Would backup Conda environments", "info")
        return True
    conda_bin = str(conda_path / "bin" / "conda")
    rc, out, _ = run_command([conda_bin, "env", "list"], check=False, timeout=10)
    if rc != 0:
        print_status("Conda environments (timeout or error)", "warn")
        return True
    envs = []
    for line in out.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        name = parts[0]
        if name != "*" and name.replace("-", "").replace("_", "").isalnum():
            envs.append(name)
    count = 0
    for env in envs:
        rc, out, _ = run_command([conda_bin, "env", "export", "-n", env], check=False, timeout=30)
        if rc == 0:
            (conda_dir / f"{env}.yml").write_text(out)
            count += 1
    if count > 0:
        print_status(f"Conda environments ({count})", "ok")
    else:
        print_status("Conda environments (none exported)", "warn")
    return True


def backup_history(dest_dir: Path) -> None:
    history_dir = dest_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    if config.dry_run:
        print_status("[DRY RUN] Would backup shell history", "info")
        return
    found = False
    for name in (".bash_history", ".zsh_history"):
        src = config.home / name
        if src.is_file():
            if copy_file(src, history_dir / name):
                found = True
    fish_hist = config.home / ".local" / "share" / "fish"
    if fish_hist.is_dir():
        try:
            shutil.copytree(str(fish_hist), str(history_dir / "fish"), dirs_exist_ok=True)
            found = True
        except Exception:
            pass
    if found:
        print_status("Shell history", "ok")
    else:
        print_status("Shell history (not found)", "skip")


def backup_cloud_creds(dest_dir: Path) -> None:
    cloud_dir = dest_dir / "config" / "cloud"
    cloud_dir.mkdir(parents=True, exist_ok=True)
    found = 0
    if not config.dry_run:
        for name, src_path, arcname in [
            ("aws", config.home / ".aws", ".aws"),
            ("azure", config.home / ".azure", ".azure"),
            ("gcloud", config.home / ".config" / "gcloud", "gcloud"),
        ]:
            if src_path.is_dir():
                try:
                    with tarfile.open(cloud_dir / f"{name}.tar.gz", "w:gz") as tar:
                        tar.add(str(src_path), arcname=arcname)
                    found += 1
                except Exception as e:
                    log("WARN", f"Cloud creds backup failed for {name}: {e}")
    if found > 0 or config.dry_run:
        print_status(f"Cloud credentials ({found})", "ok")
    else:
        print_status("Cloud credentials not found", "skip")


def estimate_backup_size(
    shells: List[str], include_git_config: bool, include_ssh: bool,
    include_conda: bool, include_history: bool,
) -> int:
    total = 0
    for shell in shells:
        if shell == "fish":
            d = config.home / ".config" / "fish"
            if d.is_dir():
                total += dir_size_kb(d)
        elif shell == "bash":
            for f in (".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"):
                p = config.home / f
                if p.is_file():
                    total += dir_size_kb(p)
        elif shell == "zsh":
            for f in (".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"):
                p = config.home / f
                if p.is_file():
                    total += dir_size_kb(p)
            omz = config.home / ".oh-my-zsh"
            if omz.is_dir():
                total += dir_size_kb(omz)
    starship = config.home / ".config" / "starship.toml"
    if starship.is_file():
        total += dir_size_kb(starship)
    if include_git_config:
        gc = config.home / ".gitconfig"
        if gc.is_file():
            total += dir_size_kb(gc)
    if include_ssh:
        sd = config.home / ".ssh"
        if sd.is_dir():
            total += dir_size_kb(sd)
    if include_conda:
        conda_dir = config.home / "miniconda3"
        if not conda_dir.is_dir():
            conda_dir = config.home / "anaconda3"
        if conda_dir.is_dir():
            total += 50
    if include_history:
        for f in (".bash_history", ".zsh_history", ".local/share/fish/fish_history"):
            p = config.home / f
            if p.is_file():
                total += dir_size_kb(p)
    return total


def do_backup() -> None:
    print_banner()
    print_header("Backup Shell Environment")

    if not check_dependencies():
        raise SystemExit(1)

    os_name, arch = detect_os()
    pm = detect_package_manager(os_name)

    print()
    print_status(f"Operating System: {os_name} ({arch})", "info")
    print_status(f"Package Manager: {pm}", "info")

    print_section("Backup Repository")
    print()
    print(f"  Enter the Git repository URL where backups will be stored.")
    print(f"  {Colors.GRAY}Example: git@github.com:username/my-shell-backup.git{Colors.NC}")
    print()

    repo_url = read_input("Repository URL")
    if not repo_url:
        print_error("Repository URL is required")
        raise SystemExit(1)

    hostname = get_hostname().lower()
    hostname = "".join(c for c in hostname if c.isalnum() or c == "-")
    default_shell = detect_shell()
    date_stamp = __import__("datetime").datetime.now().strftime("%Y%m%d")
    default_name = f"{default_shell}-{hostname}-{date_stamp}"

    print()
    print(f"  {Colors.GRAY}Suggested name: {default_name}{Colors.NC}")
    print(f"  {Colors.GRAY}Format: {{shell}}-{{hostname}}-{{date}}{Colors.NC}")

    backup_name = read_input("Backup name", default_name)
    backup_name = sanitize_name(backup_name)

    print_section("Backup Type")
    print()
    print(f"  {Colors.GRAY}[1]{Colors.NC} {Colors.BOLD}Full Backup{Colors.NC} - For personal use (includes sensitive data)")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Shell configs (.bashrc, .zshrc, etc.)")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Starship configuration")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Git config {Colors.YELLOW}(includes user.name, user.email){Colors.NC}")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} SSH keys {Colors.YELLOW}(private keys included){Colors.NC}")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Conda environments")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Shell history")
    print()
    print(f"  {Colors.GRAY}[2]{Colors.NC} {Colors.BOLD}Shareable Backup{Colors.NC} - Safe to share publicly (excludes sensitive data)")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Shell configs (.bashrc, .zshrc, etc.)")
    print(f"      {Colors.GREEN}\u2713{Colors.NC} Starship configuration")
    print(f"      {Colors.RED}\u2717{Colors.NC} Git config {Colors.GRAY}(excluded){Colors.NC}")
    print(f"      {Colors.RED}\u2717{Colors.NC} SSH keys {Colors.GRAY}(excluded){Colors.NC}")
    print(f"      {Colors.RED}\u2717{Colors.NC} Conda environments {Colors.GRAY}(excluded){Colors.NC}")
    print(f"      {Colors.RED}\u2717{Colors.NC} Shell history {Colors.GRAY}(excluded){Colors.NC}")
    print()

    type_choice = read_choice(
        "Select backup type",
        ["Full backup (personal use)", "Shareable backup (safe to share)"],
    )
    is_shareable = type_choice == 2

    include_ssh = False
    include_git_cfg = False
    include_history = False
    include_cloud_creds = False
    include_conda = True

    if is_shareable:
        print_section("Shareable Backup")
        print()
        print(f"  {Colors.YELLOW}The following will be EXCLUDED:{Colors.NC}")
        print_item("SSH keys")
        print_item("Git config (name/email)")
        print_item("Shell history")
        print_item("Cloud credentials")
        print()
        print(f"  {Colors.GREEN}The following will be INCLUDED:{Colors.NC}")
        print_item("Shell configurations")
        print_item("Starship config")
        print_item("Package list")
        print()
        include_conda = read_yes_no("Include Conda environments?", True)
    else:
        print_section("Select Data to Backup")
        print()
        include_ssh = read_yes_no("Include SSH keys?", True)
        include_git_cfg = read_yes_no("Include Git config?", True)
        include_history = read_yes_no("Include shell history?", False)
        include_cloud_creds = read_yes_no("Include cloud credentials (AWS/Azure/GCP)?", False)
        include_conda = read_yes_no("Include Conda environments?", True)

    print_section("Shell Selection")
    print()
    print("  Detected shells:")

    shells_to_backup: List[str] = []
    for shell_name in ("fish", "bash", "zsh"):
        if command_exists(shell_name):
            mark = f" {Colors.GREEN}(default){Colors.NC}" if default_shell == shell_name else ""
            extra = ""
            if shell_name == "zsh" and (config.home / ".oh-my-zsh").is_dir():
                extra = " + Oh-My-Zsh"
            print(f"      {Colors.GRAY}\u2022{Colors.NC} {shell_name.capitalize()}{extra}{mark}")
            if read_yes_no(f"    Backup {shell_name.capitalize()}?", True):
                shells_to_backup.append(shell_name)

    print_section("Estimating Backup Size")
    print()
    total_kb = estimate_backup_size(shells_to_backup, include_git_cfg, include_ssh, include_conda, include_history)
    if total_kb >= 1024:
        print(f"  Estimated size: {Colors.CYAN}{total_kb // 1024}MB{Colors.NC}")
    else:
        print(f"  Estimated size: {Colors.CYAN}{total_kb}KB{Colors.NC}")

    config.setup()

    print_section("Creating Backup")
    print()

    backup_dir = config.temp_dir / "backup" / backup_name
    for sub in ("shells", "packages", "config", "conda", "ssh"):
        (backup_dir / sub).mkdir(parents=True, exist_ok=True)

    for shell in shells_to_backup:
        if shell == "fish":
            backup_fish(backup_dir)
        elif shell == "bash":
            backup_bash(backup_dir)
        elif shell == "zsh":
            backup_zsh(backup_dir)

    backup_packages(backup_dir, pm)
    backup_starship(backup_dir)

    if include_git_cfg:
        backup_git_config(backup_dir)
    else:
        print_status("Git config (excluded)", "skip")

    if include_ssh:
        if not backup_ssh(backup_dir):
            print_error("SSH backup failed, but continuing...")
    else:
        print_status("SSH keys (excluded)", "skip")

    if include_conda:
        backup_conda(backup_dir)
    else:
        print_status("Conda environments (excluded)", "skip")

    if include_history:
        backup_history(backup_dir)
    else:
        print_status("Shell history (excluded)", "skip")

    if include_cloud_creds:
        backup_cloud_creds(backup_dir)
    else:
        print_status("Cloud credentials (excluded)", "skip")

    print()
    print_section("Finalizing Backup")

    print(f"  {Colors.GRAY}Creating backup manifest...{Colors.NC}")
    backup_type = "shareable" if is_shareable else "full"
    create_manifest(backup_dir, backup_name, backup_type, shells_to_backup, os_name, arch, pm)

    print_section("Pushing to Repository")
    print()

    git_dir = config.temp_dir / "git"

    if repo_url.startswith("git@"):
        if not verify_ssh_connection(repo_url):
            print()
            print(f"  {Colors.GRAY}Your backup is saved locally at:{Colors.NC}")
            print(f"  {Colors.CYAN}{backup_dir}{Colors.NC}")
            raise SystemExit(1)

    print(f"  {Colors.GRAY}Cloning repository...{Colors.NC}")
    if not clone_repo(repo_url, git_dir):
        print(f"  {Colors.YELLOW}Clone failed, initializing new repository...{Colors.NC}")
        if not init_repo(git_dir, repo_url):
            print_error("Failed to initialize git repository")
            raise SystemExit(1)

    backups_dest = git_dir / "backups"
    backups_dest.mkdir(parents=True, exist_ok=True)
    print(f"  {Colors.GRAY}Copying backup files...{Colors.NC}")
    try:
        shutil.copytree(str(backup_dir), str(backups_dest / backup_name), dirs_exist_ok=True)
    except Exception as e:
        print_error(f"Failed to copy backup files: {e}")
        raise SystemExit(1)
    print_status("Backup files copied", "ok")

    if push_to_repo(git_dir, f"Backup: {backup_name}"):
        print_status("Pushed to repository", "ok")
    else:
        print_error("Failed to push to repository")
        print()
        print(f"  {Colors.YELLOW}Your backup is saved locally at:{Colors.NC}")
        print(f"  {Colors.CYAN}{backup_dir}{Colors.NC}")
        print()
        print(f"  {Colors.YELLOW}You can manually push it later:{Colors.NC}")
        print(f"  {Colors.GRAY}cd {git_dir} && git push -u origin main{Colors.NC}")
        raise SystemExit(1)

    print()
    print(f"{Colors.GREEN}\u2554{'═' * 62}\u2557{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   {Colors.BOLD}BACKUP COMPLETE!{Colors.NC}{' ' * 43}{Colors.GREEN}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   Backup: {Colors.CYAN}{backup_name}{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   Repository: {Colors.CYAN}{repo_url}{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   To restore on another machine:")
    print(f"{Colors.GREEN}\u2551{Colors.NC}   {Colors.GRAY}python3 <(curl -sL .../run.py) restore{Colors.NC}")
    print(f"{Colors.GREEN}\u2551{' ' * 62}\u2551{Colors.NC}")
    print(f"{Colors.GREEN}\u255a{'═' * 62}\u255d{Colors.NC}")
    print()
