#!/usr/bin/env python3
import sys

from shellpack.core import (
    config, Colors, VERSION,
    print_banner,
)
from shellpack.backup import do_backup
from shellpack.restore import do_restore


def show_help() -> None:
    print_banner()
    print(f"""
{Colors.BOLD}USAGE{Colors.NC}
    shellpack <command> [options]

{Colors.BOLD}COMMANDS{Colors.NC}
    backup              Backup shell environment to a Git repository
    restore             Restore shell environment from a Git repository
    help, --help, -h    Show this help message
    version, --version  Show version information

{Colors.BOLD}OPTIONS{Colors.NC}
    --verbose, -v       Enable verbose output
    --dry-run           Show what would be done without making changes

{Colors.BOLD}EXAMPLES{Colors.NC}
    python3 shellpack.py backup
    python3 shellpack.py restore
    python3 shellpack.py --dry-run backup

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
    print(f"shellpack version {VERSION}")


def main(argv=None) -> None:
    if argv is None:
        argv = sys.argv[1:]

    args = list(argv)

    while args:
        arg = args[0]
        if arg in ("--verbose", "-v"):
            config.verbose = True
            args.pop(0)
        elif arg == "--dry-run":
            config.dry_run = True
            args.pop(0)
        elif arg in ("--help", "-h", "help"):
            show_help()
            return
        elif arg in ("--version", "version"):
            show_version()
            return
        elif arg == "backup":
            args.pop(0)
            do_backup()
            return
        elif arg == "restore":
            args.pop(0)
            do_restore()
            return
        else:
            from shellpack.core import print_error
            print_error(f"Unknown command: {arg}")
            print()
            print(f"Run 'shellpack --help' for usage.")
            raise SystemExit(1)

    show_help()


if __name__ == "__main__":
    main()
