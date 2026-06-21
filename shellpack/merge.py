#!/usr/bin/env python3
"""Merge engine for intelligently combining shell configurations."""

import re
from pathlib import Path
from typing import List, Set, Tuple, Optional

from shellpack.core import config, log, copy_file


def _read_lines(path: Path) -> List[str]:
    """Read a file as a list of lines."""
    try:
        text = path.read_text(encoding="utf-8")
        return text.splitlines()
    except Exception as e:
        log("WARN", f"Failed to read {path}: {e}")
        return []


def _write_lines(path: Path, lines: List[str]) -> bool:
    """Write lines to a file."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return True
    except Exception as e:
        log("ERROR", f"Failed to write {path}: {e}")
        return False


def _extract_aliases(lines: List[str]) -> Set[str]:
    """Extract alias definitions from shell config lines."""
    aliases = set()
    for line in lines:
        line = line.strip()
        if line.startswith("alias ") and "=" in line:
            # alias ll='ls -la' -> ll
            name = line[6:].split("=")[0].strip()
            aliases.add(name)
    return aliases


def _extract_exports(lines: List[str]) -> Set[str]:
    """Extract export variable names from shell config lines."""
    exports = set()
    for line in lines:
        line = line.strip()
        if line.startswith("export ") and "=" in line:
            # export PATH="..." -> PATH
            name = line[7:].split("=")[0].strip()
            exports.add(name)
    return exports


def _extract_functions(lines: List[str]) -> Set[str]:
    """Extract function names from shell config lines."""
    funcs = set()
    for line in lines:
        line = line.strip()
        # bash/zsh: function_name() { or function function_name {
        m = re.match(r"^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", line)
        if m:
            funcs.add(m.group(1))
    return funcs


def _extract_fish_functions(lines: List[str]) -> Set[str]:
    """Extract function names from fish config lines."""
    funcs = set()
    for line in lines:
        line = line.strip()
        if line.startswith("function "):
            parts = line.split()
            if len(parts) >= 2:
                funcs.add(parts[1].strip(";"))
    return funcs


def _extract_fish_abbrs(lines: List[str]) -> Set[str]:
    """Extract abbreviation names from fish config lines."""
    abbrs = set()
    for line in lines:
        line = line.strip()
        if line.startswith("abbr "):
            # abbr -a ll 'ls -la' -> ll
            m = re.search(r"\s-a\s+([a-zA-Z0-9_]+)", line)
            if m:
                abbrs.add(m.group(1))
    return abbrs


def merge_shell_config(
    local_path: Path,
    backup_path: Path,
    shell: str,
    output_path: Optional[Path] = None,
) -> Tuple[bool, str]:
    """Intelligently merge a shell config file from backup into local.

    Strategy:
    - For bash/zsh: append new aliases, exports, and functions from backup
      that don't already exist in local. Don't overwrite existing definitions.
    - For fish: append new functions, abbreviations, and set statements.
    - For simple rc files: append a marked section at the end.

    Returns (success, message).
    """
    if not backup_path.is_file():
        return False, "Backup file not found"

    if not local_path.is_file():
        # Local doesn't exist - just copy backup
        copy_file(backup_path, output_path or local_path)
        return True, "Copied (local did not exist)"

    local_lines = _read_lines(local_path)
    backup_lines = _read_lines(backup_path)

    if shell in ("bash", "zsh"):
        return _merge_bash_zsh(local_lines, backup_lines, local_path, backup_path, output_path)
    elif shell == "fish":
        return _merge_fish(local_lines, backup_lines, local_path, backup_path, output_path)
    else:
        return _merge_generic(local_lines, backup_lines, local_path, backup_path, output_path)


def _merge_bash_zsh(
    local_lines: List[str],
    backup_lines: List[str],
    local_path: Path,
    backup_path: Path,
    output_path: Optional[Path],
) -> Tuple[bool, str]:
    """Merge bash/zsh config by appending new definitions."""
    local_aliases = _extract_aliases(local_lines)
    local_exports = _extract_exports(local_lines)
    local_funcs = _extract_functions(local_lines)

    new_lines: List[str] = []
    new_aliases = 0
    new_exports = 0
    new_funcs = 0

    for line in backup_lines:
        stripped = line.strip()

        if stripped.startswith("alias ") and "=" in stripped:
            name = stripped[6:].split("=")[0].strip()
            if name not in local_aliases:
                new_lines.append(line)
                new_aliases += 1

        elif stripped.startswith("export ") and "=" in stripped:
            name = stripped[7:].split("=")[0].strip()
            if name not in local_exports:
                new_lines.append(line)
                new_exports += 1

        elif re.match(r"^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stripped):
            m = re.match(r"^(?:function\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", stripped)
            if m and m.group(1) not in local_funcs:
                new_lines.append(line)
                new_funcs += 1

    if not new_lines:
        return True, "No new definitions to merge"

    out_path = output_path or local_path
    merged = local_lines.copy()

    # Add a marker comment
    merged.append("")
    merged.append("# --- Added by ShellPack sync ---")
    merged.extend(new_lines)
    merged.append("# --- End ShellPack sync ---")

    if _write_lines(out_path, merged):
        stats = []
        if new_aliases:
            stats.append(f"{new_aliases} alias(es)")
        if new_exports:
            stats.append(f"{new_exports} export(s)")
        if new_funcs:
            stats.append(f"{new_funcs} function(s)")
        return True, f"Merged: {', '.join(stats)}"
    return False, "Failed to write merged file"


def _merge_fish(
    local_lines: List[str],
    backup_lines: List[str],
    local_path: Path,
    backup_path: Path,
    output_path: Optional[Path],
) -> Tuple[bool, str]:
    """Merge fish config by appending new functions, abbrs, and set statements."""
    local_funcs = _extract_fish_functions(local_lines)
    local_abbrs = _extract_fish_abbrs(local_lines)

    # Extract set variables (fish uses 'set -x VAR value')
    local_sets: Set[str] = set()
    for line in local_lines:
        stripped = line.strip()
        if stripped.startswith("set "):
            parts = stripped.split()
            if len(parts) >= 3:
                # Skip flags like -x, -g, -U
                var_name = None
                for part in parts[1:]:
                    if not part.startswith("-"):
                        var_name = part
                        break
                if var_name:
                    local_sets.add(var_name)

    new_lines: List[str] = []
    new_funcs = 0
    new_abbrs = 0
    new_sets = 0

    for line in backup_lines:
        stripped = line.strip()

        if stripped.startswith("function "):
            parts = stripped.split()
            if len(parts) >= 2:
                name = parts[1].strip(";")
                if name not in local_funcs:
                    new_lines.append(line)
                    new_funcs += 1

        elif stripped.startswith("abbr "):
            m = re.search(r"\s-a\s+([a-zA-Z0-9_]+)", stripped)
            if m and m.group(1) not in local_abbrs:
                new_lines.append(line)
                new_abbrs += 1

        elif stripped.startswith("set "):
            parts = stripped.split()
            var_name = None
            for part in parts[1:]:
                if not part.startswith("-"):
                    var_name = part
                    break
            if var_name and var_name not in local_sets:
                new_lines.append(line)
                new_sets += 1

    if not new_lines:
        return True, "No new fish definitions to merge"

    out_path = output_path or local_path
    merged = local_lines.copy()
    merged.append("")
    merged.append("# --- Added by ShellPack sync ---")
    merged.extend(new_lines)
    merged.append("# --- End ShellPack sync ---")

    if _write_lines(out_path, merged):
        stats = []
        if new_funcs:
            stats.append(f"{new_funcs} function(s)")
        if new_abbrs:
            stats.append(f"{new_abbrs} abbr(s)")
        if new_sets:
            stats.append(f"{new_sets} variable(s)")
        return True, f"Merged: {', '.join(stats)}"
    return False, "Failed to write merged file"


def _merge_generic(
    local_lines: List[str],
    backup_lines: List[str],
    local_path: Path,
    backup_path: Path,
    output_path: Optional[Path],
) -> Tuple[bool, str]:
    """Generic merge: append unique lines from backup that don't exist in local."""
    local_set = set(line.strip() for line in local_lines if line.strip())

    new_lines = []
    for line in backup_lines:
        stripped = line.strip()
        if stripped and stripped not in local_set:
            new_lines.append(line)

    if not new_lines:
        return True, "No new content to merge"

    out_path = output_path or local_path
    merged = local_lines.copy()
    merged.append("")
    merged.append("# --- Added by ShellPack sync ---")
    merged.extend(new_lines)
    merged.append("# --- End ShellPack sync ---")

    if _write_lines(out_path, merged):
        return True, f"Merged: {len(new_lines)} new line(s)"
    return False, "Failed to write merged file"


