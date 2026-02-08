#!/usr/bin/env bash

#===============================================================================
#
#   ███████╗██╗  ██╗███████╗██╗     ██╗     ███████╗██╗   ██╗███╗   ██╗ ██████╗
#   ██╔════╝██║  ██║██╔════╝██║     ██║     ██╔════╝╚██╗ ██╔╝████╗  ██║██╔════╝
#   ███████╗███████║█████╗  ██║     ██║     ███████╗ ╚████╔╝ ██╔██╗ ██║██║     
#   ╚════██║██╔══██║██╔══╝  ██║     ██║     ╚════██║  ╚██╔╝  ██║╚██╗██║██║     
#   ███████║██║  ██║███████╗███████╗███████╗███████║   ██║   ██║ ╚████║╚██████╗
#   ╚══════╝╚═╝  ╚═╝╚══════╝╚══════╝╚══════╝╚══════╝   ╚═╝   ╚═╝  ╚═══╝ ╚═════╝
#
#   Cross-Platform Shell Environment Backup & Restore
#   
#   https://github.com/MoxForge/shellpack
#
#===============================================================================
#
# VERSION:     1.0.0
# LICENSE:     MIT
# AUTHOR:      MoxForge
# PLATFORMS:   macOS, Linux, Windows (WSL)
#
# USAGE:
#   shellpack backup              Backup shell environment to Git repo
#   shellpack restore             Restore shell environment from Git repo
#   shellpack --help              Show help message
#   shellpack --version           Show version
#
# ONE-LINER (run directly from GitHub):
#   bash <(curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.sh) backup
#   bash <(curl -sL https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.sh) restore
#
#===============================================================================

set -euo pipefail

# Version
readonly VERSION="1.0.0"
readonly SCRIPT_NAME="shellpack"
readonly GITHUB_REPO="https://github.com/MoxForge/shellpack"

# Colors (check if terminal supports colors)
if [[ -t 1 ]] && [[ "${TERM:-}" != "dumb" ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly BLUE='\033[0;34m'
    readonly CYAN='\033[0;36m'
    readonly GRAY='\033[0;90m'
    readonly BOLD='\033[1m'
    readonly NC='\033[0m'
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly CYAN=''
    readonly GRAY=''
    readonly BOLD=''
    readonly NC=''
fi

# Configuration
readonly TEMP_DIR="${TMPDIR:-/tmp}/${SCRIPT_NAME}_$$"
readonly MANIFEST_FILE="manifest.json"
readonly LOG_FILE="${TEMP_DIR}/shellpack.log"

# Flags
VERBOSE=false
DRY_RUN=false

#===============================================================================
# Logging & Output Functions
#===============================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    # Always log to file if it exists
    if [[ -d "$(dirname "$LOG_FILE")" ]]; then
        echo "[$timestamp] [$level] $message" >> "$LOG_FILE" 2>/dev/null || true
    fi
    
    # Print to stdout if verbose or if it's an error
    if $VERBOSE || [[ "$level" == "ERROR" ]]; then
        echo -e "${GRAY}[$timestamp]${NC} $message" >&2
    fi
}

print_banner() {
    echo ""
    echo -e "${CYAN}┌──────────────────────────────────────────────────────────────┐${NC}"
    echo -e "${CYAN}│${NC}  ${BOLD}ShellPack${NC} v${VERSION}                                          ${CYAN}│${NC}"
    echo -e "${CYAN}│${NC}  Cross-Platform Shell Environment Backup & Restore          ${CYAN}│${NC}"
    echo -e "${CYAN}└──────────────────────────────────────────────────────────────┘${NC}"
    echo ""
}

print_header() {
    local title="$1"
    echo ""
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}  ${title}${NC}"
    echo -e "${CYAN}══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_section() {
    local title="$1"
    echo ""
    echo -e "${YELLOW}──────────────────────────────────────────────────────────────${NC}"
    echo -e "${YELLOW}  ${title}${NC}"
    echo -e "${YELLOW}──────────────────────────────────────────────────────────────${NC}"
}

print_status() {
    local message="$1"
    local status="${2:-info}"
    
    local icon color
    case "$status" in
        ok|success)  icon="✓"; color="$GREEN" ;;
        error|fail)  icon="✗"; color="$RED" ;;
        warn)        icon="!"; color="$YELLOW" ;;
        skip)        icon="→"; color="$GRAY" ;;
        info)        icon="•"; color="$BLUE" ;;
        *)           icon=" "; color="$NC" ;;
    esac
    
    echo -e "  ${color}[${icon}]${NC} ${message}"
    log "INFO" "$message"
}

print_item() {
    echo -e "      ${GRAY}•${NC} $1"
}

print_error() {
    echo -e "  ${RED}[✗] ERROR:${NC} $1" >&2
    log "ERROR" "$1"
}

print_warning() {
    echo -e "  ${YELLOW}[!] WARNING:${NC} $1"
    log "WARN" "$1"
}

print_success() {
    echo -e "  ${GREEN}[✓]${NC} $1"
}

print_progress() {
    local current="$1"
    local total="$2"
    local message="${3:-}"
    local percent=$((current * 100 / total))
    local filled=$((percent / 2))
    local empty=$((50 - filled))
    
    printf "\r  [${GREEN}%${filled}s${NC}%${empty}s] %3d%% %s" "" "" "$percent" "$message"
    
    if [[ $current -eq $total ]]; then
        echo ""
    fi
}

#===============================================================================
# User Input Functions
#===============================================================================

read_input() {
    local prompt="$1"
    local default="${2:-}"
    local result
    
    if [[ -n "$default" ]]; then
        echo -en "  ${CYAN}$prompt${NC} [${GRAY}$default${NC}]: "
    else
        echo -en "  ${CYAN}$prompt${NC}: "
    fi
    
    read -r result
    
    if [[ -z "$result" ]]; then
        echo "$default"
    else
        echo "$result"
    fi
}

read_yes_no() {
    local prompt="$1"
    local default="${2:-y}"
    local result
    
    local hint
    if [[ "$default" == "y" ]]; then
        hint="Y/n"
    else
        hint="y/N"
    fi
    
    echo -en "  ${CYAN}$prompt${NC} [${GRAY}$hint${NC}]: "
    read -r result
    
    if [[ -z "$result" ]]; then
        result="$default"
    fi
    
    [[ "${result,,}" == "y" || "${result,,}" == "yes" ]]
}

