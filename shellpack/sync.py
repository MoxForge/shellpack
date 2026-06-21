#!/usr/bin/env python3
"""Sync orchestrator - safely update local shell from backup."""

import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any

from shellpack.core import (
    config, Colors, log, VERSION,
    print_banner, print_header, print_section, print_status, print_item,
    print_error, print_warning, print_success,
    read_input, read_yes_no, read_choice,
    run_command, command_exists,
    detect_os, detect_package_manager, detect_shell, get_hostname,
    check_dependencies, read_manifest,
    clone_repo, init_repo, push_to_repo, verify_ssh_connection,
    set_ssh_permissions, generate_ssh_key,
    copy_file, safe_extract_tar, calculate_checksum,
    rollback_stack, add_rollback_action, execute_rollback,
)
from shellpack.snapshot import (
    create_snapshot, restore_from_snapshot, list_snapshots, prune_snapshots,
)
from shellpack.diff import (
    full_diff, diff_shell_config, diff_config, diff_packages,
    DiffStatus, ChangeAction, ComponentDiff, FileDiff,
)
from shellpack.merge import merge_shell_config, merge_package_lists


COMPONENT_LABELS = {
    "fish": "Fish Shell",
    "bash": "Bash",
    "zsh": "Zsh",
    "oh-my-zsh": "Oh-My-Zsh",
    "packages": "Packages",
    "starship": "Starship Prompt",
    "git": "Git Config",
    "ssh": "SSH Keys",
    "conda": "Conda Environments",
    "history": "Shell History",
    "cloud": "Cloud Credentials",
}


def _print_diff_status(status: DiffStatus) -> str:
    """Return a colored status string for a diff status."""
    color_map = {
        DiffStatus.IDENTICAL: f"{Colors.GREEN}identical{Colors.NC}",
        DiffStatus.ADDED: f"{Colors.GREEN}added{Colors.NC}",
        DiffStatus.REMOVED: f"{Colors.RED}removed{Colors.NC}",
        DiffStatus.MODIFIED: f"{Colors.YELLOW}modified{Colors.NC}",
        DiffStatus.CONFLICT: f"{Colors.RED}CONFLICT{Colors.NC}",
        DiffStatus.MISSING_LOCAL: f"{Colors.YELLOW}missing locally{Colors.NC}",
        DiffStatus.MISSING_BACKUP: f"{Colors.GRAY}not in backup{Colors.NC}",
    }
    return color_map.get(status, str(status))


def _print_action_status(action: ChangeAction) -> str:
    """Return a colored action string."""
    color_map = {
        ChangeAction.NONE: f"{Colors.GRAY}none{Colors.NC}",
        ChangeAction.OVERWRITE: f"{Colors.YELLOW}overwrite{Colors.NC}",
        ChangeAction.MERGE: f"{Colors.CYAN}merge{Colors.NC}",
        ChangeAction.SKIP: f"{Colors.GRAY}skip{Colors.NC}",
        ChangeAction.INSTALL: f"{Colors.GREEN}install{Colors.NC}",
    }
    return color_map.get(action, str(action))


