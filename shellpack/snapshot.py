#!/usr/bin/env python3
"""Snapshot infrastructure for safe rollback and pre-sync backups."""

import json
import shutil
import tarfile
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from shellpack.core import (
    config, log, print_status, print_error, print_item,
    safe_extract_tar, copy_file, run_command,
)

SNAPSHOT_DIR = config.home / ".shellpack" / "snapshots"
SNAPSHOT_MAX_AGE_DAYS = 30
SNAPSHOT_MAX_COUNT = 10


def _ensure_snapshot_dir() -> Path:
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    return SNAPSHOT_DIR


def create_snapshot(
    name: Optional[str] = None,
    include_shells: bool = True,
    include_packages: bool = True,
    include_config: bool = True,
    include_ssh: bool = False,
    include_conda: bool = False,
    include_history: bool = False,
    include_cloud: bool = False,
) -> Optional[Path]:
    """Create a snapshot of the current shell environment.

    Returns the path to the created snapshot directory, or None on failure.
    Snapshots are stored in ~/.shellpack/snapshots/.
    """
    snapshot_dir = _ensure_snapshot_dir()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    snap_name = name or f"pre-sync-{timestamp}"
    snap_path = snapshot_dir / snap_name
    snap_path.mkdir(parents=True, exist_ok=True)

    if config.dry_run:
        print_status(f"[DRY RUN] Would create snapshot: {snap_name}", "info")
        return snap_path

    manifest: Dict[str, Any] = {
        "version": "2.1.0",
        "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "name": snap_name,
        "components": [],
    }

    try:
        # Snapshot shells
        if include_shells:
            shells_dir = snap_path / "shells"
            shells_dir.mkdir(parents=True, exist_ok=True)

            fish_dir = config.home / ".config" / "fish"
            if fish_dir.is_dir():
                with tarfile.open(shells_dir / "fish.tar.gz", "w:gz") as tar:
                    tar.add(str(fish_dir), arcname="fish")
                manifest["components"].append("fish")

            bash_files = [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"]
            bash_snap = shells_dir / "bash"
            bash_snap.mkdir(parents=True, exist_ok=True)
            for f in bash_files:
                src = config.home / f
                if src.is_file():
                    copy_file(src, bash_snap / f)
            if any((bash_snap / f).is_file() for f in bash_files):
                manifest["components"].append("bash")

            zsh_files = [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"]
            zsh_snap = shells_dir / "zsh"
            zsh_snap.mkdir(parents=True, exist_ok=True)
            for f in zsh_files:
                src = config.home / f
                if src.is_file():
                    copy_file(src, zsh_snap / f)
            if any((zsh_snap / f).is_file() for f in zsh_files):
                manifest["components"].append("zsh")

            omz_dir = config.home / ".oh-my-zsh"
            if omz_dir.is_dir():
                with tarfile.open(shells_dir / "ohmyzsh.tar.gz", "w:gz") as tar:
                    tar.add(str(omz_dir), arcname=".oh-my-zsh")
                manifest["components"].append("oh-my-zsh")

        # Snapshot packages
        if include_packages:
            pkg_dir = snap_path / "packages"
            pkg_dir.mkdir(parents=True, exist_ok=True)
            from shellpack.core import detect_package_manager, detect_os
            os_name, _ = detect_os()
            pm = detect_package_manager(os_name)
            if pm == "brew":
                rc, out, _ = run_command(["brew", "list"], capture=True, check=False)
                if rc == 0 and out:
                    (pkg_dir / "brew.txt").write_text(out)
                    manifest["components"].append("packages")
            elif pm == "apt":
                rc, out, _ = run_command(["apt", "list", "--installed"], capture=True, check=False)
                if rc == 0 and out:
                    (pkg_dir / "apt.txt").write_text(out)
                    manifest["components"].append("packages")
            elif pm == "dnf":
                rc, out, _ = run_command(["dnf", "list", "installed"], capture=True, check=False)
                if rc == 0 and out:
                    (pkg_dir / "dnf.txt").write_text(out)
                    manifest["components"].append("packages")
            elif pm == "pacman":
                rc, out, _ = run_command(["pacman", "-Q"], capture=True, check=False)
                if rc == 0 and out:
                    (pkg_dir / "pacman.txt").write_text(out)
                    manifest["components"].append("packages")

        # Snapshot config
        if include_config:
            cfg_dir = snap_path / "config"
            cfg_dir.mkdir(parents=True, exist_ok=True)

            starship = config.home / ".config" / "starship.toml"
            if starship.is_file():
                copy_file(starship, cfg_dir / "starship.toml")
                manifest["components"].append("starship")

            gitconfig = config.home / ".gitconfig"
            if gitconfig.is_file():
                copy_file(gitconfig, cfg_dir / ".gitconfig")
                manifest["components"].append("git")

        # Snapshot SSH
        if include_ssh:
            ssh_dir = config.home / ".ssh"
            if ssh_dir.is_dir():
                ssh_snap = snap_path / "ssh"
                ssh_snap.mkdir(parents=True, exist_ok=True)
                with tarfile.open(ssh_snap / "ssh.tar.gz", "w:gz") as tar:
                    tar.add(str(ssh_dir), arcname=".ssh")
                manifest["components"].append("ssh")

        # Snapshot history
        if include_history:
            hist_dir = snap_path / "history"
            hist_dir.mkdir(parents=True, exist_ok=True)
            for name in [".bash_history", ".zsh_history"]:
                src = config.home / name
                if src.is_file():
                    copy_file(src, hist_dir / name)
            fish_hist = config.home / ".local" / "share" / "fish"
            if fish_hist.is_dir():
                shutil.copytree(str(fish_hist), str(hist_dir / "fish"), dirs_exist_ok=True)
            if any(hist_dir.iterdir()):
                manifest["components"].append("history")

        # Snapshot cloud
        if include_cloud:
            cloud_dir = snap_path / "cloud"
            cloud_dir.mkdir(parents=True, exist_ok=True)
            for name, src_path in [
                ("aws", config.home / ".aws"),
                ("azure", config.home / ".azure"),
                ("gcloud", config.home / ".config" / "gcloud"),
            ]:
                if src_path.is_dir():
                    with tarfile.open(cloud_dir / f"{name}.tar.gz", "w:gz") as tar:
                        tar.add(str(src_path), arcname=src_path.name)
                    manifest["components"].append(f"cloud-{name}")

        # Write manifest
        manifest_path = snap_path / "snapshot.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=4)

        log("INFO", f"Snapshot created: {snap_path}")
        return snap_path

    except Exception as e:
        log("ERROR", f"Snapshot creation failed: {e}")
        # Clean up partial snapshot
        try:
            shutil.rmtree(snap_path)
        except Exception:
            pass
        return None


def restore_from_snapshot(snapshot_path: Path) -> bool:
    """Restore the environment from a snapshot.

    This overwrites current files with the snapshot contents.
    Use with caution - preferably after creating a new snapshot first.
    """
    if not snapshot_path.is_dir():
        print_error(f"Snapshot not found: {snapshot_path}")
        return False

    manifest_path = snapshot_path / "snapshot.json"
    if not manifest_path.is_file():
        print_error(f"Invalid snapshot (no manifest): {snapshot_path}")
        return False

    if config.dry_run:
        print_status(f"[DRY RUN] Would restore from snapshot: {snapshot_path.name}", "info")
        return True

    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
    except Exception as e:
        print_error(f"Failed to read snapshot manifest: {e}")
        return False

    components = manifest.get("components", [])
    success = True

    try:
        # Restore shells
        shells_dir = snapshot_path / "shells"
        if shells_dir.is_dir():
            fish_tar = shells_dir / "fish.tar.gz"
            if fish_tar.is_file() and "fish" in components:
                dest = config.home / ".config"
                dest.mkdir(parents=True, exist_ok=True)
                safe_extract_tar(fish_tar, dest)

            bash_snap = shells_dir / "bash"
            if bash_snap.is_dir() and "bash" in components:
                for f in [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"]:
                    src = bash_snap / f
                    if src.is_file():
                        copy_file(src, config.home / f)

            zsh_snap = shells_dir / "zsh"
            if zsh_snap.is_dir() and "zsh" in components:
                for f in [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"]:
                    src = zsh_snap / f
                    if src.is_file():
                        copy_file(src, config.home / f)

            omz_tar = shells_dir / "ohmyzsh.tar.gz"
            if omz_tar.is_file() and "oh-my-zsh" in components:
                safe_extract_tar(omz_tar, config.home)

        # Restore config
        cfg_dir = snapshot_path / "config"
        if cfg_dir.is_dir():
            starship = cfg_dir / "starship.toml"
            if starship.is_file() and "starship" in components:
                dest = config.home / ".config"
                dest.mkdir(parents=True, exist_ok=True)
                copy_file(starship, dest / "starship.toml")

            gitconfig = cfg_dir / ".gitconfig"
            if gitconfig.is_file() and "git" in components:
                copy_file(gitconfig, config.home / ".gitconfig")

        # Restore SSH
        ssh_dir = snapshot_path / "ssh"
        if ssh_dir.is_dir() and "ssh" in components:
            ssh_tar = ssh_dir / "ssh.tar.gz"
            if ssh_tar.is_file():
                safe_extract_tar(ssh_tar, config.home)

        # Restore history
        hist_dir = snapshot_path / "history"
        if hist_dir.is_dir() and "history" in components:
            for name in [".bash_history", ".zsh_history"]:
                src = hist_dir / name
                if src.is_file():
                    copy_file(src, config.home / name)
            fish_hist = hist_dir / "fish"
            if fish_hist.is_dir():
                dest = config.home / ".local" / "share" / "fish"
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copytree(str(fish_hist), str(dest), dirs_exist_ok=True)

        # Restore cloud
        cloud_dir = snapshot_path / "cloud"
        if cloud_dir.is_dir():
            for name, extract_to in [
                ("aws", config.home),
                ("azure", config.home),
                ("gcloud", config.home / ".config"),
            ]:
                tar_path = cloud_dir / f"{name}.tar.gz"
                if tar_path.is_file() and f"cloud-{name}" in components:
                    extract_to.mkdir(parents=True, exist_ok=True)
                    safe_extract_tar(tar_path, extract_to)

        log("INFO", f"Snapshot restored: {snapshot_path}")
        return True

    except Exception as e:
        log("ERROR", f"Snapshot restore failed: {e}")
        return False


def list_snapshots() -> List[Dict[str, Any]]:
    """Return a list of available snapshots sorted by creation time (newest first)."""
    snapshot_dir = _ensure_snapshot_dir()
    snapshots: List[Dict[str, Any]] = []

    for entry in sorted(snapshot_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_dir():
            continue
        manifest_path = entry / "snapshot.json"
        if not manifest_path.is_file():
            continue
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            snapshots.append({
                "name": manifest.get("name", entry.name),
                "created": manifest.get("created", "unknown"),
                "components": manifest.get("components", []),
                "path": entry,
            })
        except Exception:
            continue

    return snapshots


def prune_snapshots(
    max_age_days: int = SNAPSHOT_MAX_AGE_DAYS,
    max_count: int = SNAPSHOT_MAX_COUNT,
) -> int:
    """Remove old snapshots beyond max_age_days and max_count.

    Returns the number of snapshots removed.
    """
    snapshot_dir = _ensure_snapshot_dir()
    removed = 0
    now = datetime.now(timezone.utc)

    entries = list(snapshot_dir.iterdir())
    entries.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    for i, entry in enumerate(entries):
        if not entry.is_dir():
            continue

        # Remove if beyond max count
        if i >= max_count:
            try:
                shutil.rmtree(entry)
                removed += 1
                continue
            except Exception:
                continue

        # Remove if beyond max age
        try:
            mtime = datetime.fromtimestamp(entry.stat().st_mtime, tz=timezone.utc)
            age_days = (now - mtime).days
            if age_days > max_age_days:
                shutil.rmtree(entry)
                removed += 1
        except Exception:
            continue

    if removed > 0:
        log("INFO", f"Pruned {removed} old snapshot(s)")
    return removed