read_choice() {
    local prompt="$1"
    shift
    local options=("$@")
    local choice
    
    echo ""
    for i in "${!options[@]}"; do
        echo -e "      ${GRAY}[$((i+1))]${NC} ${options[$i]}"
    done
    echo ""
    
    while true; do
        echo -en "  ${CYAN}$prompt${NC} [${GRAY}1${NC}]: "
        read -r choice
        
        if [[ -z "$choice" ]]; then
            choice=1
        fi
        
        if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#options[@]} )); then
            echo "$choice"
            return 0
        fi
        
        print_error "Invalid choice. Please enter 1-${#options[@]}"
    done
}

read_password() {
    local prompt="$1"
    local password
    
    echo -en "  ${CYAN}$prompt${NC}: "
    read -rs password
    echo ""
    
    echo "$password"
}

#===============================================================================
# System Detection Functions
#===============================================================================

detect_os() {
    local os
    case "$(uname -s)" in
        Linux*)
            if grep -qi microsoft /proc/version 2>/dev/null; then
                os="wsl"
            else
                os="linux"
            fi
            ;;
        Darwin*)
            os="macos"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            os="windows"
            ;;
        *)
            os="unknown"
            ;;
    esac
    
    log "INFO" "Detected OS: $os"
    echo "$os"
}

detect_arch() {
    local arch
    case "$(uname -m)" in
        x86_64|amd64)
            arch="amd64"
            ;;
        arm64|aarch64)
            arch="arm64"
            ;;
        armv7l)
            arch="arm"
            ;;
        *)
            arch="unknown"
            ;;
    esac
    
    log "INFO" "Detected architecture: $arch"
    echo "$arch"
}

detect_package_manager() {
    local os="$1"
    local pm
    
    case "$os" in
        macos)
            pm="brew"
            ;;
        linux|wsl)
            if command -v apt &>/dev/null; then
                pm="apt"
            elif command -v dnf &>/dev/null; then
                pm="dnf"
            elif command -v yum &>/dev/null; then
                pm="yum"
            elif command -v pacman &>/dev/null; then
                pm="pacman"
            elif command -v zypper &>/dev/null; then
                pm="zypper"
            elif command -v apk &>/dev/null; then
                pm="apk"
            else
                pm="unknown"
            fi
            ;;
        *)
            pm="unknown"
            ;;
    esac
    
    log "INFO" "Detected package manager: $pm"
    echo "$pm"
}

detect_shell() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")
    log "INFO" "Detected default shell: $shell_name"
    echo "$shell_name"
}

#===============================================================================
# Dependency Check Functions
#===============================================================================

check_command() {
    local cmd="$1"
    local name="${2:-$cmd}"
    
    if command -v "$cmd" &>/dev/null; then
        log "INFO" "Found: $name"
        return 0
    else
        log "WARN" "Missing: $name"
        return 1
    fi
}

check_dependencies() {
    print_section "Checking Dependencies"
    echo ""
    
    local missing=()
    local os=$(detect_os)
    local pm=$(detect_package_manager "$os")
    
    # Required dependencies
    local required=("git" "curl" "tar")
    
    for dep in "${required[@]}"; do
        if check_command "$dep"; then
            print_status "$dep" "ok"
        else
            print_status "$dep - MISSING" "error"
            missing+=("$dep")
        fi
    done
    
    # Optional but recommended
    echo ""
    echo -e "  ${GRAY}Optional:${NC}"
    
    if check_command "jq"; then
        print_status "jq (JSON parsing)" "ok"
    else
        print_status "jq (JSON parsing) - not installed" "skip"
    fi
    
    if check_command "ssh"; then
        print_status "ssh" "ok"
    else
        print_status "ssh - not installed" "warn"
    fi
    
    # Check if any required dependencies are missing
    if [[ ${#missing[@]} -gt 0 ]]; then
        echo ""
        print_error "Missing required dependencies: ${missing[*]}"
        echo ""
        echo -e "  ${YELLOW}Install them with:${NC}"
        
        case "$pm" in
            apt)
                echo -e "    ${CYAN}sudo apt update && sudo apt install -y ${missing[*]}${NC}"
                ;;
            brew)
                echo -e "    ${CYAN}brew install ${missing[*]}${NC}"
                ;;
            dnf)
                echo -e "    ${CYAN}sudo dnf install -y ${missing[*]}${NC}"
                ;;
            pacman)
                echo -e "    ${CYAN}sudo pacman -S ${missing[*]}${NC}"
                ;;
            *)
                echo -e "    ${GRAY}Please install: ${missing[*]}${NC}"
                ;;
        esac
        
        echo ""
        return 1
    fi
    
    return 0
}

#===============================================================================
# Git Functions
#===============================================================================

parse_github_url() {
    local url="$1"
    local user_repo=""
    
    # Handle different URL formats
    if [[ "$url" =~ git@github\.com:(.+?)(\.git)?$ ]]; then
        user_repo="${BASH_REMATCH[1]}"
    elif [[ "$url" =~ github\.com[/:](.+?)(\.git)?$ ]]; then
        user_repo="${BASH_REMATCH[1]}"
    fi
    
    # Remove trailing .git if present
    user_repo="${user_repo%.git}"
    
    log "INFO" "Parsed GitHub URL: $url -> $user_repo"
    echo "$user_repo"
}

list_backups_from_repo() {
    local repo_url="$1"
    local user_repo
    user_repo=$(parse_github_url "$repo_url")
    
    if [[ -z "$user_repo" ]]; then
        log "ERROR" "Could not parse repository URL"
        return 1
    fi
    
    # Try GitHub API first (works for public repos)
    local api_url="https://api.github.com/repos/${user_repo}/contents/backups"
    local response
    
    log "INFO" "Fetching backup list from: $api_url"
    
    response=$(curl -sL -w "\n%{http_code}" "$api_url" 2>/dev/null) || true
    
    local http_code
    http_code=$(echo "$response" | tail -n1)
    local body
    body=$(echo "$response" | sed '$d')
    
    if [[ "$http_code" == "200" ]]; then
        # Parse JSON response
        if command -v jq &>/dev/null; then
            echo "$body" | jq -r '.[] | select(.type=="dir") | .name' 2>/dev/null
        else
            echo "$body" | grep -o '"name": "[^"]*"' | cut -d'"' -f4
        fi
    else
        log "WARN" "GitHub API returned: $http_code"
        echo ""
    fi
}