def merge_package_lists(
    backup_pkg_file: Path,
    pm: str,
) -> Tuple[bool, str]:
    """Install packages from backup that are not already installed locally.

    Returns (success, message).
    """
    if not backup_pkg_file.is_file():
        return False, "Backup package list not found"

    try:
        backup_packages = set()
        for line in backup_pkg_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                parts = line.split()
                if parts:
                    backup_packages.add(parts[0])
    except Exception as e:
        return False, f"Failed to read backup package list: {e}"

    # Get local packages
    local_packages = set()
    from shellpack.core import run_command

    if pm == "brew":
        rc, out, _ = run_command(["brew", "list"], capture=True, check=False)
        if rc == 0:
            local_packages = set(out.strip().splitlines())
    elif pm == "apt":
        rc, out, _ = run_command(["dpkg-query", "-W", "-f=${Package}\\n"], capture=True, check=False)
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
    else:
        return False, f"Unsupported package manager: {pm}"

    to_install = sorted(backup_packages - local_packages)
    if not to_install:
        return True, "All packages already installed"

    # Install packages
    installed = 0
    failed = 0
    for pkg in to_install:
        if pm == "brew":
            rc, _, _ = run_command(["brew", "install", pkg], check=False, timeout=120)
        elif pm == "apt":
            rc, _, _ = run_command(["sudo", "apt-get", "install", "-y", pkg], check=False, timeout=120)
        elif pm == "dnf":
            rc, _, _ = run_command(["sudo", "dnf", "install", "-y", pkg], check=False, timeout=120)
        elif pm == "pacman":
            rc, _, _ = run_command(["sudo", "pacman", "-S", "--noconfirm", pkg], check=False, timeout=120)
        else:
            continue

        if rc == 0:
            installed += 1
        else:
            failed += 1

    msg = f"Installed: {installed}"
    if failed:
        msg += f", Failed: {failed}"
    return failed == 0, msg
