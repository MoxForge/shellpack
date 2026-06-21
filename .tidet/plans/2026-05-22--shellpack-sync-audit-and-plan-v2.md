---
schema_version: 1
slug: 2026-05-22--shellpack-sync-audit-and-plan-v2
title: ShellPack Security Audit & Sync Feature Plan — Revision 2
status: approved
created_at: 2026-06-21T12:28:07.313688Z
decided_at: 2026-06-21T12:28:24.864502Z
run_id: 0611d885-9522-4e38-b6be-6b3731aca3d6
---

# ShellPack Security Audit & Sync Feature Plan — Revision 2

## Executive Summary

This is a **critical revision** after a second-pass deep audit with maximum scrutiny. The original audit identified 2 critical and 2 high-severity issues. **This revision adds 2 additional critical bugs and 3 additional high-severity issues** found in core path-handling, repository initialization, and directory-destruction logic. **These bugs can destroy user data or corrupt the user's current working directory right now.** They must be fixed before any sync feature is implemented.

**Status:** 4 Critical, 5 High, 5 Medium, 4 Low issues identified.

---

## Part 1: Security & Correctness Audit Findings

### Critical — Fix Immediately (Data Loss / Corruption Risk)

#### C1: Path Traversal via Tarfile Extraction
**Location:** `restore_fish()`, `restore_zsh()`, `restore_ssh()`, `restore_cloud_creds()`
**Issue:** `tarfile.extractall(path=...)` has zero member validation. Malicious tarballs with members like `../../../.ssh/authorized_keys` write outside the target directory.
**Impact:** Arbitrary file overwrite anywhere the user has write permission.
**Fix:** Validate every member's resolved path is within the destination before extraction.

#### C2: Rollback Executes Arbitrary Shell Commands
**Location:** `execute_rollback()` in `core.py`
**Issue:** Rollback actions are stored as raw strings and executed with `subprocess.run(action, shell=True)`. If any action string is constructed from user input (backup names, paths), this is command injection.
**Impact:** Arbitrary code execution during error recovery.
**Fix:** Store rollbacks as `(callable, args, kwargs)` tuples, execute without `shell=True`.

#### C3: `init_repo()` Initializes Wrong Directory — Completely Broken
**Location:** `init_repo()` in `core.py`, line 371
**Issue:** `git init` is run **without `-C dest_dir`**:
```python
def init_repo(dest_dir: Path, repo_url: str) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    rc, _, _ = run_command(["git", "init"], capture=True, check=False)  # BUG: no -C!
    if rc != 0:
        return False
    run_command(["git", "-C", str(dest_dir), "remote", "add", "origin", repo_url], check=False)
    return True
```
This initializes the **current working directory** as a git repo, not `dest_dir`. Then it adds a remote to `dest_dir` which was never initialized. If run from inside an existing git repo, it **reinitializes that repo and destroys its hooks/config**.
**Impact:** Corrupts whatever directory the user happens to be in when running ShellPack.
**Fix:** Change to `run_command(["git", "init", str(dest_dir)], capture=True, check=False)`.

#### C4: `copy_directory()` Destroys Destination Before Verifying Source
**Location:** `copy_directory()` in `core.py`, line 581
**Issue:**
```python
def copy_directory(src: Path, dest: Path) -> bool:
    try:
        if dest.exists():
            shutil.rmtree(dest)      # ← DESTROYS dest
        shutil.copytree(src, dest)   # ← Could fail; dest is already gone
        return True
```
If `src` is empty, unreadable, or the copytree fails mid-way, the user's original `dest` directory is **permanently deleted** with no recovery path.
**Impact:** Data loss. Used in `restore_cloud_creds()` and `restore_history()`.
**Fix:** Copy to a temp directory first, then atomic rename. Or use `shutil.copytree(src, dest, dirs_exist_ok=True)` without the destructive rmtree.

### High — Fix Before Sync Feature