clone_repo() {
    local repo_url="$1"
    local dest_dir="$2"
    local depth="${3:-1}"
    
    log "INFO" "Cloning repository: $repo_url -> $dest_dir"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would clone: $repo_url" "info"
        return 0
    fi
    
    if git clone --depth "$depth" "$repo_url" "$dest_dir" 2>&1 | tee -a "$LOG_FILE"; then
        log "INFO" "Clone successful"
        return 0
    else
        log "ERROR" "Clone failed"
        return 1
    fi
}

push_to_repo() {
    local repo_dir="$1"
    local message="$2"
    
    log "INFO" "Pushing to repository: $message"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would push: $message" "info"
        return 0
    fi
    
    cd "$repo_dir"
    
    git add -A >> "$LOG_FILE" 2>&1
    git commit -m "$message" >> "$LOG_FILE" 2>&1 || true
    
    # Try main branch first, then master
    if git push -u origin main >> "$LOG_FILE" 2>&1; then
        return 0
    elif git push -u origin master >> "$LOG_FILE" 2>&1; then
        return 0
    else
        log "ERROR" "Push failed"
        return 1
    fi
}

#===============================================================================
# Backup Functions
#===============================================================================

backup_fish() {
    local dest_dir="$1"
    
    if [[ ! -d "$HOME/.config/fish" ]]; then
        print_status "Fish config not found" "skip"
        return 0
    fi
    
    mkdir -p "$dest_dir/shells/fish"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would backup Fish config" "info"
        return 0
    fi
    
    tar -czf "$dest_dir/shells/fish/fish_config.tar.gz" \
        -C "$HOME/.config" fish 2>/dev/null
    
    print_status "Fish config" "ok"
}

backup_bash() {
    local dest_dir="$1"
    local files=(".bashrc" ".bash_aliases" ".bash_profile" ".profile" ".bash_logout")
    local found=0
    
    mkdir -p "$dest_dir/shells/bash"
    
    for file in "${files[@]}"; do
        if [[ -f "$HOME/$file" ]]; then
            if ! $DRY_RUN; then
                cp "$HOME/$file" "$dest_dir/shells/bash/"
            fi
            ((found++))
        fi
    done
    
    if [[ $found -gt 0 ]]; then
        print_status "Bash config ($found files)" "ok"
    else
        print_status "Bash config not found" "skip"
    fi
}

backup_zsh() {
    local dest_dir="$1"
    local files=(".zshrc" ".zprofile" ".zshenv" ".zlogin" ".zlogout")
    local found=0
    
    mkdir -p "$dest_dir/shells/zsh"
    
    for file in "${files[@]}"; do
        if [[ -f "$HOME/$file" ]]; then
            if ! $DRY_RUN; then
                cp "$HOME/$file" "$dest_dir/shells/zsh/"
            fi
            ((found++))
        fi
    done
    
    # Backup Oh-My-Zsh if present
    if [[ -d "$HOME/.oh-my-zsh" ]]; then
        if ! $DRY_RUN; then
            tar -czf "$dest_dir/shells/zsh/ohmyzsh.tar.gz" \
                -C "$HOME" .oh-my-zsh 2>/dev/null
        fi
        print_status "Zsh config + Oh-My-Zsh" "ok"
    elif [[ $found -gt 0 ]]; then
        print_status "Zsh config ($found files)" "ok"
    else
        print_status "Zsh config not found" "skip"
    fi
}

backup_packages() {
    local dest_dir="$1"
    local pm="$2"
    
    mkdir -p "$dest_dir/packages"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would backup package list ($pm)" "info"
        return 0
    fi
    
    case "$pm" in
        apt)
            apt list --installed 2>/dev/null | grep -v "Listing..." > "$dest_dir/packages/apt_packages.txt"
            apt-mark showmanual 2>/dev/null > "$dest_dir/packages/apt_manual.txt"
            print_status "APT packages" "ok"
            ;;
        brew)
            brew list --formula > "$dest_dir/packages/brew_formula.txt" 2>/dev/null || true
            brew list --cask > "$dest_dir/packages/brew_cask.txt" 2>/dev/null || true
            brew leaves > "$dest_dir/packages/brew_leaves.txt" 2>/dev/null || true
            print_status "Homebrew packages" "ok"
            ;;
        dnf|yum)
            rpm -qa > "$dest_dir/packages/rpm_packages.txt" 2>/dev/null
            print_status "RPM packages" "ok"
            ;;
        pacman)
            pacman -Qe > "$dest_dir/packages/pacman_packages.txt" 2>/dev/null
            pacman -Qm > "$dest_dir/packages/pacman_aur.txt" 2>/dev/null || true
            print_status "Pacman packages" "ok"
            ;;
        *)
            print_status "Package manager not supported: $pm" "skip"
            ;;
    esac
}

backup_starship() {
    local dest_dir="$1"
    
    mkdir -p "$dest_dir/config"
    
    if [[ -f "$HOME/.config/starship.toml" ]]; then
        if ! $DRY_RUN; then
            cp "$HOME/.config/starship.toml" "$dest_dir/config/"
        fi
        print_status "Starship config" "ok"
    else
        print_status "Starship config not found" "skip"
    fi
}

backup_git_config() {
    local dest_dir="$1"
    
    mkdir -p "$dest_dir/config"
    
    if [[ -f "$HOME/.gitconfig" ]]; then
        if ! $DRY_RUN; then
            cp "$HOME/.gitconfig" "$dest_dir/config/"
        fi
        print_status "Git config" "ok"
    else
        print_status "Git config not found" "skip"
    fi
}

backup_ssh() {
    local dest_dir="$1"
    
    if [[ ! -d "$HOME/.ssh" ]]; then
        print_status "SSH directory not found" "skip"
        return 0
    fi
    
    mkdir -p "$dest_dir/ssh"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would backup SSH keys" "info"
        return 0
    fi
    
    tar -czf "$dest_dir/ssh/ssh_backup.tar.gz" \
        -C "$HOME" .ssh 2>/dev/null
    
    print_status "SSH keys" "ok"
}

backup_conda() {
    local dest_dir="$1"
    
    # Find conda installation
    local conda_path=""
    local conda_paths=(
        "$HOME/miniconda3"
        "$HOME/anaconda3"
        "$HOME/miniforge3"
        "/opt/homebrew/Caskroom/miniconda/base"
        "/usr/local/miniconda3"
    )
    
    for path in "${conda_paths[@]}"; do
        if [[ -f "$path/bin/conda" ]]; then
            conda_path="$path"
            break
        fi
    done
    
    if [[ -z "$conda_path" ]]; then
        print_status "Conda not found" "skip"
        return 0
    fi
    
    mkdir -p "$dest_dir/conda"
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would backup Conda environments" "info"
        return 0
    fi
    
    # Get list of environments
    local envs
    envs=$("$conda_path/bin/conda" env list 2>/dev/null | grep -v "^#" | grep -v "^$" | awk '{print $1}' | grep -v "^\*$")
    
    local count=0
    for env in $envs; do
        if [[ -n "$env" ]] && [[ "$env" =~ ^[a-zA-Z0-9_-]+$ ]]; then
            "$conda_path/bin/conda" env export -n "$env" > "$dest_dir/conda/${env}.yml" 2>/dev/null || true
            ((count++))
        fi
    done
    
    print_status "Conda environments ($count)" "ok"
}

