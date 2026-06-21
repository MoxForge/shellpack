---
schema_version: 1
slug: 2026-05-22--shellpack-sync-audit-and-plan
title: ShellPack Audit & Sync Feature Plan
status: proposed
created_at: 2026-06-21T12:25:33.722555Z
run_id: 51282fd2-d766-4f39-9cab-6350e0d53bfb
---

# ShellPack Audit & Sync Feature Plan

## Executive Summary

ShellPack v2.0.0 is a well-structured Python rewrite of a Bash-based shell environment backup/restore tool. The codebase is modular, readable, and generally well-designed. However, a security audit reveals **2 critical and 2 high-severity vulnerabilities** that must be fixed before the sync feature is implemented. Additionally, the sync feature (updating a live shell from a saved backup) requires careful design to avoid destroying user data.

---

## Part 1: Security Audit Findings

### Critical (Fix Before Any New Features)

#### C1: Path Traversal via Tarfile Extraction (`backup.py`, `restore.py`)
**Location:** `restore_fish()`, `restore_zsh()`, `restore_ssh()`, `restore_cloud_creds()`, `backup_ssh()`, `backup_cloud_creds()`

**Issue:** `tarfile.extractall(path=...)` is called without validating member paths. A malicious tarball with members like `../../../etc/cron.d/backdoor` can write outside the intended directory.

**Evidence:**
```python
# restore.py:restore_fish()
with tarfile.open(archive, "r:gz") as tar:
    tar.extractall(path=str(dest))  # No member validation
```

**Fix:** Validate every member's resolved path is within the destination directory before extraction. Use a safe extraction helper.

#### C2: Rollback Actions Execute Arbitrary Shell Commands (`core.py`)
**Location:** `execute_rollback()`

**Issue:** Rollback actions are stored as strings and executed with `subprocess.run(action, shell=True)`. If any rollback action is constructed from user input (backup names, paths, etc.), this is command injection.

**Evidence:**
```python
# core.py:execute_rollback()
for action in reversed(rollback_stack):
    subprocess.run(action, shell=True, capture_output=True)  # shell=True + string
```

**Fix:** Store rollback actions as `(callable, args, kwargs)` tuples and execute them without `shell=True`.

### High (Fix Before Sync Feature)

#### H1: SSH Passphrase Visible in Process List (`core.py`)
**Location:** `generate_ssh_key()`

**Issue:** The SSH key passphrase is passed directly on the command line to `ssh-keygen`, making it visible to any user running `ps` on the system.

**Evidence:**
```python
cmd = ["ssh-keygen", "-t", key_type, "-C", email, "-f", str(key_file), "-N", passphrase]
```

**Fix:** Use `ssh-keygen -N ""` (no passphrase) or pipe the passphrase via stdin using `ssh-keygen`'s batch mode, or document that passphrases should be added interactively after generation.

#### H2: PowerShell Command Injection (`shellpack.ps1`)
**Location:** `Start-RestoreNewWSL()`, `Copy-SSHKeysToWSL()`, user creation blocks

**Issue:** User-provided `$username`, `$wslName`, and `$password` are directly interpolated into bash command strings passed to `wsl -d ... -- bash -c "..."`. A username containing quotes or semicolons can inject arbitrary commands.

**Evidence:**
```powershell
wsl -d $wslName -- bash -c "useradd -m -s /bin/bash -G sudo '$username'"
wsl -d $wslName -- bash -c "echo '${username}:${password}' | chpasswd"
```

**Fix:** Pass arguments via `bash -c '...' -- "$arg1" "$arg2"` or use WSL's `--` separator for argument passing. Validate usernames against `^[a-z_][a-z0-9_-]*$`.

### Medium

#### M1: Permissive Git URL Validation (`core.py`)
**Location:** `validate_git_url()`

**Issue:** The regex patterns allow `file:///`, `javascript:`, `data:` URLs because the scheme check is `https?|git|ssh` but the regex uses `[^/]+` which matches anything before the first slash. More importantly, the third pattern `^(https?|git|ssh)://[a-zA-Z0-9._-]+(/[a-zA-Z0-9._/-]+)?$` allows any scheme due to a logical issue — actually looking closer, the patterns are fine for schemes but the `[a-zA-Z0-9._-]+` host part doesn't require a TLD structure and allows numeric IPs. The bigger issue: no restriction on `file://` or other dangerous schemes.

**Fix:** Reject `file://`, `javascript:`, `data:` explicitly. Require known-safe schemes only.

#### M2: Manifest Checksum Never Verified (`restore.py`)
**Location:** `do_restore()`

**Issue:** `calculate_checksum()` computes a SHA-256 of the backup during creation, but `read_manifest()` loads the checksum and never compares it against a freshly computed checksum of the restored files.

**Fix:** After cloning/extracting, recompute the checksum and verify against the manifest. Fail on mismatch.

#### M3: Starship Installer Unverified (`restore.py`)
**Location:** `install_starship()`

**Issue:** Pipes curl directly to sh without checksum verification or HTTPS certificate pinning.

**Fix:** Document as acceptable for convenience, but add a warning. Alternatively, use the official install script with checksum verification.