#### H1: SSH Passphrase Visible in Process List
**Location:** `generate_ssh_key()` in `core.py`, line 461
**Issue:** Passphrase passed directly on command line: `ssh-keygen -N <passphrase>`.
**Impact:** Any user running `ps` can see the passphrase.
**Fix:** Remove passphrase parameter; generate keys without passphrase. Document that users should run `ssh-keygen -p` afterward to add one interactively.

#### H2: PowerShell Command Injection
**Location:** `shellpack.ps1` — user creation, SSH copy, restore blocks
**Issue:** Username, password, and WSL name are directly interpolated into bash command strings:
```powershell
wsl -d $wslName -- bash -c "useradd -m -s /bin/bash -G sudo '$username'"
```
A username like `'; rm -rf /; '` injects arbitrary commands.
**Impact:** Arbitrary command execution inside WSL.
**Fix:** Validate username against `^[a-z_][a-z0-9_-]*$`. Pass arguments via `bash -c '...' -- "$arg1"` or use WSL `--` separator.

#### H3: `set_default_shell()` Tee Command Is No-Op
**Location:** `set_default_shell()` in `restore.py`, line 327
**Issue:**
```python
run_command(["sudo", "tee", "-a", "/etc/shells"], check=False)
```
`tee` reads from stdin, but no stdin is provided. The shell path is **never added** to `/etc/shells`.
**Impact:** `chsh -s <shell>` fails because the shell isn't in `/etc/shells`. User thinks it worked because the function prints "ok" on success but doesn't verify `/etc/shells` actually changed.
**Fix:**
```python
run_command(["sh", "-c", f"echo {shlex.quote(shell_path)} | sudo tee -a /etc/shells > /dev/null"])
```

#### H4: `restore_conda()` Blindly Overwrites / Fails on Existing Envs
**Location:** `restore_conda()` in `restore.py`, line 203
**Issue:** Runs `conda env create -f <yml> -n <name>` without checking if the environment already exists. `conda env create` **fails** if the env exists. There is no `--force` or update logic.
**Impact:** Partial restore failure; user gets error spam. Existing environments with local modifications are neither preserved nor updated.
**Fix:** Check `conda env list` first. If env exists, skip or offer to `conda env update`.

#### H5: No Checksum Verification During Restore
**Location:** `do_restore()` in `restore.py`
**Issue:** `calculate_checksum()` computes SHA-256 during backup and stores it in the manifest. `do_restore()` reads the manifest but **never recomputes and compares** the checksum of the cloned/extracted files.
**Impact:** A corrupted or tampered backup is silently accepted.
**Fix:** After cloning, compute `calculate_checksum(backup_dir)` and compare to `manifest["checksum"]`. Fail on mismatch with a clear error.

### Medium

#### M1: Permissive Git URL Validation
**Location:** `validate_git_url()` in `core.py`
**Issue:** Patterns allow `file:///etc/passwd`, `javascript:alert(1)` because `[a-zA-Z0-9._-]+` doesn't restrict schemes properly and the first pattern allows any URL ending in `.git`.
**Fix:** Explicitly whitelist schemes: only `https://`, `http://`, `git://`, `ssh://`, and `git@` patterns. Reject `file://`, `javascript:`, `data:` explicitly.

#### M2: `clone_repo()` Fails Silently on Existing Directory
**Location:** `clone_repo()` in `core.py`
**Issue:** If `dest_dir` already exists and is non-empty, `git clone` fails. No cleanup or retry logic.
**Impact:** User gets "Clone failed" with no actionable guidance.
**Fix:** If dest exists, either remove it (with user confirmation) or use `git clone --force`, or pick a different temp dir.

#### M3: `run.py` Downloads Code Without Verification
**Location:** `run.py`
**Issue:** Downloads Python modules from raw GitHub and executes them without checksum verification.
**Impact:** If the GitHub repo is compromised or there's a MITM attack, arbitrary Python code runs on the user's machine.
**Fix:** This is fundamental to the one-liner design. Document the risk. For local installs, verify checksums or use pinned releases.