backup_history() {
    local dest_dir="$1"
    
    mkdir -p "$dest_dir/config/history"
    
    local found=0
    
    if ! $DRY_RUN; then
        # Fish history
        if [[ -f "$HOME/.local/share/fish/fish_history" ]]; then
            cp "$HOME/.local/share/fish/fish_history" "$dest_dir/config/history/"
            ((found++))
        fi
        
        # Bash history
        if [[ -f "$HOME/.bash_history" ]]; then
            cp "$HOME/.bash_history" "$dest_dir/config/history/"
            ((found++))
        fi
        
        # Zsh history
        if [[ -f "$HOME/.zsh_history" ]]; then
            cp "$HOME/.zsh_history" "$dest_dir/config/history/"
            ((found++))
        fi
    fi
    
    if [[ $found -gt 0 ]] || $DRY_RUN; then
        print_status "Shell history" "ok"
    else
        print_status "Shell history not found" "skip"
    fi
}

backup_cloud_creds() {
    local dest_dir="$1"
    
    mkdir -p "$dest_dir/config/cloud"
    
    local found=0
    
    if ! $DRY_RUN; then
        # AWS
        if [[ -d "$HOME/.aws" ]]; then
            tar -czf "$dest_dir/config/cloud/aws.tar.gz" -C "$HOME" .aws 2>/dev/null
            ((found++))
        fi
        
        # Azure
        if [[ -d "$HOME/.azure" ]]; then
            tar -czf "$dest_dir/config/cloud/azure.tar.gz" -C "$HOME" .azure 2>/dev/null
            ((found++))
        fi
        
        # GCP
        if [[ -d "$HOME/.config/gcloud" ]]; then
            tar -czf "$dest_dir/config/cloud/gcloud.tar.gz" -C "$HOME/.config" gcloud 2>/dev/null
            ((found++))
        fi
    fi
    
    if [[ $found -gt 0 ]] || $DRY_RUN; then
        print_status "Cloud credentials ($found)" "ok"
    else
        print_status "Cloud credentials not found" "skip"
    fi
}

create_manifest() {
    local dest_dir="$1"
    local backup_name="$2"
    local backup_type="$3"
    local shells="$4"
    local os="$5"
    local pm="$6"
    
    local default_shell
    default_shell=$(detect_shell)
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would create manifest" "info"
        return 0
    fi
    
    cat > "$dest_dir/$MANIFEST_FILE" << EOF
{
    "version": "$VERSION",
    "created": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
    "backup_name": "$backup_name",
    "backup_type": "$backup_type",
    "source": {
        "user": "$(whoami)",
        "hostname": "$(hostname)",
        "os": "$os",
        "arch": "$(detect_arch)",
        "package_manager": "$pm",
        "default_shell": "$default_shell"
    },
    "shells": [$shells],
    "checksum": ""
}
EOF
    
    # Calculate checksum
    local checksum
    if command -v sha256sum &>/dev/null; then
        checksum=$(find "$dest_dir" -type f ! -name "$MANIFEST_FILE" -exec sha256sum {} \; | sort | sha256sum | cut -d' ' -f1)
    elif command -v shasum &>/dev/null; then
        checksum=$(find "$dest_dir" -type f ! -name "$MANIFEST_FILE" -exec shasum -a 256 {} \; | sort | shasum -a 256 | cut -d' ' -f1)
    else
        checksum="unavailable"
    fi
    
    # Update manifest with checksum
    if command -v jq &>/dev/null; then
        jq --arg cs "$checksum" '.checksum = $cs' "$dest_dir/$MANIFEST_FILE" > "$dest_dir/${MANIFEST_FILE}.tmp"
        mv "$dest_dir/${MANIFEST_FILE}.tmp" "$dest_dir/$MANIFEST_FILE"
    else
        sed -i.bak "s/\"checksum\": \"\"/\"checksum\": \"$checksum\"/" "$dest_dir/$MANIFEST_FILE" 2>/dev/null || true
        rm -f "$dest_dir/${MANIFEST_FILE}.bak"
    fi
    
    print_status "Manifest created" "ok"
}

#===============================================================================
# Restore Functions
#===============================================================================

restore_fish() {
    local src_dir="$1"
    
    if [[ ! -f "$src_dir/shells/fish/fish_config.tar.gz" ]]; then
        print_status "Fish config not in backup" "skip"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore Fish config" "info"
        return 0
    fi
    
    mkdir -p "$HOME/.config"
    tar -xzf "$src_dir/shells/fish/fish_config.tar.gz" -C "$HOME/.config" 2>/dev/null
    
    print_status "Fish config" "ok"
}

restore_bash() {
    local src_dir="$1"
    local files=(".bashrc" ".bash_aliases" ".bash_profile" ".profile" ".bash_logout")
    local found=0
    
    for file in "${files[@]}"; do
        if [[ -f "$src_dir/shells/bash/$file" ]]; then
            if ! $DRY_RUN; then
                cp "$src_dir/shells/bash/$file" "$HOME/"
            fi
            ((found++))
        fi
    done
    
    if [[ $found -gt 0 ]]; then
        print_status "Bash config ($found files)" "ok"
    else
        print_status "Bash config not in backup" "skip"
    fi
}

restore_zsh() {
    local src_dir="$1"
    local files=(".zshrc" ".zprofile" ".zshenv" ".zlogin" ".zlogout")
    local found=0
    
    for file in "${files[@]}"; do
        if [[ -f "$src_dir/shells/zsh/$file" ]]; then
            if ! $DRY_RUN; then
                cp "$src_dir/shells/zsh/$file" "$HOME/"
            fi
            ((found++))
        fi
    done
    
    # Restore Oh-My-Zsh if present
    if [[ -f "$src_dir/shells/zsh/ohmyzsh.tar.gz" ]]; then
        if ! $DRY_RUN; then
            tar -xzf "$src_dir/shells/zsh/ohmyzsh.tar.gz" -C "$HOME" 2>/dev/null
        fi
        print_status "Zsh config + Oh-My-Zsh" "ok"
    elif [[ $found -gt 0 ]]; then
        print_status "Zsh config ($found files)" "ok"
    else
        print_status "Zsh config not in backup" "skip"
    fi
}

