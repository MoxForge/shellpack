#!/usr/bin/env python3
"""Core utilities, configuration, and UI helpers for ShellPack."""

import os
import sys
import json
import shutil
import hashlib
import platform
import subprocess
import tempfile
import re
import time
import atexit
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

VERSION = "2.0.0"
SCRIPT_NAME = "shellpack"
GITHUB_REPO = "https://github.com/MoxForge/shellpack"


class Colors:
    if sys.stdout.isatty() and os.environ.get("TERM") != "dumb":
        RED = "\033[0;31m"
        GREEN = "\033[0;32m"
        YELLOW = "\033[0;33m"
        BLUE = "\033[0;34m"
        CYAN = "\033[0;36m"
        GRAY = "\033[0;90m"
        BOLD = "\033[1m"
        NC = "\033[0m"
    else:
        RED = GREEN = YELLOW = BLUE = CYAN = GRAY = BOLD = NC = ""


class Config:
    def __init__(self):
        self.temp_dir = Path(tempfile.gettempdir()) / f"{SCRIPT_NAME}_{os.getpid()}"
        self.manifest_file = "manifest.json"
        self.log_file = self.temp_dir / "shellpack.log"
        self.verbose = False
        self.dry_run = False
        self.home = Path.home()

    def setup(self):
        self.temp_dir.mkdir(parents=True, exist_ok=True)


config = Config()
rollback_stack: List[str] = []


def log(level: str, message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config.log_file, "a") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass
    if config.verbose or level == "ERROR":
        print(f"{Colors.GRAY}[{timestamp}]{Colors.NC} {message}", file=sys.stderr)


def print_banner():
    print()
    print(f"{Colors.CYAN}┌──────────────────────────────────────────────────────────────┐{Colors.NC}")
    print(f"{Colors.CYAN}│{Colors.NC}  {Colors.BOLD}ShellPack{Colors.NC} v{VERSION}                                            {Colors.CYAN}│{Colors.NC}")
    print(f"{Colors.CYAN}│{Colors.NC}  Cross-Platform Shell Environment Backup & Restore           {Colors.CYAN}│{Colors.NC}")
    print(f"{Colors.CYAN}└──────────────────────────────────────────────────────────────┘{Colors.NC}")
    print()


def print_header(title: str):
    print()
    print(f"{Colors.CYAN}══════════════════════════════════════════════════════════════{Colors.NC}")
    print(f"{Colors.CYAN}  {title}{Colors.NC}")
    print(f"{Colors.CYAN}══════════════════════════════════════════════════════════════{Colors.NC}")
    print()


def print_section(title: str):
    print()
    print(f"{Colors.YELLOW}──────────────────────────────────────────────────────────────{Colors.NC}")
    print(f"{Colors.YELLOW}  {title}{Colors.NC}")
    print(f"{Colors.YELLOW}──────────────────────────────────────────────────────────────{Colors.NC}")


def print_status(message: str, status: str = "info"):
    icons = {"ok": "✓", "success": "✓", "error": "✗", "fail": "✗", "warn": "!", "skip": "→", "info": "•"}
    colors_map = {
        "ok": Colors.GREEN, "success": Colors.GREEN, "error": Colors.RED, "fail": Colors.RED,
        "warn": Colors.YELLOW, "skip": Colors.GRAY, "info": Colors.BLUE,
    }
    icon = icons.get(status, " ")
    color = colors_map.get(status, Colors.NC)
    print(f"  {color}[{icon}]{Colors.NC} {message}")
    log("INFO", message)


def print_item(message: str):
    print(f"      {Colors.GRAY}•{Colors.NC} {message}")


def print_error(message: str):
    print(f"  {Colors.RED}[✗] ERROR:{Colors.NC} {message}", file=sys.stderr)
    log("ERROR", message)


def print_warning(message: str):
    print(f"  {Colors.YELLOW}[!] WARNING:{Colors.NC} {message}")
    log("WARN", message)


def print_success(message: str):
    print(f"  {Colors.GREEN}[✓]{Colors.NC} {message}")


def read_input(prompt: str, default: str = "") -> str:
    if default:
        display = f"  {Colors.CYAN}{prompt}{Colors.NC} [{Colors.GRAY}{default}{Colors.NC}]: "
    else:
        display = f"  {Colors.CYAN}{prompt}{Colors.NC}: "
    try:
        result = input(display).strip()
        return result if result else default
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def read_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    display = f"  {Colors.CYAN}{prompt}{Colors.NC} {suffix}: "
    try:
        result = input(display).strip().lower()
        if not result:
            return default
        return result in ("y", "yes")
    except (EOFError, KeyboardInterrupt):
        print()
        return default


