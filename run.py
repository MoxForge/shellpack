#!/usr/bin/env python3
"""
ShellPack - One-liner launcher for curl execution.

Usage:
    python3 <(curl -sL https://raw.githubusercontent.com/.../run.py) backup
    python3 <(curl -sL https://raw.githubusercontent.com/.../run.py) restore
"""
import sys
import subprocess
import tempfile
from pathlib import Path

REPO_URL = "https://raw.githubusercontent.com/MoxForge/shellpack/main"
REQUIRED_FILES = [
    "shellpack/__init__.py",
    "shellpack/core.py",
    "shellpack/backup.py",
    "shellpack/restore.py",
    "shellpack/cli.py",
]


def download_file(url: str, dest: Path) -> bool:
    try:
        result = subprocess.run(
            ["curl", "-sL", url, "-o", str(dest)],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0 and dest.stat().st_size > 0
    except Exception:
        return False


def main():
    work_dir = Path(tempfile.mkdtemp(prefix="shellpack-"))
    pkg_dir = work_dir / "shellpack"
    pkg_dir.mkdir(parents=True, exist_ok=True)

    print("Downloading ShellPack...")
    for rel_path in REQUIRED_FILES:
        url = f"{REPO_URL}/{rel_path}"
        dest = work_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not download_file(url, dest):
            print(f"Failed to download: {rel_path}")
            sys.exit(1)

    sys.path.insert(0, str(work_dir))
    from shellpack.cli import main as cli_main
    cli_main(sys.argv[1:])


if __name__ == "__main__":
    main()