def _interactive_component_selection(diffs: List[ComponentDiff]) -> List[ComponentDiff]:
    """Let user select which components to sync and how.

    Returns a filtered/modified list of ComponentDiff with updated actions.
    """
    print_section("Component Selection")
    print()
    print(f"  {Colors.GRAY}Review each component and choose how to handle it:{Colors.NC}")
    print()

    for comp in diffs:
        label = COMPONENT_LABELS.get(comp.name, comp.name)
        status = _print_diff_status(comp.status)

        if comp.status == DiffStatus.IDENTICAL or comp.status == DiffStatus.MISSING_BACKUP:
            print(f"  [{Colors.GRAY}skip{Colors.NC}] {label}: {status}")
            comp.action = ChangeAction.SKIP
            continue

        if comp.status == DiffStatus.CONFLICT:
            print(f"  [{Colors.RED}CONFLICT{Colors.NC}] {label}: {comp.details}")
            comp.action = ChangeAction.SKIP
            continue

        # Show details
        print(f"  {Colors.BOLD}{label}{Colors.NC}: {status}")
        if comp.details:
            print(f"    {Colors.GRAY}{comp.details}{Colors.NC}")

        for fd in comp.files:
            action_str = _print_action_status(fd.action)
            print(f"    {Colors.GRAY}  {fd.path.name}: {action_str}{Colors.NC}")

        # Ask user
        if comp.name == "packages":
            choices = ["Install missing packages", "Skip packages"]
            default = 1 if comp.status == DiffStatus.MODIFIED else 2
        elif comp.name in ("ssh", "cloud"):
            choices = ["Skip (sensitive - never auto-sync)", "Overwrite"]
            default = 1
        else:
            choices = ["Merge (append new items)", "Overwrite", "Skip"]
            default = 1

        choice = read_choice(f"How to handle {label}?", choices, default)

        if comp.name == "packages":
            comp.action = ChangeAction.INSTALL if choice == 1 else ChangeAction.SKIP
        elif comp.name in ("ssh", "cloud"):
            comp.action = ChangeAction.OVERWRITE if choice == 2 else ChangeAction.SKIP
        else:
            if choice == 1:
                comp.action = ChangeAction.MERGE
            elif choice == 2:
                comp.action = ChangeAction.OVERWRITE
            else:
                comp.action = ChangeAction.SKIP

        # Update file-level actions to match component action
        if comp.action != ChangeAction.NONE:
            for fd in comp.files:
                if comp.action == ChangeAction.SKIP:
                    fd.action = ChangeAction.SKIP
                elif comp.action == ChangeAction.OVERWRITE:
                    if fd.status == DiffStatus.MISSING_LOCAL:
                        fd.action = ChangeAction.OVERWRITE
                # For MERGE, keep individual file actions

        print()

    return diffs