def read_choice(prompt: str, options: List[str]) -> int:
    print()
    for i, opt in enumerate(options):
        print(f"      {Colors.GRAY}[{i + 1}]{Colors.NC} {opt}")
    print()
    while True:
        display = f"  {Colors.CYAN}{prompt}{Colors.NC} [{Colors.GRAY}1{Colors.NC}]: "
        try:
            result = input(display).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 1
        if not result:
            return 1
        if result.isdigit() and 1 <= int(result) <= len(options):
            return int(result)
        print_error(f"Invalid choice. Please enter 1-{len(options)}")


def read_password(prompt: str) -> str:
    import getpass
    try:
        return getpass.getpass(f"  {Colors.CYAN}{prompt}{Colors.NC}: ")
    except (EOFError, KeyboardInterrupt):
        print()
        return ""


def validate_git_url(url: str) -> bool:
    if not url:
        return False
    patterns = [
        r"^(https?|git|ssh)://[a-zA-Z0-9._-]+(/[a-zA-Z0-9._/-]+)?\.git$",
        r"^git@[a-zA-Z0-9._-]+:[a-zA-Z0-9._/-]+\.git$",
        r"^(https?|git|ssh)://[a-zA-Z0-9._-]+(/[a-zA-Z0-9._/-]+)?$",
    ]
    return any(re.match(p, url) for p in patterns)


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", email))


def sanitize_name(name: str) -> str:
    name = re.sub(r"[^a-zA-Z0-9._-]", "", name)
    name = re.sub(r"\.\.+", ".", name)
    if len(name) > 100:
        name = name[:100]
    if not name:
        name = f"backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    return name


def run_command(
    cmd: List[str], capture: bool = True, check: bool = True, timeout: int = 0
) -> Tuple[int, str, str]:
    try:
        kwargs: Dict[str, Any] = {"capture_output": capture, "text": True, "check": False}
        if timeout > 0:
            kwargs["timeout"] = timeout
        result = subprocess.run(cmd, **kwargs)
        if check and result.returncode != 0:
            log("ERROR", f"Command failed: {' '.join(cmd)}")
            log("ERROR", f"stderr: {result.stderr}")
        return result.returncode, result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        log("ERROR", f"Command timed out: {' '.join(cmd)}")
        return 1, "", "timeout"
    except Exception as e:
        log("ERROR", f"Command exception: {e}")
        return 1, "", str(e)


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def detect_os() -> Tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("arm64", "aarch64"):
        arch = "arm64"
    elif machine == "armv7l":
        arch = "arm"
    else:
        arch = machine
    if system == "darwin":
        return "macos", arch
    elif system == "linux":
        try:
            release = platform.uname().release.lower()
        except Exception:
            release = ""
        if "microsoft" in release:
            return "wsl", arch
        return "linux", arch
    return system, arch


def detect_package_manager(os_name: str = "") -> str:
    if os_name == "macos":
        return "brew"
    for pm in ("apt", "dnf", "yum", "pacman", "zypper", "apk"):
        if command_exists(pm):
            return pm
    return "unknown"


def detect_shell() -> str:
    shell = os.environ.get("SHELL", "/bin/bash")
    return Path(shell).name


def get_hostname() -> str:
    try:
        return platform.node() or "unknown"
    except Exception:
        return "unknown"


def check_disk_space(required_mb: int = 100, target_dir: Optional[Path] = None) -> bool:
    target = target_dir or config.temp_dir
    try:
        check_path = target.parent if not target.exists() else target
        stat = os.statvfs(check_path)
        available_mb = (stat.f_bavail * stat.f_frsize) // (1024 * 1024)
        if available_mb < required_mb:
            print_error(f"Insufficient disk space: {available_mb}MB available, {required_mb}MB required")
            return False
        log("INFO", f"Disk space check passed: {available_mb}MB available")
        return True
    except Exception as e:
        log("WARN", f"Could not check disk space: {e}")
        return True


def calculate_checksum(directory: Path) -> str:
    hasher = hashlib.sha256()
    for filepath in sorted(directory.rglob("*")):
        if filepath.is_file() and filepath.name != "manifest.json":
            try:
                hasher.update(filepath.read_bytes())
            except Exception:
                pass
    return hasher.hexdigest()


