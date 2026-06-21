#!/usr/bin/env python3
import sys

from shellpack.core import (
    config, Colors, VERSION,
    print_banner,
)
from shellpack.backup import do_backup
from shellpack.restore import do_restore
from shellpack.sync import do_sync
from shellpack.snapshot import (
    create_snapshot, restore_from_snapshot, list_snapshots, prune_snapshots,
)


def show_help() -> None:
    print_banner()
    print(f"""
{Colors.BOLD}USAGE{Colors.NC}
    shellpack <command> [options]

{Colors.BOLD}COMMANDS{Colors.NC}
    backup              Backup shell environment to a Git repository
    restore             Restore shell environment from a Git repository
    sync                Sync shell environment with a backup (safe merge)
    snapshot            Create a local snapshot of current environment
    restore-snapshot    Restore from a local snapshot
    list-snapshots      List available local snapshots
    prune-snapshots     Remove old snapshots
    help, --help, -h    Show this help message
    version, --version  Show version information

{Colors.BOLD}OPTIONS{Colors.NC}
    --verbose, -v       Enable verbose output
    --dry-run           Show what would be done without making changes

{Colors.BOLD}EXAMPLES{Colors.NC}
    python3 shellpack.py backup
    python3 shellpack.py restore
    python3 shellpack.py sync
    python3 shellpack.py snapshot
    python3 shellpack.py restore-snapshot pre-sync-20260101-120000
    python3 shellpack.py --dry-run sync

{Colors.BOLD}WHAT GETS BACKED UP{Colors.NC}
    \u2022 Shell configs (Fish, Bash, Zsh, Oh-My-Zsh)
    \u2022 Package lists (apt, brew, dnf, pacman)
    \u2022 Conda/Miniconda environments
    \u2022 Starship prompt configuration
    \u2022 Git configuration
    \u2022 SSH keys (optional)
    \u2022 Cloud credentials (optional)
    \u2022 Shell history (optional)

{Colors.BOLD}SUPPORTED PLATFORMS{Colors.NC}
    \u2022 macOS (Intel & Apple Silicon)
    \u2022 Linux (Ubuntu, Debian, Fedora, Arch, etc.)
    \u2022 Windows (WSL/WSL2)

{Colors.BOLD}MORE INFO{Colors.NC}
    Version: {VERSION}
""")


def show_version() -> None:
    print(f"ShellPack v{VERSION}")


def _handle_snapshot_command(args: list) -> None:
    """Handle snapshot subcommands."""
    if not args:
        # Default: create snapshot
        snap = create_snapshot()
        if snap:
            print(f"Snapshot created: {snap}")
        else:
            print("Failed to create snapshot", file=sys.stderr)
            sys.exit(1)
        return

    subcmd = args[0]
    if subcmd in ("restore-snapshot", "restore"):
        if len(args) < 2:
            print("Usage: shellpack restore-snapshot <snapshot-name>", file=sys.stderr)
            sys.exit(1)
        name = args[1]
        from shellpack.snapshot import SNAPSHOT_DIR
        snap_path = SNAPSHOT_DIR / name
        if restore_from_snapshot(snap_path):
            print(f"Restored from snapshot: {name}")
        else:
            print("Restore failed", file=sys.stderr)
            sys.exit(1)
    elif subcmd in ("list-snapshots", "list"):
        snapshots = list_snapshots()
        if not snapshots:
            print("No snapshots found.")
            return
        print(f"{'Name':<40} {'Created':<25} {'Components'}")
        print("-" * 80)
        for s in snapshots:
            comps = ", ".join(s.get("components", [])[:5])
            print(f"{s['name']:<40} {s['created']:<25} {comps}")
    elif subcmd in ("prune-snapshots", "prune"):
        removed = prune_snapshots()
        print(f"Removed {removed} old snapshot(s)")
    else:
        print(f"Unknown snapshot command: {subcmd}", file=sys.stderr)
        sys.exit(1)


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    # Parse global flags
    i = 0
    while i < len(argv) and argv[i].startswith("-"):
        flag = argv[i]
        if flag in ("--verbose", "-v"):
            config.verbose = True
        elif flag == "--dry-run":
            config.dry_run = True
        elif flag in ("--help", "-h"):
            show_help()
            return
        elif flag == "--version":
            show_version()
            return
        else:
            print(f"Unknown option: {flag}", file=sys.stderr)
            sys.exit(1)
        i += 1

    args = argv[i:]

    if not args:
        show_help()
        return

    command = args[0]
    subargs = args[1:]

    if command == "backup":
        do_backup()
    elif command == "restore":
        do_restore()
    elif command == "sync":
        do_sync()
    elif command == "snapshot":
        _handle_snapshot_command(subargs)
    elif command in ("restore-snapshot", "list-snapshots", "prune-snapshots"):
        _handle_snapshot_command([command] + subargs)
    elif command in ("help", "--help", "-h"):
        show_help()
    elif command in ("version", "--version"):
        show_version()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        print("Run 'shellpack help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