#### M4: `install_starship()` Pipes Curl to Sh
**Location:** `install_starship()` in `restore.py`
**Issue:** `curl -sS https://starship.rs/install.sh | sh -s -- -y` — unverified remote execution.
**Impact:** If starship.rs is compromised, arbitrary code execution.
**Fix:** Add warning in UI. For sync feature, make starship installation optional and explicit.

#### M5: `restore_ssh()` Extracts to `$HOME` Without Path Validation
**Location:** `restore_ssh()` in `restore.py`, line 157
**Issue:** Extracts tarball directly to `config.home`. Same tarfile path-traversal risk as C1, but to the most sensitive directory.
**Impact:** Overwrite of `.ssh/authorized_keys`, `.bashrc`, etc.
**Fix:** Use the same safe extraction helper as C1.

### Low

#### L1: `copy_file()` Doesn't Verify Write Success
**Location:** `copy_file()` in `core.py`
**Issue:** `shutil.copy2()` can fail in edge cases (disk full, destination permission denied). The function returns `True`/`False` but callers don't always check the return value.
**Fix:** After `shutil.copy2()`, verify `dest.exists()` and `dest.stat().st_size == src.stat().st_size`.

#### L2: `backup_name` of `.` Creates Confusing Directory
**Location:** `sanitize_name()` in `core.py`
**Issue:** Input `...` becomes `.` after sanitization. A backup named `.` is technically valid but creates a hidden directory.
**Fix:** Reject names that are only dots after sanitization.

#### L3: `detect_shell()` Returns Incorrect Shell on Non-Login
**Location:** `detect_shell()` in `core.py`
**Issue:** Reads `$SHELL` environment variable, which reflects the user's default shell, not necessarily the currently running shell. In a `bash` subshell started from `fish`, it returns `fish`.
**Impact:** Backup name includes wrong shell. Minor UX issue.
**Fix:** Detect parent process name as fallback.

#### L4: No Automated Tests
**Location:** Entire codebase
**Issue:** Zero unit tests, zero integration tests.
**Impact:** Regressions go undetected. Refactoring is risky.
**Fix:** Add pytest-based tests for core utilities, merge logic, and path validation.

---

## Part 2: Sync Feature Design (Revised)

### Design Principles

1. **Never destroy without a snapshot.** Every sync must create a full local snapshot first.
2. **Never overwrite SSH keys.** SSH is always opt-in with explicit confirmation.
3. **Merge, don't replace.** Shell configs should be combined intelligently.
4. **Verify everything.** Checksums, dry-runs, and pre-flight validation.
5. **Fail safe.** If any component fails, offer one-command rollback to pre-sync state.

### Sync vs Restore vs Backup

| Operation | Direction | Destructive? | Use Case |
|-----------|-----------|-------------|----------|
| **backup** | Local → Git repo | No | Save current environment |
| **restore** | Git repo → Local | Yes (blind overwrite) | Rebuild machine from scratch |
| **sync** | Git repo → Local | No (merge with snapshot) | Update current machine with backup changes |

### Sync Workflow (Revised)

```
┌─────────────────┐
│  1. Pre-flight  │  Check deps, validate repo URL, clone backup
├─────────────────┤
│ 2. Verify Check │  Recompute SHA-256, compare to manifest
├─────────────────┤
│ 3. Snapshot     │  Full local backup → ~/.shellpack/snapshots/<ts>/
├─────────────────┤
│ 4. Diff & Plan  │  Compare each component; build change plan
├─────────────────┤
│ 5. Interactive  │  Show diff table; user approves each component
├─────────────────┤
│ 6. Apply        │  Apply changes component-by-component
├─────────────────┤
│ 7. Verify       │  Confirm changes applied; report failures
├─────────────────┤
│ 8. Rollback     │  On failure, offer to restore from snapshot
└─────────────────┘
```