restore_starship() {
    local src_dir="$1"
    
    if [[ ! -f "$src_dir/config/starship.toml" ]]; then
        print_status "Starship config not in backup" "skip"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore Starship config" "info"
        return 0
    fi
    
    mkdir -p "$HOME/.config"
    cp "$src_dir/config/starship.toml" "$HOME/.config/"
    
    print_status "Starship config" "ok"
}

restore_git_config() {
    local src_dir="$1"
    
    if [[ ! -f "$src_dir/config/.gitconfig" ]]; then
        print_status "Git config not in backup" "skip"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore Git config" "info"
        return 0
    fi
    
    cp "$src_dir/config/.gitconfig" "$HOME/"
    
    print_status "Git config" "ok"
}

restore_ssh() {
    local src_dir="$1"
    
    if [[ ! -f "$src_dir/ssh/ssh_backup.tar.gz" ]]; then
        return 1
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore SSH keys" "info"
        return 0
    fi
    
    tar -xzf "$src_dir/ssh/ssh_backup.tar.gz" -C "$HOME" 2>/dev/null
    chmod 700 "$HOME/.ssh"
    chmod 600 "$HOME/.ssh/"* 2>/dev/null || true
    chmod 644 "$HOME/.ssh/"*.pub 2>/dev/null || true
    
    print_status "SSH keys" "ok"
}

restore_conda() {
    local src_dir="$1"
    local os="$2"
    local arch="$3"
    
    if [[ ! -d "$src_dir/conda" ]] || ! ls "$src_dir/conda/"*.yml &>/dev/null; then
        print_status "Conda environments not in backup" "skip"
        return 0
    fi
    
    # Install Miniconda if not present
    if [[ ! -d "$HOME/miniconda3" ]]; then
        echo ""
        echo -e "  ${GRAY}Installing Miniconda...${NC}"
        
        if ! $DRY_RUN; then
            local installer_url
            case "$os" in
                macos)
                    if [[ "$arch" == "arm64" ]]; then
                        installer_url="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh"
                    else
                        installer_url="https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh"
                    fi
                    ;;
                *)
                    installer_url="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
                    ;;
            esac
            
            curl -sL "$installer_url" -o /tmp/miniconda.sh
            bash /tmp/miniconda.sh -b -p "$HOME/miniconda3" >/dev/null 2>&1
            rm /tmp/miniconda.sh
        fi
        
        print_status "Miniconda installed" "ok"
    fi
    
    # Initialize conda for shells
    if ! $DRY_RUN; then
        "$HOME/miniconda3/bin/conda" init bash >/dev/null 2>&1 || true
        "$HOME/miniconda3/bin/conda" init fish >/dev/null 2>&1 || true
        "$HOME/miniconda3/bin/conda" init zsh >/dev/null 2>&1 || true
    fi
    
    # Restore environments
    local count=0
    for yml in "$src_dir/conda/"*.yml; do
        if [[ -f "$yml" ]]; then
            local env_name
            env_name=$(basename "$yml" .yml)
            if [[ "$env_name" != "base" ]]; then
                if ! $DRY_RUN; then
                    "$HOME/miniconda3/bin/conda" env create -f "$yml" -n "$env_name" >/dev/null 2>&1 || true
                fi
                ((count++))
            fi
        fi
    done
    
    print_status "Conda environments ($count)" "ok"
}

restore_history() {
    local src_dir="$1"
    
    if [[ ! -d "$src_dir/config/history" ]]; then
        print_status "Shell history not in backup" "skip"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore shell history" "info"
        return 0
    fi
    
    # Fish history
    if [[ -f "$src_dir/config/history/fish_history" ]]; then
        mkdir -p "$HOME/.local/share/fish"
        cp "$src_dir/config/history/fish_history" "$HOME/.local/share/fish/"
    fi
    
    # Bash history
    if [[ -f "$src_dir/config/history/.bash_history" ]]; then
        cp "$src_dir/config/history/.bash_history" "$HOME/"
    fi
    
    # Zsh history
    if [[ -f "$src_dir/config/history/.zsh_history" ]]; then
        cp "$src_dir/config/history/.zsh_history" "$HOME/"
    fi
    
    print_status "Shell history" "ok"
}

restore_cloud_creds() {
    local src_dir="$1"
    
    if [[ ! -d "$src_dir/config/cloud" ]]; then
        print_status "Cloud credentials not in backup" "skip"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would restore cloud credentials" "info"
        return 0
    fi
    
    local found=0
    
    if [[ -f "$src_dir/config/cloud/aws.tar.gz" ]]; then
        tar -xzf "$src_dir/config/cloud/aws.tar.gz" -C "$HOME" 2>/dev/null
        ((found++))
    fi
    
    if [[ -f "$src_dir/config/cloud/azure.tar.gz" ]]; then
        tar -xzf "$src_dir/config/cloud/azure.tar.gz" -C "$HOME" 2>/dev/null
        ((found++))
    fi
    
    if [[ -f "$src_dir/config/cloud/gcloud.tar.gz" ]]; then
        mkdir -p "$HOME/.config"
        tar -xzf "$src_dir/config/cloud/gcloud.tar.gz" -C "$HOME/.config" 2>/dev/null
        ((found++))
    fi
    
    if [[ $found -gt 0 ]]; then
        print_status "Cloud credentials ($found)" "ok"
    fi
}

install_shell() {
    local shell="$1"
    local pm="$2"
    
    if command -v "$shell" &>/dev/null; then
        print_status "$shell (already installed)" "ok"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would install $shell" "info"
        return 0
    fi
    
    case "$shell" in
        fish)
            case "$pm" in
                apt)
                    sudo apt-add-repository -y ppa:fish-shell/release-3 >/dev/null 2>&1 || true
                    sudo apt update >/dev/null 2>&1
                    sudo apt install -y fish >/dev/null 2>&1
                    ;;
                brew)
                    brew install fish >/dev/null 2>&1
                    ;;
                dnf)
                    sudo dnf install -y fish >/dev/null 2>&1
                    ;;
                pacman)
                    sudo pacman -S --noconfirm fish >/dev/null 2>&1
                    ;;
            esac
            ;;
        zsh)
            case "$pm" in
                apt)
                    sudo apt install -y zsh >/dev/null 2>&1
                    ;;
                brew)
                    brew install zsh >/dev/null 2>&1
                    ;;
                dnf)
                    sudo dnf install -y zsh >/dev/null 2>&1
                    ;;
                pacman)
                    sudo pacman -S --noconfirm zsh >/dev/null 2>&1
                    ;;
            esac
            ;;
    esac
    
    if command -v "$shell" &>/dev/null; then
        print_status "$shell" "ok"
    else
        print_status "$shell installation failed" "error"
    fi
}