def check_dependencies() -> bool:
    print_section("Checking Dependencies")
    print()
    os_name, _ = detect_os()
    pm = detect_package_manager(os_name)
    missing = []
    for dep in ("git", "curl", "tar"):
        if command_exists(dep):
            print_status(dep, "ok")
        else:
            print_status(f"{dep} - MISSING", "error")
            missing.append(dep)
    print()
    print(f"  {Colors.GRAY}Optional:{Colors.NC}")
    for dep, label in [("jq", "jq (JSON parsing)"), ("ssh", "ssh")]:
        if command_exists(dep):
            print_status(label, "ok")
        else:
            print_status(f"{label} - not installed", "skip")
    if missing:
        print()
        print_error(f"Missing required dependencies: {' '.join(missing)}")
        install_hints = {
            "apt": f"sudo apt update && sudo apt install -y {' '.join(missing)}",
            "brew": f"brew install {' '.join(missing)}",
            "dnf": f"sudo dnf install -y {' '.join(missing)}",
            "pacman": f"sudo pacman -S {' '.join(missing)}",
        }
        hint = install_hints.get(pm, f"Please install: {' '.join(missing)}")
        print(f"  {Colors.YELLOW}Install them with:{Colors.NC}")
        print(f"    {Colors.CYAN}{hint}{Colors.NC}")
        print()
        return False
    return True


def retry_with_backoff(func, max_attempts: int = 3, delay: int = 2, max_delay: int = 30):
    attempt = 1
    current_delay = delay
    last_exc = None
    while attempt <= max_attempts:
        try:
            return func()
        except Exception as e:
            last_exc = e
            log("WARN", f"Attempt {attempt}/{max_attempts} failed: {e}")
            if attempt < max_attempts:
                time.sleep(current_delay)
                current_delay = min(current_delay * 2, max_delay)
            attempt += 1
    raise last_exc


def parse_github_url(url: str) -> str:
    m = re.search(r"github\.com[/:](.+?)(?:\.git)?$", url)
    if m:
        return m.group(1).rstrip("/")
    return ""


def clone_repo(repo_url: str, dest_dir: Path, depth: int = 1) -> bool:
    if config.dry_run:
        print_status(f"[DRY RUN] Would clone: {repo_url}", "info")
        return True
    log("INFO", f"Cloning repository: {repo_url} -> {dest_dir}")
    rc, _, err = run_command(["git", "clone", "--depth", str(depth), repo_url, str(dest_dir)], check=False)
    if rc == 0:
        print_status("Repository cloned", "ok")
        return True
    log("ERROR", f"Clone failed: {err}")
    return False


def init_repo(dest_dir: Path, repo_url: str) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    rc, _, _ = run_command(["git", "init"], capture=True, check=False)
    if rc != 0:
        return False
    run_command(["git", "-C", str(dest_dir), "remote", "add", "origin", repo_url], check=False)
    return True


def push_to_repo(repo_dir: Path, message: str) -> bool:
    if config.dry_run:
        print_status(f"[DRY RUN] Would push: {message}", "info")
        return True
    log("INFO", f"Pushing to repository: {message}")
    print(f"  {Colors.GRAY}Staging files...{Colors.NC}")
    rc, _, err = run_command(["git", "-C", str(repo_dir), "add", "-A"], check=False)
    if rc != 0:
        print_error(f"git add failed: {err}")
        return False
    print(f"  {Colors.GRAY}Creating commit...{Colors.NC}")
    rc, _, err = run_command(["git", "-C", str(repo_dir), "commit", "-m", message], check=False)
    if rc != 0:
        rc2, _, _ = run_command(["git", "-C", str(repo_dir), "diff", "--cached", "--quiet"], check=False)
        if rc2 == 0:
            log("INFO", "No changes to commit")
            print(f"  {Colors.YELLOW}No changes to commit{Colors.NC}")
    print(f"  {Colors.GRAY}Pushing to remote...{Colors.NC}")
    for branch in ("main", "master"):
        rc, _, err = run_command(
            ["git", "-C", str(repo_dir), "push", "-u", "origin", branch],
            check=False, timeout=60,
        )
        if rc == 0 or "Everything up-to-date" in err:
            return True
    print_error("Push failed - check authentication and network")
    print(f"  {Colors.RED}Push error:{Colors.NC} {err}", file=sys.stderr)
    return False