def _apply_component_sync(
    comp: ComponentDiff,
    backup_dir: Path,
    pm: str,
) -> bool:
    """Apply sync changes for a single component.

    Returns True on success.
    """
    if comp.action == ChangeAction.SKIP or comp.action == ChangeAction.NONE:
        return True

    try:
        if comp.name == "packages":
            if comp.action == ChangeAction.INSTALL:
                pkg_file = backup_dir / "packages" / f"{pm}.txt"
                success, msg = merge_package_lists(pkg_file, pm)
                print_status(f"Packages: {msg}", "ok" if success else "error")
                return success
            return True

        if comp.name == "starship":
            src = backup_dir / "config" / "starship.toml"
            dest = config.home / ".config" / "starship.toml"
            if src.is_file():
                if comp.action == ChangeAction.MERGE:
                    # Starship is single-file, merge just overwrites
                    copy_file(src, dest)
                else:
                    copy_file(src, dest)
                print_status("Starship config", "ok")
            return True

        if comp.name == "git":
            src = backup_dir / "config" / ".gitconfig"
            dest = config.home / ".gitconfig"
            if src.is_file():
                if comp.action == ChangeAction.MERGE:
                    success, msg = merge_shell_config(dest, src, "bash", dest)
                    print_status(f"Git config: {msg}", "ok" if success else "warn")
                else:
                    copy_file(src, dest)
                    print_status("Git config", "ok")
            return True

        if comp.name in ("bash", "zsh"):
            files_map = {
                "bash": [".bashrc", ".bash_aliases", ".bash_profile", ".profile", ".bash_logout"],
                "zsh": [".zshrc", ".zprofile", ".zshenv", ".zlogin", ".zlogout"],
            }
            backup_shell_dir = backup_dir / "shells" / comp.name
            for fname in files_map.get(comp.name, []):
                src = backup_shell_dir / fname
                dest = config.home / fname
                if not src.is_file():
                    continue

                if comp.action == ChangeAction.MERGE and dest.is_file():
                    success, msg = merge_shell_config(dest, src, comp.name, dest)
                    if success:
                        print_status(f"  {fname}: {msg}", "ok")
                    else:
                        print_status(f"  {fname}: {msg}", "warn")
                else:
                    copy_file(src, dest)
                    print_status(f"  {fname}", "ok")
            return True

        if comp.name == "fish":
            archive = backup_dir / "shells" / "fish" / "fish_config.tar.gz"
            if archive.is_file():
                dest = config.home / ".config"
                dest.mkdir(parents=True, exist_ok=True)

                if comp.action == ChangeAction.MERGE and (dest / "fish").is_dir():
                    # For fish merge, we extract to temp and merge key files
                    temp_fish = config.temp_dir / "sync_fish"
                    temp_fish.mkdir(parents=True, exist_ok=True)
                    safe_extract_tar(archive, temp_fish)
                    extracted = temp_fish / "fish"
                    if extracted.is_dir():
                        for f in extracted.rglob("*.fish"):
                            rel = f.relative_to(extracted)
                            local_file = dest / "fish" / rel
                            if local_file.is_file():
                                success, msg = merge_shell_config(local_file, f, "fish", local_file)
                                if success:
                                    print_status(f"  {rel}: {msg}", "ok")
                            else:
                                copy_file(f, local_file)
                                print_status(f"  {rel}", "ok")
                        # Copy non-.fish files
                        for f in extracted.rglob("*"):
                            if f.is_file() and f.suffix != ".fish":
                                rel = f.relative_to(extracted)
                                dest_file = dest / "fish" / rel
                                if not dest_file.is_file():
                                    copy_file(f, dest_file)
                else:
                    safe_extract_tar(archive, dest)
                    print_status("Fish config", "ok")
            return True

        if comp.name == "oh-my-zsh":
            archive = backup_dir / "shells" / "oh-my-zsh" / "ohmyzsh_backup.tar.gz"
            if archive.is_file():
                if comp.action == ChangeAction.MERGE and (config.home / ".oh-my-zsh").is_dir():
                    # Merge custom themes and plugins
                    temp_omz = config.temp_dir / "sync_omz"
                    temp_omz.mkdir(parents=True, exist_ok=True)
                    safe_extract_tar(archive, temp_omz)
                    extracted = temp_omz / ".oh-my-zsh"
                    if extracted.is_dir():
                        for subdir in ("custom/themes", "custom/plugins"):
                            src_dir = extracted / subdir
                            if src_dir.is_dir():
                                dest_dir = config.home / ".oh-my-zsh" / subdir
                                for f in src_dir.iterdir():
                                    if f.is_file():
                                        copy_file(f, dest_dir / f.name)
                                        print_status(f"  {subdir}/{f.name}", "ok")
                else:
                    safe_extract_tar(archive, config.home)
                    print_status("Oh-My-Zsh", "ok")
            return True

        if comp.name == "ssh":
            archive = backup_dir / "ssh" / "ssh_backup.tar.gz"
            if archive.is_file():
                safe_extract_tar(archive, config.home)
                set_ssh_permissions()
                print_status("SSH keys", "ok")
            return True

        if comp.name == "history":
            hist_dir = backup_dir / "history"
            if hist_dir.is_dir():
                for name in [".bash_history", ".zsh_history"]:
                    src = hist_dir / name
                    dest = config.home / name
                    if src.is_file():
                        if dest.is_file():
                            # Merge history: append unique lines
                            local_lines = set(dest.read_text().splitlines())
                            backup_lines = src.read_text().splitlines()
                            new_lines = [l for l in backup_lines if l not in local_lines]
                            if new_lines:
                                with open(dest, "a") as f:
                                    f.write("\n".join(new_lines) + "\n")
                                print_status(f"  {name}: appended {len(new_lines)} entries", "ok")
                        else:
                            copy_file(src, dest)
                            print_status(f"  {name}", "ok")

                fish_src = hist_dir / "fish"
                if fish_src.is_dir():
                    fish_dest = config.home / ".local" / "share" / "fish"
                    fish_dest.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(str(fish_src), str(fish_dest), dirs_exist_ok=True)
                    print_status("  Fish history", "ok")
            return True

        if comp.name == "cloud":
            cloud_dir = backup_dir / "cloud"
            if cloud_dir.is_dir():
                for name, extract_to in [
                    ("aws", config.home),
                    ("azure", config.home),
                    ("gcloud", config.home / ".config"),
                ]:
                    tar_path = cloud_dir / f"{name}.tar.gz"
                    if tar_path.is_file():
                        extract_to.mkdir(parents=True, exist_ok=True)
                        safe_extract_tar(tar_path, extract_to)
                        print_status(f"  {name}", "ok")
            return True

        return True

    except Exception as e:
        log("ERROR", f"Sync failed for {comp.name}: {e}")
        print_error(f"Failed to sync {comp.name}: {e}")
        return False