install_starship() {
    local pm="$1"
    
    if command -v starship &>/dev/null; then
        print_status "Starship (already installed)" "ok"
        return 0
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would install Starship" "info"
        return 0
    fi
    
    curl -sS https://starship.rs/install.sh | sh -s -- -y >/dev/null 2>&1
    
    if command -v starship &>/dev/null; then
        print_status "Starship" "ok"
    else
        print_status "Starship installation failed" "warn"
    fi
}

set_default_shell() {
    local shell="$1"
    
    local shell_path
    shell_path=$(which "$shell" 2>/dev/null)
    
    if [[ -z "$shell_path" ]]; then
        print_status "Cannot find $shell path" "error"
        return 1
    fi
    
    if $DRY_RUN; then
        print_status "[DRY RUN] Would set default shell to $shell" "info"
        return 0
    fi
    
    # Add to /etc/shells if not present
    if ! grep -q "$shell_path" /etc/shells 2>/dev/null; then
        echo "$shell_path" | sudo tee -a /etc/shells >/dev/null 2>&1 || true
    fi
    
    # Change shell
    if chsh -s "$shell_path" 2>/dev/null; then
        print_status "Default shell set to $shell" "ok"
    elif sudo chsh -s "$shell_path" "$(whoami)" 2>/dev/null; then
        print_status "Default shell set to $shell" "ok"
    else
        print_status "Could not set default shell (try manually: chsh -s $shell_path)" "warn"
    fi
}

#===============================================================================
# Main Commands
#===============================================================================

do_backup() {
    print_banner
    print_header "Backup Shell Environment"
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Detect system
    local os arch pm
    os=$(detect_os)
    arch=$(detect_arch)
    pm=$(detect_package_manager "$os")
    
    echo ""
    print_status "Operating System: $os ($arch)" "info"
    print_status "Package Manager: $pm" "info"
    
    # Get repository URL
    print_section "Backup Repository"
    echo ""
    echo -e "  Enter the Git repository URL where backups will be stored."
    echo -e "  ${GRAY}Example: git@github.com:username/my-shell-backup.git${NC}"
    echo ""
    
    local repo_url
    repo_url=$(read_input "Repository URL")
    
    if [[ -z "$repo_url" ]]; then
        print_error "Repository URL is required"
        exit 1
    fi
    
    # Generate backup name
    local hostname default_shell date_stamp default_name
    hostname=$(hostname | tr '[:upper:]' '[:lower:]' | tr -cd '[:alnum:]-')
    default_shell=$(detect_shell)
    date_stamp=$(date '+%Y%m%d')
    default_name="${default_shell}-${hostname}-${date_stamp}"
    
    echo ""
    echo -e "  ${GRAY}Suggested name: $default_name${NC}"
    echo -e "  ${GRAY}Format: {shell}-{hostname}-{date}${NC}"
    
    local backup_name
    backup_name=$(read_input "Backup name" "$default_name")
    
    # Backup type
    print_section "Backup Type"
    echo ""
    echo -e "  What type of backup do you want to create?"
    
    local type_choice
    type_choice=$(read_choice "Select type" \
        "Full backup (personal use - includes sensitive data)" \
        "Shareable backup (safe to share - excludes sensitive data)")
    
    local is_shareable=false
    [[ "$type_choice" == "2" ]] && is_shareable=true
    
    # Data selection
    local include_ssh=false
    local include_git_config=false
    local include_history=false
    local include_cloud_creds=false
    local include_conda=true
    
    if $is_shareable; then
        print_section "Shareable Backup"
        echo ""
        echo -e "  ${YELLOW}The following will be EXCLUDED:${NC}"
        print_item "SSH keys"
        print_item "Git config (name/email)"
        print_item "Shell history"
        print_item "Cloud credentials"
        echo ""
        echo -e "  ${GREEN}The following will be INCLUDED:${NC}"
        print_item "Shell configurations"
        print_item "Starship config"
        print_item "Package list"
        echo ""
        include_conda=$(read_yes_no "Include Conda environments?" "y") && include_conda=true || include_conda=false
    else
        print_section "Select Data to Backup"
        echo ""
        read_yes_no "Include SSH keys?" "y" && include_ssh=true
        read_yes_no "Include Git config?" "y" && include_git_config=true
        read_yes_no "Include shell history?" "n" && include_history=true
        read_yes_no "Include cloud credentials (AWS/Azure/GCP)?" "n" && include_cloud_creds=true
        read_yes_no "Include Conda environments?" "y" && include_conda=true
    fi
    
    # Shell selection
    print_section "Shell Selection"
    echo ""
    echo -e "  Detected shells:"
    
    local shells_to_backup=()
    local shell_json=""
    
    if command -v fish &>/dev/null; then
        local mark=""
        [[ "$default_shell" == "fish" ]] && mark=" ${GREEN}(default)${NC}"
        echo -e "      ${GRAY}•${NC} Fish$mark"
        if read_yes_no "    Backup Fish?" "y"; then
            shells_to_backup+=("fish")
            shell_json="${shell_json}\"fish\","
        fi
    fi
    
    if command -v bash &>/dev/null; then
        local mark=""
        [[ "$default_shell" == "bash" ]] && mark=" ${GREEN}(default)${NC}"
        echo -e "      ${GRAY}•${NC} Bash$mark"
        if read_yes_no "    Backup Bash?" "y"; then
            shells_to_backup+=("bash")
            shell_json="${shell_json}\"bash\","
        fi
    fi
    
    if command -v zsh &>/dev/null; then
        local mark=""
        [[ "$default_shell" == "zsh" ]] && mark=" ${GREEN}(default)${NC}"
        local omz=""
        [[ -d "$HOME/.oh-my-zsh" ]] && omz=" + Oh-My-Zsh"
        echo -e "      ${GRAY}•${NC} Zsh${omz}$mark"
        if read_yes_no "    Backup Zsh?" "y"; then
            shells_to_backup+=("zsh")
            shell_json="${shell_json}\"zsh\","
        fi
    fi
    
    # Remove trailing comma
    shell_json="${shell_json%,}"
    
    # Create temp directory
    mkdir -p "$TEMP_DIR"
    
    # Perform backup
    print_section "Creating Backup"
    echo ""
    
    local backup_dir="$TEMP_DIR/backup/$backup_name"
    mkdir -p "$backup_dir"/{shells,packages,config,conda,ssh}
    
    # Backup shells
    for shell in "${shells_to_backup[@]}"; do
        case "$shell" in
            fish) backup_fish "$backup_dir" ;;
            bash) backup_bash "$backup_dir" ;;
            zsh)  backup_zsh "$backup_dir" ;;
        esac
    done
    
    # Backup other components
    backup_packages "$backup_dir" "$pm"
    backup_starship "$backup_dir"
    
    if $include_git_config; then
        backup_git_config "$backup_dir"
    else
        print_status "Git config (excluded)" "skip"
    fi
    
    if $include_ssh; then
        backup_ssh "$backup_dir"
    else
        print_status "SSH keys (excluded)" "skip"
    fi
    
    if $include_conda; then
        backup_conda "$backup_dir"
    else
        print_status "Conda environments (excluded)" "skip"
    fi
    
    if $include_history; then
        backup_history "$backup_dir"
    else
        print_status "Shell history (excluded)" "skip"
    fi
    
    if $include_cloud_creds; then
        backup_cloud_creds "$backup_dir"
    else
        print_status "Cloud credentials (excluded)" "skip"
    fi
    
    # Create manifest
    local backup_type="full"
    $is_shareable && backup_type="shareable"
    create_manifest "$backup_dir" "$backup_name" "$backup_type" "$shell_json" "$os" "$pm"
    
    # Push to repository
    print_section "Pushing to Repository"
    echo ""
    
    local git_dir="$TEMP_DIR/git"
    
    echo -e "  ${GRAY}Cloning repository...${NC}"
    if ! git clone --depth 1 "$repo_url" "$git_dir" 2>/dev/null; then
        # Repo might be empty
        mkdir -p "$git_dir"
        cd "$git_dir"
        git init >/dev/null 2>&1
        git remote add origin "$repo_url"
    fi
    
    # Copy backup to repo
    mkdir -p "$git_dir/backups"
    cp -r "$backup_dir" "$git_dir/backups/"
    
    # Push
    cd "$git_dir"
    
    echo -e "  ${GRAY}Pushing backup...${NC}"
    if push_to_repo "$git_dir" "Backup: $backup_name"; then
        print_status "Pushed to repository" "ok"
    else
        print_error "Failed to push to repository"
        echo ""
        echo -e "  ${YELLOW}Your backup is saved locally at:${NC}"
        echo -e "  ${CYAN}$backup_dir${NC}"
        exit 1
    fi
    
    # Success
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║   ${BOLD}BACKUP COMPLETE!${NC}${GREEN}                                         ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║${NC}   Backup: ${CYAN}$backup_name${NC}"
    echo -e "${GREEN}║${NC}   Repository: ${CYAN}$repo_url${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║${NC}   To restore on another machine:                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}   ${GRAY}bash <(curl -sL $GITHUB_REPO/main/shellpack.sh) restore${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