### Component Diff Matrix

For each component, sync computes:

| Status | Meaning | Default Action |
|--------|---------|----------------|
| `identical` | Backup == Local | Skip |
| `backup_only` | In backup, not local | Offer to apply |
| `local_only` | In local, not backup | Keep local |
| `conflict` | Both exist, differ | Offer merge strategies |

### Merge Strategies (Per Component)

| Component | Backup Strategy | Conflict Strategy |
|-----------|----------------|-------------------|
| **Fish config** | Extract if local missing | Smart merge: append new functions/aliases from backup; preserve local `fish_variables` |
| **Bash config** | Copy if local missing | Smart merge: union of aliases and exports; backup additions appended as `# ShellPack merged` section |
| **Zsh config** | Copy if local missing | Same as Bash; Oh-My-Zsh only restored if missing entirely |
| **Starship** | Copy if local missing | Full replace (declarative config, safe) |
| **Git config** | Copy if local missing | Merge: local `user.name`/`user.email` preserved; backup settings added if absent |
| **Packages** | Install missing from backup list | N/A (additive only) |
| **Conda** | Create env from `.yml` if missing | Skip existing; offer `conda env update` |
| **SSH** | Never auto-copy | Explicit user approval required; never overwrite existing |
| **History** | Append backup entries to local | Deduplicate by command text + timestamp |
| **Cloud creds** | Never auto-copy | Explicit user approval; never overwrite existing |

### Smart Shell Config Merge Algorithm

A lightweight, safe merge that doesn't require a full shell parser:

1. **Extract aliases:** Parse `alias name='value'` or `alias name="value"` from both files
2. **Extract exports:** Parse `export VAR=value` from both files
3. **Identify new items:** Aliases/exports in backup but NOT in local → append to local file
4. **Identify conflicts:** Same name, different value → flag for user decision
5. **Preserve everything else:** Functions, conditionals, sourcing, custom logic stays untouched
6. **Append section:** New items go into a clearly marked `# === Merged from ShellPack backup ===` block

This errs on the side of preserving local customizations.

### Package Sync Details

For each supported package manager:

```python
def sync_packages(backup_dir: Path, pm: str) -> SyncResult:
    backup_pkgs = parse_package_list(backup_dir / "packages" / f"{pm}_manual.txt")
    local_pkgs = get_installed_packages(pm)
    missing = backup_pkgs - local_pkgs

    for pkg in missing:
        if is_safe_package_name(pkg):  # Validate before install
            install_package(pm, pkg)
```

Package name validation: `^[a-zA-Z0-9._+-]+$` (reject anything with shell metacharacters).

### Pre-Sync Snapshot Format

```
~/.shellpack/snapshots/
└── 2026-05-22T14-30-00/
    ├── manifest.json          # Snapshot metadata
    ├── shells/
    │   ├── fish_config.tar.gz
    │   ├── bash/
    │   └── zsh/
    ├── config/
    │   ├── starship.toml
    │   └── gitconfig
    ├── packages/
    ├── ssh/                   # Only if user opts in
    ├── conda/
    └── history/
```

Snapshots are gzip-compressed. A `shellpack restore-snapshot <timestamp>` command restores from a snapshot.

### Rollback During Sync

If a component fails during sync:
1. Log the failure
2. Skip remaining components in that category
3. Offer user: `Continue with remaining components?` / `Rollback all sync changes?`
4. Rollback restores from the pre-sync snapshot

---

## Part 3: Implementation Plan (Revised)

### Phase 1: Critical Bug Fixes (Must Be First)

**These fix active data-loss and corruption bugs.**

