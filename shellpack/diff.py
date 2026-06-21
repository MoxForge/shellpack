#!/usr/bin/env python3
"""Diff engine for comparing local environment against backups."""

import difflib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from shellpack.core import config, log


class DiffStatus(str, Enum):
    IDENTICAL = "identical"
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    CONFLICT = "conflict"
    MISSING_LOCAL = "missing_local"
    MISSING_BACKUP = "missing_backup"


class ChangeAction(str, Enum):
    NONE = "none"
    OVERWRITE = "overwrite"
    MERGE = "merge"
    SKIP = "skip"
    INSTALL = "install"


@dataclass
class FileDiff:
    path: Path
    status: DiffStatus
    backup_path: Optional[Path] = None
    local_path: Optional[Path] = None
    backup_size: int = 0
    local_size: int = 0
    unified_diff: str = ""
    action: ChangeAction = ChangeAction.NONE


@dataclass
class ComponentDiff:
    name: str
    status: DiffStatus
    files: List[FileDiff] = field(default_factory=list)
    action: ChangeAction = ChangeAction.NONE
    details: str = ""


def _file_checksum(path: Path) -> str:
    """Compute a quick checksum for comparison."""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()[:16]
    except Exception:
        return ""


def _read_text_safe(path: Path) -> str:
    """Read text file, trying multiple encodings."""
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return ""


def diff_text_files(
    local_path: Path,
    backup_path: Path,
    context_lines: int = 3,
) -> str:
    """Generate a unified diff between two text files."""
    local_lines = _read_text_safe(local_path).splitlines(keepends=True)
    backup_lines = _read_text_safe(backup_path).splitlines(keepends=True)

    # Ensure lines end with newline for clean diff
    if local_lines and not local_lines[-1].endswith("\n"):
        local_lines[-1] += "\n"
    if backup_lines and not backup_lines[-1].endswith("\n"):
        backup_lines[-1] += "\n"

    diff = difflib.unified_diff(
        local_lines,
        backup_lines,
        fromfile=f"local/{local_path.name}",
        tofile=f"backup/{backup_path.name}",
        lineterm="",
        n=context_lines,
    )
    return "".join(diff)