def do_sync() -> None:
    """Main sync orchestrator.

    1. Create pre-sync snapshot
    2. Clone/pull backup repo
    3. Compute diff
    4. Interactive component selection
    5. Apply changes with rollback support
    6. Post-sync report
    """
    print_banner()
    print_header("Sync Shell Environment")

    if not check_dependencies():
        raise SystemExit(1)

    os_name, arch = detect_os()
    pm = detect_package_manager(os_name)

    print()
    print_status(f"Operating System: {os_name}", "info")
    print_status(f"Architecture: {arch}", "info")
    print_status(f"Package Manager: {pm}", "info")
    print_status(f"Current Shell: {detect_shell()}", "info")

    # Ask for backup repo
    print_section("Backup Repository")
    print()
    print(f"  {Colors.GRAY}Enter the URL of your backup Git repository:{Colors.NC}")
    print(f"  {Colors.GRAY}Example: git@github.com:username/shell-backups.git{Colors.NC}")
    print()

    while True:
        repo_url = read_input("Repository URL")
        if not repo_url:
            print_error("Repository URL is required")
            continue
        from shellpack.core import validate_git_url
        if not validate_git_url(repo_url):
            print_error("Invalid Git URL format")
            continue
        break

    # Clone repo
    work_dir = config.temp_dir / "sync"
    work_dir.mkdir(parents=True, exist_ok=True)

    print()
    print_status("Cloning repository...", "info")

    repo_dir = work_dir / "repo"
    if repo_dir.is_dir():
        shutil.rmtree(repo_dir)

    if not clone_repo(repo_url, repo_dir):
        print_error("Failed to clone repository")
        raise SystemExit(1)

    # List available backups
    backups_dir = repo_dir / "backups"
    if not backups_dir.is_dir():
        print_error("No backups directory found in repository")
        raise SystemExit(1)

    backups = sorted(
        [d for d in backups_dir.iterdir() if d.is_dir()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not backups:
        print_error("No backups found in repository")
        raise SystemExit(1)

    print_section("Available Backups")
    print()
    print(f"  {Colors.GRAY}Choose a backup to sync from:{Colors.NC}")
    print()

    backup_names = []
    for b in backups:
        manifest_path = b / config.manifest_file
        if manifest_path.is_file():
            manifest = read_manifest(manifest_path)
            if manifest:
                src = manifest.get("source", {})
                hostname = src.get("hostname", "unknown")
                shell = src.get("default_shell", "unknown")
                created = manifest.get("created", "unknown")
                backup_names.append(f"{b.name} [{hostname}] ({shell}) - {created}")
            else:
                backup_names.append(b.name)
        else:
            backup_names.append(b.name)

    choice = read_choice("Select backup", backup_names, 1)
    backup_dir = backups[choice - 1]

    print()
    print_status(f"Selected backup: {backup_dir.name}", "info")

    # Read and verify manifest
    manifest = read_manifest(backup_dir / config.manifest_file)
    if manifest:
        print(f"  {Colors.GRAY}Source: {manifest.get('source', {}).get('hostname', 'unknown')}{Colors.NC}")
        print(f"  {Colors.GRAY}Created: {manifest.get('created', 'unknown')}{Colors.NC}")
        print(f"  {Colors.GRAY}Backup type: {manifest.get('backup_type', 'unknown')}{Colors.NC}")

        # Verify checksum
        print()
        print(f"  {Colors.GRAY}Verifying backup integrity...{Colors.NC}")
        expected = manifest.get("checksum", "")
        if expected:
            actual = calculate_checksum(backup_dir)
            if actual != expected:
                print_error("Backup integrity check FAILED!")
                print(f"  {Colors.RED}Expected: {expected[:16]}...{Colors.NC}")
                print(f"  {Colors.RED}Actual:   {actual[:16]}...{Colors.NC}")
                print()
                if not read_yes_no("Continue anyway?", False):
                    raise SystemExit(1)
            else:
                print_status("Backup integrity verified", "ok")
        else:
            print_warning("No checksum in manifest - cannot verify integrity")

    # Create pre-sync snapshot
    print()
    print_section("Pre-Sync Snapshot")
    print()
    print(f"  {Colors.GRAY}Creating snapshot of current environment for safety...{Colors.NC}")
    print()

    snapshot = create_snapshot(
        name=f"pre-sync-{backup_dir.name}",
        include_shells=True,
        include_packages=True,
        include_config=True,
        include_ssh=False,
        include_conda=False,
        include_history=True,
        include_cloud=False,
    )

    if snapshot:
        print_status(f"Snapshot created: {snapshot.name}", "ok")
        print(f"  {Colors.GRAY}Location: {snapshot}{Colors.NC}")
        print(f"  {Colors.GRAY}Run 'shellpack restore-snapshot {snapshot.name}' to revert{Colors.NC}")
    else:
        print_warning("Failed to create pre-sync snapshot")
        if not read_yes_no("Continue without snapshot?", False):
            raise SystemExit(1)

    # Compute diff
    print()
    print_section("Comparing with Backup")
    print()

    shells = manifest.get("shells", ["bash", "zsh", "fish"]) if manifest else ["bash", "zsh", "fish"]
    diffs = full_diff(backup_dir, pm, shells)

    # Show summary
    for comp in diffs:
        label = COMPONENT_LABELS.get(comp.name, comp.name)
        status = _print_diff_status(comp.status)
        print(f"  {label}: {status}")

    # Check if anything needs sync
    actionable = [c for c in diffs if c.status not in (
        DiffStatus.IDENTICAL, DiffStatus.MISSING_BACKUP, DiffStatus.CONFLICT
    )]

    if not actionable:
        print()
        print_status("Everything is up to date! Nothing to sync.", "ok")
        return

    # Dry run option
    if config.dry_run:
        print()
        print_status("DRY RUN - no changes made", "info")
        return

    # Interactive component selection
    diffs = _interactive_component_selection(diffs)

    # Final confirmation
    to_apply = [c for c in diffs if c.action not in (ChangeAction.NONE, ChangeAction.SKIP)]
    if not to_apply:
        print()
        print_status("No components selected for sync. Exiting.", "info")
        return

    print()
    print_section("Sync Summary")
    print()
    for comp in to_apply:
        label = COMPONENT_LABELS.get(comp.name, comp.name)
        action = _print_action_status(comp.action)
        print(f"  {label}: {action}")

    print()
    if not read_yes_no("Apply these changes?", False):
        print()
        print_status("Sync cancelled. Your environment is unchanged.", "info")
        return

    # Apply changes
    print()
    print_section("Applying Changes")
    print()

    failed_components: List[str] = []
    success_count = 0

    for comp in to_apply:
        label = COMPONENT_LABELS.get(comp.name, comp.name)
        print(f"  {Colors.BOLD}{label}{Colors.NC}...")

        if _apply_component_sync(comp, backup_dir, pm):
            success_count += 1
        else:
            failed_components.append(label)

    # Post-sync report
    print()
    print_header("Sync Report")
    print()

    total = len(to_apply)
    print(f"  Components: {success_count}/{total} successful")

    if failed_components:
        print()
        print(f"  {Colors.RED}Failed components:{Colors.NC}")
        for name in failed_components:
            print(f"    {Colors.RED}- {name}{Colors.NC}")

    if snapshot:
        print()
        print(f"  {Colors.GRAY}Pre-sync snapshot: {snapshot.name}{Colors.NC}")
        print(f"  {Colors.GRAY}To revert: shellpack restore-snapshot {snapshot.name}{Colors.NC}")

    # Prune old snapshots
    pruned = prune_snapshots()
    if pruned > 0:
        print(f"  {Colors.GRAY}Pruned {pruned} old snapshot(s){Colors.NC}")

    print()
    if not failed_components:
        print_success("Sync completed successfully!")
    else:
        print_warning("Sync completed with some failures.")

    print()