| # | File | Fix | Verification |
|---|------|-----|--------------|
| 1.1 | `core.py` | Fix `init_repo()`: add `str(dest_dir)` to `git init` | Run backup from inside a git repo; verify CWD repo is untouched |
| 1.2 | `core.py` | Fix `copy_directory()`: remove `shutil.rmtree()`; use `dirs_exist_ok=True` | Verify existing dirs aren't destroyed on copy failure |
| 1.3 | `core.py` | Add `safe_extract_tar()` helper with path traversal validation | Test with malicious tarball containing `../../../etc/passwd` |
| 1.4 | `restore.py` | Replace all `tar.extractall()` calls with `safe_extract_tar()` | Verify safe extraction in all 4 restore functions |
| 1.5 | `core.py` | Refactor rollback: store `(func, args, kwargs)` instead of strings | Verify rollback works after simulating a failure |
| 1.6 | `core.py` | Fix `generate_ssh_key()`: remove passphrase from CLI | Verify `ps aux` shows no passphrase |
| 1.7 | `restore.py` | Fix `set_default_shell()`: pipe shell path into `tee` | Verify `/etc/shells` is actually modified |
| 1.8 | `restore.py` | Fix `restore_conda()`: check if env exists before create | Verify existing envs are skipped gracefully |
| 1.9 | `core.py` | Fix `validate_git_url()`: whitelist schemes only | Verify `file://` and `javascript:` are rejected |
| 1.10 | `restore.py` | Add manifest checksum verification in `do_restore()` | Tamper with a file in backup, verify restore fails |
| 1.11 | `shellpack.ps1` | Fix command injection: validate username, use safe arg passing | Test with malicious username input |

### Phase 2: Snapshot Infrastructure (Required for Sync Safety)

| # | File | Description |
|---|------|-------------|
| 2.1 | `shellpack/snapshot.py` | **New.** Create local snapshots: `create_snapshot(dest_dir)` with full backup logic |
| 2.2 | `shellpack/snapshot.py` | Restore from snapshot: `restore_snapshot(snapshot_dir)` |
| 2.3 | `shellpack/snapshot.py` | List and prune snapshots: `list_snapshots()`, `prune_snapshots(keep=10)` |
| 2.4 | `shellpack/cli.py` | Add `snapshot` and `restore-snapshot` commands |

### Phase 3: Diff & Merge Engine (Core Sync Logic)

| # | File | Description |
|---|------|-------------|
| 3.1 | `shellpack/diff.py` | **New.** `ComponentDiff` dataclass, `diff_directory()`, `diff_file()`, `diff_package_lists()` |
| 3.2 | `shellpack/merge.py` | **New.** `merge_shell_config()`, `merge_git_config()`, `merge_history()`, `union_lines()` |
| 3.3 | `shellpack/diff.py` | `diff_shell_config()` — extract aliases/exports and compare |
| 3.4 | `shellpack/merge.py` | Package sync: `sync_packages(pm, backup_dir)` — compute missing, install safely |

### Phase 4: Sync Orchestrator

| # | File | Description |
|---|------|-------------|
| 4.1 | `shellpack/sync.py` | **New.** `do_sync()` — full sync workflow with pre-flight, snapshot, diff, interactive approval, apply |
| 4.2 | `shellpack/sync.py` | Interactive component selection: show diff matrix, collect user choices |
| 4.3 | `shellpack/sync.py` | Apply changes with per-component rollback points |
| 4.4 | `shellpack/sync.py` | Post-sync report: what changed, snapshot location, restart suggestion |

### Phase 5: CLI Integration & Polish

| # | File | Description |
|---|------|-------------|
| 5.1 | `shellpack/cli.py` | Add `sync` command with `--auto` (non-interactive, safe defaults) and `--dry-run` |
| 5.2 | `shellpack/cli.py` | Update help text to document sync, snapshot, and restore-snapshot |
| 5.3 | `shellpack/__init__.py` | Bump version to 2.1.0 |
| 5.4 | `README.md` | Document sync usage and safety guarantees |

### Phase 6: Testing