def diff_shell_config(
    backup_dir: Path,
    shell: str,
) -> ComponentDiff:
    """Diff shell configuration between backup and local environment."""
    result = ComponentDiff(name=shell, status=DiffStatus.IDENTICAL)

    if shell == "fish":
        local_dir = config.home / ".config" / "fish"
        backup_tar = backup_dir / "shells" / "fish" / "fish_config.tar.gz"
        if not backup_tar.is_file():
            result.status = DiffStatus.MISSING_BACKUP
            return result
        if not local_dir.is_dir():
            result.status = DiffStatus.MISSING_LOCAL
            result.action = ChangeAction.OVERWRITE
            return result

        # For fish, we diff key files
        import tarfile
        try:
            with tarfile.open(backup_tar, "r:gz") as tar:
                members = {m.name: m for m in tar.getmembers() if m.isfile()}
                for name, member in members.items():
                    fname = name.split("/", 1)[-1] if "/" in name else name
                    local_file = local_dir / fname
                    backup_extracted = config.temp_dir / "diff_fish" / fname
                    backup_extracted.parent.mkdir(parents=True, exist_ok=True)
                    with tar.extractfile(member) as src, open(backup_extracted, "wb") as dst:
                        if src:
                            dst.write(src.read())

                    if not local_file.is_file():
                        result.files.append(FileDiff(
                            path=local_file,
                            status=DiffStatus.MISSING_LOCAL,
                            backup_path=backup_extracted,
                            action=ChangeAction.OVERWRITE,
                        ))
                        result.status = DiffStatus.MODIFIED
                    elif _file_checksum(local_file) != _file_checksum(backup_extracted):
                        result.files.append(FileDiff(
                            path=local_file,
                            status=DiffStatus.MODIFIED,
                            local_path=local_file,
                            backup_path=backup_extracted,
                            unified_diff=diff_text_files(local_file, backup_extracted),
                            action=ChangeAction.MERGE,
                        ))
                        result.status = DiffStatus.MODIFIED
        except Exception as e:
            log("WARN", f"Fish diff failed: {e}")
            result.status = DiffStatus.CONFLICT
            result.details = str(e)

    elif shell in ("bash", "zsh"):
        files_map = {
            "bash": [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"],
            "zsh": [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"],
        }
        backup_shell_dir = backup_dir / "shells" / shell
        if not backup_shell_dir.is_dir():
            result.status = DiffStatus.MISSING_BACKUP
            return result

        for fname in files_map.get(shell, []):
            local_file = config.home / fname
            backup_file = backup_shell_dir / fname

            if not backup_file.is_file():
                if local_file.is_file():
                    result.files.append(FileDiff(
                        path=local_file,
                        status=DiffStatus.MISSING_BACKUP,
                        local_path=local_file,
                        action=ChangeAction.SKIP,
                    ))
                continue

            if not local_file.is_file():
                result.files.append(FileDiff(
                    path=local_file,
                    status=DiffStatus.MISSING_LOCAL,
                    backup_path=backup_file,
                    action=ChangeAction.OVERWRITE,
                ))
                result.status = DiffStatus.MODIFIED
            elif _file_checksum(local_file) != _file_checksum(backup_file):
                result.files.append(FileDiff(
                    path=local_file,
                    status=DiffStatus.MODIFIED,
                    local_path=local_file,
                    backup_path=backup_file,
                    unified_diff=diff_text_files(local_file, backup_file),
                    action=ChangeAction.MERGE,
                ))
                result.status = DiffStatus.MODIFIED

    return result


def diff_packages(
    backup_dir: Path,
    pm: str,
) -> ComponentDiff:
    """Diff installed packages between backup and local environment."""
    result = ComponentDiff(name="packages", status=DiffStatus.IDENTICAL)

    pkg_dir = backup_dir / "packages"
    if not pkg_dir.is_dir():
        result.status = DiffStatus.MISSING_BACKUP
        return result

    # Read backup package list
    backup_pkg_file = pkg_dir / f"{pm}.txt"
    if not backup_pkg_file.is_file():
        result.status = DiffStatus.MISSING_BACKUP
        return result

    backup_packages = set()
    try:
        for line in backup_pkg_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract package name (format varies by PM)
                parts = line.split()
                if parts:
                    backup_packages.add(parts[0])
    except Exception as e:
        log("WARN", f"Failed to read backup package list: {e}")
        result.status = DiffStatus.CONFLICT
        result.details = str(e)
        return result

    # Get local package list
    local_packages = set()
    try:
        from shellpack.core import run_command
        if pm == "brew":
            rc, out, _ = run_command(["brew", "list"], capture=True, check=False)
            if rc == 0:
                local_packages = set(out.strip().splitlines())
        elif pm == "apt":
            rc, out, _ = run_command(["dpkg-query", "-W", "-f=${Package}\n"], capture=True, check=False)
            if rc == 0:
                local_packages = set(out.strip().splitlines())
        elif pm == "dnf":
            rc, out, _ = run_command(["dnf", "list", "installed", "--quiet"], capture=True, check=False)
            if rc == 0:
                for line in out.strip().splitlines():
                    parts = line.split(".")
                    if parts:
                        local_packages.add(parts[0])
        elif pm == "pacman":
            rc, out, _ = run_command(["pacman", "-Qq"], capture=True, check=False)
            if rc == 0:
                local_packages = set(out.strip().splitlines())
    except Exception as e:
        log("WARN", f"Failed to get local package list: {e}")
        result.status = DiffStatus.CONFLICT
        result.details = str(e)
        return result

    missing = sorted(backup_packages - local_packages)
    extra = sorted(local_packages - backup_packages)

    if missing:
        result.status = DiffStatus.MODIFIED
        result.details = f"{len(missing)} packages to install, {len(extra)} extra local packages"
        for pkg in missing:
            result.files.append(FileDiff(
                path=Path(pkg),
                status=DiffStatus.MISSING_LOCAL,
                action=ChangeAction.INSTALL,
            ))
    elif extra:
        result.status = DiffStatus.IDENTICAL
        result.details = f"{len(extra)} extra local packages (no action needed)"

    return result


def diff_config(
    backup_dir: Path,
    config_name: str,
) -> ComponentDiff:
    """Diff a specific config component (starship, git)."""
    result = ComponentDiff(name=config_name, status=DiffStatus.IDENTICAL)

    config_map = {
        "starship": (config.home / ".config" / "starship.toml", backup_dir / "config" / "starship.toml"),
        "git": (config.home / ".gitconfig", backup_dir / "config" / ".gitconfig"),
    }

    local_file, backup_file = config_map.get(config_name, (None, None))
    if not local_file or not backup_file:
        result.status = DiffStatus.CONFLICT
        result.details = f"Unknown config: {config_name}"
        return result

    if not backup_file.is_file():
        result.status = DiffStatus.MISSING_BACKUP
        return result

    if not local_file.is_file():
        result.files.append(FileDiff(
            path=local_file,
            status=DiffStatus.MISSING_LOCAL,
            backup_path=backup_file,
            action=ChangeAction.OVERWRITE,
        ))
        result.status = DiffStatus.MODIFIED
        result.action = ChangeAction.OVERWRITE
    elif _file_checksum(local_file) != _file_checksum(backup_file):
        result.files.append(FileDiff(
            path=local_file,
            status=DiffStatus.MODIFIED,
            local_path=local_file,
            backup_path=backup_file,
            unified_diff=diff_text_files(local_file, backup_file),
            action=ChangeAction.MERGE,
        ))
        result.status = DiffStatus.MODIFIED
        result.action = ChangeAction.MERGE

    return result


def full_diff(
    backup_dir: Path,
    pm: str,
    shells: List[str],
) -> List[ComponentDiff]:
    """Compute a full diff between local environment and backup.

    Returns a list of ComponentDiff objects for each component.
    """
    results: List[ComponentDiff] = []

    for shell in shells:
        results.append(diff_shell_config(backup_dir, shell))

    results.append(diff_packages(backup_dir, pm))

    for cfg in ("starship", "git"):
        results.append(diff_config(backup_dir, cfg))

    return results