def verify_ssh_connection(repo_url: str) -> bool:
    m = re.match(r"git@([^:]+):", repo_url)
    if not m:
        return True
    host = m.group(1)
    print(f"  {Colors.GRAY}Verifying SSH connection...{Colors.NC}")
    _, out, err = run_command(
        ["ssh", "-T", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", f"git@{host}"],
        check=False, timeout=15,
    )
    combined = out + err
    if "successfully authenticated" in combined.lower() or "hi " in combined.lower():
        print_status("SSH connection verified", "ok")
        return True
    print_error(f"SSH authentication failed for {host}")
    print()
    print(f"  {Colors.YELLOW}Please ensure:{Colors.NC}")
    print(f"  {Colors.YELLOW}1. Your SSH key is added to your GitHub/GitLab account{Colors.NC}")
    print(f"  {Colors.YELLOW}2. Your SSH key is loaded in ssh-agent{Colors.NC}")
    print(f"  {Colors.YELLOW}3. You have access to the repository{Colors.NC}")
    return False


def set_ssh_permissions():
    ssh_dir = config.home / ".ssh"
    if not ssh_dir.is_dir():
        return
    try:
        ssh_dir.chmod(0o700)
        for f in ssh_dir.iterdir():
            if f.is_file():
                if f.name.startswith("id_") and not f.name.endswith(".pub"):
                    f.chmod(0o600)
                elif f.name.endswith(".pub"):
                    f.chmod(0o644)
                elif f.name == "config":
                    f.chmod(0o600)
                elif f.name == "known_hosts":
                    f.chmod(0o644)
                elif f.name == "authorized_keys":
                    f.chmod(0o600)
    except Exception as e:
        log("WARN", f"Could not set SSH permissions: {e}")


def generate_ssh_key(email: str, key_type: str = "ed25519", passphrase: str = "") -> bool:
    if not validate_email(email):
        print_error(f"Invalid email address: {email}")
        return False
    ssh_dir = config.home / ".ssh"
    ssh_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    key_file = ssh_dir / f"id_{key_type}"
    cmd = ["ssh-keygen", "-t", key_type, "-C", email, "-f", str(key_file), "-N", passphrase]
    rc, _, _ = run_command(cmd, check=False)
    if rc == 0:
        key_file.chmod(0o600)
        Path(f"{key_file}.pub").chmod(0o644)
        print_status("SSH key generated successfully", "ok")
        print()
        pub_key = Path(f"{key_file}.pub").read_text().strip()
        print(f"  {Colors.CYAN}Your new public key:{Colors.NC}")
        print(f"  {Colors.GRAY}{pub_key}{Colors.NC}")
        print()
        print(f"  {Colors.YELLOW}Add this key to GitHub/GitLab/Bitbucket to enable SSH access.{Colors.NC}")
        return True
    print_error("Failed to generate SSH key")
    return False


def create_manifest(
    dest_dir: Path, backup_name: str, backup_type: str,
    shells: List[str], os_name: str, arch: str, pm: str,
) -> bool:
    if config.dry_run:
        print_status("[DRY RUN] Would create manifest", "info")
        return True
    manifest = {
        "version": VERSION,
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "backup_name": backup_name,
        "backup_type": backup_type,
        "source": {
            "user": os.environ.get("USER", "unknown"),
            "hostname": get_hostname(),
            "os": os_name,
            "arch": arch,
            "package_manager": pm,
            "default_shell": detect_shell(),
        },
        "shells": shells,
        "checksum": "",
    }
    manifest_path = dest_dir / config.manifest_file
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
    except Exception as e:
        print_error(f"Failed to write manifest: {e}")
        return False
    print(f"  {Colors.GRAY}Calculating checksum...{Colors.NC}")
    checksum = calculate_checksum(dest_dir)
    manifest["checksum"] = checksum
    try:
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)
    except Exception:
        pass
    print_status("Manifest created", "ok")
    return True


def read_manifest(manifest_path: Path) -> Optional[Dict[str, Any]]:
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except Exception as e:
        log("ERROR", f"Failed to read manifest: {e}")
        return None


def add_rollback_action(action: str):
    rollback_stack.append(action)
    log("DEBUG", f"Added rollback action: {action}")


def execute_rollback():
    if not rollback_stack:
        return
    print_section("Rolling Back Changes")
    print()
    for action in reversed(rollback_stack):
        log("INFO", f"Executing rollback: {action}")
        try:
            subprocess.run(action, shell=True, capture_output=True)
        except Exception:
            pass
    rollback_stack.clear()
    print_status("Rollback completed", "ok")


def cleanup():
    if config.temp_dir.exists():
        log("INFO", f"Cleaning up temporary directory: {config.temp_dir}")
        shutil.rmtree(config.temp_dir, ignore_errors=True)


atexit.register(cleanup)


def dir_size_kb(path: Path) -> int:
    total = 0
    try:
        if path.is_file():
            return path.stat().st_size // 1024
        for f in path.rglob("*"):
            if f.is_file():
                total += f.stat().st_size
    except Exception:
        pass
    return total // 1024


def copy_file(src: Path, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return True
    except Exception as e:
        log("ERROR", f"Failed to copy {src} -> {dest}: {e}")
        return False


def copy_directory(src: Path, dest: Path) -> bool:
    try:
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        return True
    except Exception as e:
        log("ERROR", f"Failed to copy directory {src} -> {dest}: {e}")
        return False