| # | Test | Description |
|---|------|-------------|
| 6.1 | Path traversal | Craft malicious tarball; verify `safe_extract_tar()` rejects it |
| 6.2 | Snapshot roundtrip | Create snapshot, modify files, restore snapshot, verify original state |
| 6.3 | Shell config merge | Merge two bashrc files with overlapping aliases; verify union behavior |
| 6.4 | Git config merge | Merge backup and local gitconfig; verify local user.name preserved |
| 6.5 | Dry-run sync | Run `sync --dry-run`; verify no files modified |
| 6.6 | Rollback | Simulate sync failure; verify snapshot restores pre-sync state |
| 6.7 | PowerShell injection | Test WSL user creation with malicious input; verify rejection |

---

## Part 4: File Change Summary (Revised)

| File | Action | Est. Lines |
|------|--------|------------|
| `shellpack/core.py` | Fix init_repo, copy_directory, rollback, safe_extract, URL validation, SSH gen, copy_file verify | +120, -50 |
| `shellpack/backup.py` | Use safe tar helper, no other changes | +5, -5 |
| `shellpack/restore.py` | Use safe extract, fix tee, fix conda, verify checksums | +50, -30 |
| `shellpack/cli.py` | Add sync, snapshot, restore-snapshot commands | +50, -10 |
| `shellpack/snapshot.py` | **New** | ~200 |
| `shellpack/diff.py` | **New** | ~250 |
| `shellpack/merge.py` | **New** | ~300 |
| `shellpack/sync.py` | **New** | ~500 |
| `shellpack.ps1` | Fix command injection, validate inputs | +40, -25 |
| `shellpack/__init__.py` | Version bump | +1, -1 |
| `tests/` | **New directory** with pytest tests | ~400 |

**Total:** ~1,800 lines changed/added

---

## Part 5: Risk Assessment & Mitigations (Revised)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sync overwrites local shell customizations | Medium | High | Pre-sync snapshot + smart merge + interactive approval |
| Sync installs malicious packages | Low | Critical | Package name validation (`^[a-zA-Z0-9._+-]+$`) + only install from backup list |
| Malicious backup tarball | Low | Critical | Path traversal fix (C1) + checksum verification (H5) |
| Snapshot consumes excessive disk | Medium | Low | Gzip compression + automatic pruning (keep 10) |
| Merge produces broken shell config | Low | High | Merge appends new items only; never modifies existing lines. User can restore snapshot. |
| Conda env update breaks working env | Medium | Medium | Conda sync skips existing envs by default; `conda env update` is opt-in |
| SSH key loss | Very Low | Critical | SSH keys never auto-synced; explicit confirmation required |
| PowerShell/WSL injection | Medium | High | Input validation + safe argument passing |

---

## Part 6: Verification Checklist for Final Delivery

Before declaring the sync feature complete, every item below must pass:

- [ ] Malicious tarball with `../../../` paths is rejected by `safe_extract_tar()`
- [ ] `init_repo()` from inside a git repo does not corrupt that repo
- [ ] `copy_directory()` failure does not delete the destination
- [ ] Rollback actions execute without `shell=True`
- [ ] `set_default_shell()` actually adds shell to `/etc/shells`
- [ ] `restore_conda()` skips existing environments
- [ ] Manifest checksum mismatch causes restore/sync to fail
- [ ] `validate_git_url("file:///etc/passwd")` returns `False`
- [ ] `shellpack.ps1` rejects username `"; rm -rf /; "`
- [ ] Dry-run sync modifies zero files
- [ ] Full sync creates a restorable snapshot
- [ ] Snapshot restore returns system to pre-sync state
- [ ] Shell config merge preserves local aliases while adding backup ones
- [ ] Git config merge preserves local `user.name`/`user.email`
- [ ] Package sync only installs packages from backup list
- [ ] SSH keys require explicit user approval to sync
- [ ] All tests pass: `pytest tests/`

---

*Revision 2 generated after second-pass deep audit. All findings verified against source code. C3 and C4 are new critical bugs not present in Revision 1.*