do_restore() {
    print_banner
    print_header "Restore Shell Environment"
    
    # Check dependencies
    if ! check_dependencies; then
        exit 1
    fi
    
    # Detect system
    local os arch pm
    os=$(detect_os)
    arch=$(detect_arch)
    pm=$(detect_package_manager "$os")
    
    echo ""
    print_status "Operating System: $os ($arch)" "info"
    print_status "Package Manager: $pm" "info"
    
    # Get repository URL
    print_section "Backup Repository"
    echo ""
    echo -e "  Enter the Git repository URL where your backups are stored."
    echo ""
    
    local repo_url
    repo_url=$(read_input "Repository URL")
    
    if [[ -z "$repo_url" ]]; then
        print_error "Repository URL is required"
        exit 1
    fi
    
    # Clone repository
    print_section "Fetching Backups"
    echo ""
    
    mkdir -p "$TEMP_DIR"
    local git_dir="$TEMP_DIR/git"
    
    echo -e "  ${GRAY}Cloning repository...${NC}"
    if ! git clone --depth 1 "$repo_url" "$git_dir" 2>/dev/null; then
        print_error "Failed to clone repository"
        exit 1
    fi
    
    # List available backups
    local backups=()
    if [[ -d "$git_dir/backups" ]]; then
        while IFS= read -r -d '' dir; do
            backups+=("$(basename "$dir")")
        done < <(find "$git_dir/backups" -mindepth 1 -maxdepth 1 -type d -print0 | sort -z)
    fi
    
    if [[ ${#backups[@]} -eq 0 ]]; then
        print_error "No backups found in repository"
        exit 1
    fi
    
    print_status "Found ${#backups[@]} backup(s)" "ok"
    
    # Select backup
    print_section "Select Backup"
    echo ""
    
    local backup_choice
    backup_choice=$(read_choice "Choose backup to restore" "${backups[@]}")
    local backup_name="${backups[$((backup_choice-1))]}"
    local backup_dir="$git_dir/backups/$backup_name"
    
    print_status "Selected: $backup_name" "info"
    
    # Show backup info
    if [[ -f "$backup_dir/$MANIFEST_FILE" ]]; then
        echo ""
        echo -e "  ${GRAY}Backup details:${NC}"
        
        local created source_os source_host
        if command -v jq &>/dev/null; then
            created=$(jq -r '.created // "unknown"' "$backup_dir/$MANIFEST_FILE")
            source_os=$(jq -r '.source.os // "unknown"' "$backup_dir/$MANIFEST_FILE")
            source_host=$(jq -r '.source.hostname // "unknown"' "$backup_dir/$MANIFEST_FILE")
        else
            created=$(grep -o '"created": "[^"]*"' "$backup_dir/$MANIFEST_FILE" | cut -d'"' -f4)
            source_os=$(grep -o '"os": "[^"]*"' "$backup_dir/$MANIFEST_FILE" | cut -d'"' -f4)
            source_host=$(grep -o '"hostname": "[^"]*"' "$backup_dir/$MANIFEST_FILE" | cut -d'"' -f4)
        fi
        
        print_item "Created: $created"
        print_item "Source: $source_host ($source_os)"
    fi
    
    echo ""
    if ! read_yes_no "Continue with restore?" "y"; then
        echo -e "  ${YELLOW}Restore cancelled.${NC}"
        exit 0
    fi
    
    # SSH key handling
    print_section "SSH Keys"
    echo ""
    
    if [[ -f "$backup_dir/ssh/ssh_backup.tar.gz" ]]; then
        echo -e "  Found SSH keys in backup."
        echo ""
        
        local ssh_choice
        ssh_choice=$(read_choice "What do you want to do?" \
            "Restore SSH keys from backup" \
            "Generate new SSH keys" \
            "Skip SSH setup")
        
        case "$ssh_choice" in
            1)
                restore_ssh "$backup_dir"
                ;;
            2)
                local email
                email=$(read_input "Enter email for SSH key")
                if [[ -n "$email" ]]; then
                    mkdir -p "$HOME/.ssh"
                    ssh-keygen -t ed25519 -C "$email" -f "$HOME/.ssh/id_ed25519" -N "" 2>/dev/null
                    print_status "SSH key generated" "ok"
                    echo ""
                    echo -e "  ${CYAN}Your new public key:${NC}"
                    echo -e "  ${GRAY}$(cat "$HOME/.ssh/id_ed25519.pub")${NC}"
                    echo ""
                    echo -e "  ${YELLOW}Add this key to GitHub/GitLab to enable SSH access.${NC}"
                fi
                ;;
            3)
                print_status "SSH setup skipped" "skip"
                ;;
        esac
    else
        echo -e "  No SSH keys in backup."
        if read_yes_no "Generate new SSH keys?" "y"; then
            local email
            email=$(read_input "Enter email for SSH key")
            if [[ -n "$email" ]]; then
                mkdir -p "$HOME/.ssh"
                ssh-keygen -t ed25519 -C "$email" -f "$HOME/.ssh/id_ed25519" -N "" 2>/dev/null
                print_status "SSH key generated" "ok"
                echo ""
                echo -e "  ${CYAN}Your new public key:${NC}"
                echo -e "  ${GRAY}$(cat "$HOME/.ssh/id_ed25519.pub")${NC}"
            fi
        fi
    fi
    
    # Shell selection
    print_section "Shell Selection"
    echo ""
    
    local available_shells=()
    [[ -d "$backup_dir/shells/fish" ]] && available_shells+=("fish")
    [[ -d "$backup_dir/shells/bash" ]] && available_shells+=("bash")
    [[ -d "$backup_dir/shells/zsh" ]] && available_shells+=("zsh")
    
    if [[ ${#available_shells[@]} -eq 0 ]]; then
        available_shells=("bash")
    fi
    
    echo -e "  Shells available in backup:"
    for s in "${available_shells[@]}"; do
        print_item "$s"
    done
    echo ""
    
    local shell_choice default_shell
    shell_choice=$(read_choice "Select default shell" "${available_shells[@]}")
    default_shell="${available_shells[$((shell_choice-1))]}"
    
    # Install components
    print_section "Installing Components"
    echo ""
    
    # Install shells
    for shell in "${available_shells[@]}"; do
        install_shell "$shell" "$pm"
    done
    
    # Install Starship
    install_starship "$pm"
    
    # Restore configurations
    print_section "Restoring Configurations"
    echo ""
    
    for shell in "${available_shells[@]}"; do
        case "$shell" in
            fish) restore_fish "$backup_dir" ;;
            bash) restore_bash "$backup_dir" ;;
            zsh)  restore_zsh "$backup_dir" ;;
        esac
    done
    
    restore_starship "$backup_dir"
    restore_git_config "$backup_dir"
    restore_conda "$backup_dir" "$os" "$arch"
    restore_history "$backup_dir"
    restore_cloud_creds "$backup_dir"
    
    # Set default shell
    print_section "Setting Default Shell"
    echo ""
    set_default_shell "$default_shell"
    
    # Success
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║   ${BOLD}RESTORE COMPLETE!${NC}${GREEN}                                        ║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║${NC}   Your shell environment has been restored.                 ${GREEN}║${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}║${NC}   ${YELLOW}Restart your terminal or run:${NC}                            ${GREEN}║${NC}"
    echo -e "${GREEN}║${NC}   ${CYAN}exec $default_shell${NC}"
    echo -e "${GREEN}║                                                              ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

show_help() {
    print_banner
    
    cat << EOF
${BOLD}USAGE${NC}
    $SCRIPT_NAME <command> [options]

${BOLD}COMMANDS${NC}
    backup              Backup shell environment to a Git repository
    restore             Restore shell environment from a Git repository
    help, --help, -h    Show this help message
    version, --version  Show version information

${BOLD}OPTIONS${NC}
    --verbose, -v       Enable verbose output
    --dry-run           Show what would be done without making changes

${BOLD}EXAMPLES${NC}
    # Backup your shell environment
    $SCRIPT_NAME backup

    # Restore on a new machine
    $SCRIPT_NAME restore

    # Run directly from GitHub (no installation)
    bash <(curl -sL $GITHUB_REPO/main/shellpack.sh) backup
    bash <(curl -sL $GITHUB_REPO/main/shellpack.sh) restore

${BOLD}WHAT GETS BACKED UP${NC}
    • Shell configs (Fish, Bash, Zsh, Oh-My-Zsh)
    • Package lists (apt, brew, dnf, pacman)
    • Conda/Miniconda environments
    • Starship prompt configuration
    • Git configuration
    • SSH keys (optional)
    • Cloud credentials (optional)
    • Shell history (optional)

${BOLD}SUPPORTED PLATFORMS${NC}
    • macOS (Intel & Apple Silicon)
    • Linux (Ubuntu, Debian, Fedora, Arch, etc.)
    • Windows (WSL/WSL2)

${BOLD}MORE INFO${NC}
    Repository: $GITHUB_REPO
    Version:    $VERSION

EOF
}

show_version() {
    echo "$SCRIPT_NAME version $VERSION"
}

#===============================================================================
# Cleanup
#===============================================================================

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

#===============================================================================
# Main Entry Point
#===============================================================================

main() {
    # Parse global options
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --verbose|-v)
                VERBOSE=true
                shift
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --help|-h|help)
                show_help
                exit 0
                ;;
            --version|version)
                show_version
                exit 0
                ;;
            backup)
                shift
                do_backup "$@"
                exit 0
                ;;
            restore)
                shift
                do_restore "$@"
                exit 0
                ;;
            *)
                print_error "Unknown command: $1"
                echo ""
                echo "Run '$SCRIPT_NAME --help' for usage."
                exit 1
                ;;
        esac
    done
    
    # No command provided
    show_help
}

main "$@"