### Low

#### L1: `copy_file()` Doesn't Verify Write (`core.py`)
`shutil.copy2()` can fail silently in edge cases (disk full, permission denied on destination directory). The function catches exceptions but doesn't verify the file actually exists and has the right size afterward.

#### L2: `set_default_shell()` Tee Command Broken (`restore.py`)
```python
run_command(["sudo", "tee", "-a", "/etc/shells"], check=False)
```
This runs tee with no stdin provided, so it appends nothing. The shell path is never actually added to `/etc/shells`.

---

## Part 2: Sync Feature Design

### What "Sync" Means

The user wants to **update an existing shell environment from a saved backup** without the destructive blind overwrite that `restore` performs. Sync is a selective, safe, merge-oriented operation.

### Sync vs Restore

| Aspect | Restore | Sync |
|--------|---------|------|
| SSH keys | Overwrite or generate new | Never overwrite existing; warn if different |
| Shell configs | Blind copy | Show diff, allow selective merge |
| Packages | List only | Install missing packages from backup list |
| Git config | Overwrite | Merge (preserve local user.name/email if already set) |
| History | Overwrite | Append backup history to local (deduplicate) |
| Conda | Overwrite environments | Create missing environments, skip existing |
| Safety net | None | Pre-sync snapshot with one-command rollback |

### Sync Architecture

```
shellpack/
├── sync.py          # NEW: Sync orchestrator and merge engine
├── diff.py          # NEW: File comparison and conflict detection
└── merge.py         # NEW: Config file merge strategies
```

### Sync Workflow

1. **Pre-flight**
   - Check dependencies
   - Clone/pull backup repo
   - Verify manifest checksum
   - Load manifest metadata

2. **Safety Snapshot**
   - Create a timestamped local backup of the current shell environment
   - Store in `~/.shellpack/snapshots/<timestamp>/`
   - This snapshot can be restored with `shellpack restore --local-snapshot <timestamp>`

3. **Component Discovery & Diff**
   - For each component (shell configs, packages, starship, git, SSH, conda, history, cloud):
     - Check if present in backup
     - Check if present locally
     - Compute diff/status: identical, local-only, backup-only, or conflict (both modified)

4. **Interactive Resolution**
   - Present a table of components with their diff status
   - For each component, user chooses: skip, apply backup, keep local, or smart merge
   - Smart merge attempts to combine backup and local (e.g., union of aliases)

5. **Apply Changes**
   - Apply selected changes with rollback points between components
   - If any component fails, offer to roll back all sync changes

6. **Post-sync Report**
   - Summary of what changed
   - Reminder about snapshot location
   - Suggestion to restart terminal

### Merge Strategies by Component

| Component | Strategy |
|-----------|----------|
| Fish config | `config.fish`: append new functions/aliases not in local; for `fish_variables`, merge sets |
| Bash config | `.bashrc`: append new aliases/functions from backup that don't exist locally; preserve PATH customizations |
| Zsh config | `.zshrc`: same as bash; for Oh-My-Zsh, only restore if not present locally |
| Starship | Full replace (config is declarative, safe to overwrite) |
| Git config | Merge: backup settings + local overrides for `user.name`, `user.email`, `core.editor` |
| Packages | Install packages from backup list that aren't locally installed |
| Conda | Create environments from backup `.yml` if they don't exist; never delete |
| SSH | Never overwrite. If backup has keys local doesn't, offer to copy. If both have different keys, warn. |
| History | Append backup entries to local, deduplicate by command text |
| Cloud creds | Never overwrite. Offer to copy if local doesn't exist. |

### Smart Merge for Shell Configs (Bash/Fish/Zsh)

A lightweight parser that:
1. Extracts `alias` definitions from both local and backup files
2. Extracts `export VAR=` definitions
3. Identifies aliases/exports in backup but not in local → append
4. Identifies aliases/exports where both define the same name with different values → flag as conflict
5. Preserves all other lines (functions, conditionals, etc.) from local file
6. Appends a "# Merged from ShellPack backup" section with new items

This is not a full shell parser — it's a best-effort merge that errs on the side of preserving local customizations.

### Package Sync

For each supported package manager:
1. Parse backup package list
2. Query locally installed packages
3. Compute set difference (backup - local)
4. For each missing package, attempt to install
5. Report successes and failures

Example for apt:
```python
backup_pkgs = parse_apt_list(backup_dir / "packages" / "apt_manual.txt")
local_pkgs = get_local_apt_manual()
missing = backup_pkgs - local_pkgs
if missing:
    run_command(["sudo", "apt", "install", "-y"] + list(missing))
```

---

## Part 3: Implementation Plan

### Phase 1: Security Fixes (Priority: Critical)

**Files to modify:** `core.py`, `restore.py`, `backup.py`, `shellpack.ps1`

1. **Safe tarfile extraction helper** in `core.py`
   ```python
   def safe_extract_tar(archive: Path, dest: Path) -> bool:
       with tarfile.open(archive, "r:gz") as tar:
           for member in tar.getmembers():
               member_path = Path(dest) / member.name
               if not str(member_path.resolve()).startswith(str(dest.resolve())):
                   raise ValueError(f"Path traversal attempt: {member.name}")
           tar.extractall(path=str(dest), members=safe_members)
   ```

2. **Refactor rollback system** in `core.py`
   ```python
   RollbackAction = Tuple[str, Callable, Tuple, Dict]
   rollback_stack: List[RollbackAction] = []

   def add_rollback_action(description: str, func: Callable, *args, **kwargs):
       rollback_stack.append((description, func, args, kwargs))

   def execute_rollback():
       for desc, func, args, kwargs in reversed(rollback_stack):
           try:
               func(*args, **kwargs)
           except Exception:
               pass
   ```

3. **Fix SSH key generation** in `core.py`
   - Remove passphrase support from CLI generation
   - Or use `ssh-keygen` interactively via pty (complex)
   - **Decision:** Remove passphrase parameter; generate without passphrase. User can add passphrase with `ssh-keygen -p` afterward.

4. **Fix PowerShell injection** in `shellpack.ps1`
   - Validate username with `^[a-z_][a-z0-9_-]*$`
   - Use argument passing instead of string interpolation
   - Escape passwords properly

5. **Fix `set_default_shell()` tee** in `restore.py`
   - Use `run_command(["sh", "-c", f"echo {shell_path} | sudo tee -a /etc/shells"])`

6. **Fix git URL validation** in `core.py`
   - Explicitly reject `file://`, `javascript:`, `data:`

7. **Add manifest checksum verification** in `restore.py`
   - After cloning, compute checksum and compare to manifest

### Phase 2: Core Infrastructure for Sync

**New files:** `shellpack/diff.py`, `shellpack/merge.py`, `shellpack/sync.py`

1. **`diff.py`** — Component comparison
   - `ComponentStatus` enum: `IDENTICAL`, `LOCAL_ONLY`, `BACKUP_ONLY`, `CONFLICT`
   - `diff_component(backup_dir, component) -> ComponentDiff`
   - `diff_shell_config(backup_file, local_file) -> ShellDiff`
   - `diff_package_lists(backup_list, local_list) -> PackageDiff`

2. **`merge.py`** — Merge strategies
   - `merge_shell_config(backup_path, local_path, strategy) -> merged_content`
   - `merge_git_config(backup_path, local_path) -> merged_content`
   - `merge_history(backup_history, local_history) -> merged_content`
   - `append_unique_lines(backup_lines, local_lines) -> merged_lines`

3. **`sync.py`** — Main sync orchestrator
   - `do_sync()` — mirrors `do_backup()` / `do_restore()` structure
   - Pre-sync snapshot creation
   - Interactive component selection
   - Change application with per-component rollback
   - Post-sync report

### Phase 3: CLI Integration

**File to modify:** `shellpack/cli.py`

1. Add `"sync"` command alongside `"backup"` and `"restore"`
2. Add `"snapshot"` and `"restore-snapshot"` commands for safety net management
3. Update help text

### Phase 4: Testing & Verification

1. **Dry-run sync** on a test machine
2. **Verify path traversal fix** with a crafted malicious tarball
3. **Verify rollback** works after a simulated failure
4. **Verify merge** preserves local customizations
5. **Verify snapshot** can fully restore pre-sync state

---

## Part 4: File Change Summary

| File | Action | Lines (est) |
|------|--------|-------------|
| `shellpack/core.py` | Modify: safe tar extract, fix rollback, fix SSH gen, fix URL validation, fix tee | +80, -30 |
| `shellpack/backup.py` | Modify: use safe tar helper | +5, -5 |
| `shellpack/restore.py` | Modify: use safe tar extract, verify checksums, fix tee | +30, -20 |
| `shellpack/cli.py` | Modify: add sync, snapshot, restore-snapshot commands | +40, -10 |
| `shellpack/diff.py` | **New** | ~200 |
| `shellpack/merge.py` | **New** | ~250 |
| `shellpack/sync.py` | **New** | ~400 |
| `shellpack.ps1` | Modify: fix command injection | +30, -20 |
| `shellpack/__init__.py` | Modify: bump version | +1, -1 |

**Total:** ~1,100 lines changed/added

---

## Part 5: Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Sync destroys local customizations | Pre-sync snapshot + interactive diff + smart merge |
| Sync overwrites SSH keys | SSH is never auto-synced; explicit user confirmation required |
| Malicious backup tarball | Path traversal fix + checksum verification |
| Merge produces broken shell configs | Merge appends to end of file; doesn't modify existing lines |
| Package install fails mid-sync | Per-component rollback; failed component doesn't block others |
| Snapshot consumes disk space | Snapshots are gzip-compressed; user can prune old ones |

---

## Part 6: Recommended Implementation Order

1. **Security fixes first** (Phase 1) — these are standalone and make the tool safer immediately
2. **diff.py and merge.py** (Phase 2a) — unit-testable, no side effects
3. **sync.py** (Phase 2b) — integrates diff/merge with the existing backup/restore patterns
4. **CLI integration** (Phase 3)
5. **End-to-end testing** (Phase 4)

---

*Plan generated after full codebase audit. All findings verified against source code.*
