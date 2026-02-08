#Requires -Version 5.1
<#
.SYNOPSIS
    ShellPack - Cross-Platform Shell Environment Backup & Restore (Windows)

.DESCRIPTION
    Windows PowerShell wrapper for ShellPack.
    Handles WSL instance creation and calls the bash script for backup/restore.

.PARAMETER Action
    The action to perform: backup, restore, help, or version

.PARAMETER Verbose
    Enable verbose output

.PARAMETER DryRun
    Show what would be done without making changes

.EXAMPLE
    # Run from GitHub (interactive menu)
    iex (irm https://raw.githubusercontent.com/MoxForge/shellpack/main/shellpack.ps1)

    # Backup
    .\shellpack.ps1 backup

    # Restore
    .\shellpack.ps1 restore

.LINK
    https://github.com/MoxForge/shellpack

.NOTES
    Version: 1.0.0
    Author: MoxForge
    License: MIT
#>

[CmdletBinding()]
param(
    [Parameter(Position=0)]
    [ValidateSet('backup', 'restore', 'help', 'version', '')]
    [string]$Action = '',
    
    [switch]$DryRun
)

#===============================================================================
# Configuration
#===============================================================================

$Script:VERSION = "1.0.0"
$Script:SCRIPT_NAME = "shellpack"
$Script:GITHUB_REPO = "https://github.com/MoxForge/shellpack"
$Script:GITHUB_RAW = "https://raw.githubusercontent.com/MoxForge/shellpack/main"

#===============================================================================
# Output Functions
#===============================================================================

function Write-Banner {
    Write-Host ""
    Write-Host "  ┌──────────────────────────────────────────────────────────────┐" -ForegroundColor Cyan
    Write-Host "  │  ShellPack v$Script:VERSION                                          │" -ForegroundColor Cyan
    Write-Host "  │  Cross-Platform Shell Environment Backup & Restore          │" -ForegroundColor Cyan
    Write-Host "  └──────────────────────────────────────────────────────────────┘" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Header {
    param([string]$Title)
    Write-Host ""
    Write-Host "  ══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host "    $Title" -ForegroundColor Cyan
    Write-Host "  ══════════════════════════════════════════════════════════════" -ForegroundColor Cyan
    Write-Host ""
}

function Write-Section {
    param([string]$Title)
    Write-Host ""
    Write-Host "  ──────────────────────────────────────────────────────────────" -ForegroundColor Yellow
    Write-Host "    $Title" -ForegroundColor Yellow
    Write-Host "  ──────────────────────────────────────────────────────────────" -ForegroundColor Yellow
}

function Write-Status {
    param(
        [string]$Message,
        [ValidateSet('ok', 'error', 'warn', 'skip', 'info')]
        [string]$Status = 'info'
    )
    
    $icon = switch ($Status) {
        'ok'    { "[✓]"; $color = "Green" }
        'error' { "[✗]"; $color = "Red" }
        'warn'  { "[!]"; $color = "Yellow" }
        'skip'  { "[→]"; $color = "DarkGray" }
        'info'  { "[•]"; $color = "Blue" }
    }
    
    Write-Host "    $icon $Message" -ForegroundColor $color
}

function Write-Item {
    param([string]$Message)
    Write-Host "        • $Message" -ForegroundColor White
}

function Read-Input {
    param(
        [string]$Prompt,
        [string]$Default = ""
    )
    
    if ($Default) {
        Write-Host -NoNewline "    $Prompt " -ForegroundColor Cyan
        Write-Host -NoNewline "[$Default]" -ForegroundColor DarkGray
        Write-Host -NoNewline ": " -ForegroundColor Cyan
    } else {
        Write-Host -NoNewline "    ${Prompt}: " -ForegroundColor Cyan
    }
    
    $result = Read-Host
    
    if ([string]::IsNullOrWhiteSpace($result)) {
        return $Default
    }
    return $result
}

function Read-YesNo {
    param(
        [string]$Prompt,
        [bool]$Default = $true
    )
    
    $hint = if ($Default) { "Y/n" } else { "y/N" }
    Write-Host -NoNewline "    $Prompt " -ForegroundColor Cyan
    Write-Host -NoNewline "[$hint]" -ForegroundColor DarkGray
    Write-Host -NoNewline ": " -ForegroundColor Cyan
    
    $result = Read-Host
    
    if ([string]::IsNullOrWhiteSpace($result)) {
        return $Default
    }
    return $result.ToLower() -eq 'y'
}

function Read-Choice {
    param(
        [string]$Prompt,
        [string[]]$Options,
        [int]$Default = 1
    )
    
    Write-Host ""
    for ($i = 0; $i -lt $Options.Count; $i++) {
        Write-Host "        [$($i + 1)] $($Options[$i])" -ForegroundColor White
    }
    Write-Host ""
    
    do {
        Write-Host -NoNewline "    $Prompt " -ForegroundColor Cyan
        Write-Host -NoNewline "[$Default]" -ForegroundColor DarkGray
        Write-Host -NoNewline ": " -ForegroundColor Cyan
        
        $input = Read-Host
        
        if ([string]::IsNullOrWhiteSpace($input)) {
            $choice = $Default
        } else {
            $choice = [int]$input
        }
    } while ($choice -lt 1 -or $choice -gt $Options.Count)
    
    return $choice
}

function Read-Password {
    param([string]$Prompt)
    
    Write-Host -NoNewline "    ${Prompt}: " -ForegroundColor Cyan
    $secure = Read-Host -AsSecureString
    $BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    return [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)
}

#===============================================================================
# WSL Functions
#===============================================================================

function Get-WSLDistributions {
    try {
        $output = wsl --list --quiet 2>&1
        $distros = $output | Where-Object { 
            $_ -and 
            $_ -notmatch "^Windows" -and 
            $_ -notmatch "^Usage:" 
        } | ForEach-Object { 
            $_.Trim() -replace '\x00', '' 
        }
        return $distros | Where-Object { $_ }
    } catch {
        return @()
    }
}

function Test-WSLDistributionExists {
    param([string]$Name)
    $distros = Get-WSLDistributions
    return $distros -contains $Name
}

function Test-WSLAvailable {
    try {
        $null = wsl --status 2>&1
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

#===============================================================================
# Dependency Check
#===============================================================================

function Test-Dependencies {
    Write-Section "Checking Dependencies"
    Write-Host ""
    
    $missing = @()
    
    # Check WSL
    if (Test-WSLAvailable) {
        Write-Status "WSL" "ok"
    } else {
        Write-Status "WSL - NOT INSTALLED" "error"
        $missing += "WSL"
    }
    
    # Check Git
    if (Get-Command git -ErrorAction SilentlyContinue) {
        Write-Status "Git" "ok"
    } else {
        # Try common paths
        $gitPaths = @(
            "C:\Program Files\Git\bin\git.exe",
            "C:\Program Files (x86)\Git\bin\git.exe",
            "$env:LOCALAPPDATA\Programs\Git\bin\git.exe"
        )
        $found = $false
        foreach ($path in $gitPaths) {
            if (Test-Path $path) {
                Write-Status "Git (found at $path)" "ok"
                $found = $true
                break
            }
        }
        if (-not $found) {
            Write-Status "Git - NOT INSTALLED" "error"
            $missing += "Git"
        }
    }
    
    # Check curl (usually available in Windows 10+)
    if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
        Write-Status "curl" "ok"
    } else {
        Write-Status "curl - not found (using Invoke-WebRequest)" "warn"
    }
    
    if ($missing.Count -gt 0) {
        Write-Host ""
        Write-Host "    Missing dependencies: $($missing -join ', ')" -ForegroundColor Red
        Write-Host ""
        Write-Host "    Install WSL: " -ForegroundColor Yellow -NoNewline
        Write-Host "wsl --install" -ForegroundColor White
        Write-Host "    Install Git: " -ForegroundColor Yellow -NoNewline
        Write-Host "https://git-scm.com/download/win" -ForegroundColor White
        Write-Host ""
        return $false
    }
    
    return $true
}

#===============================================================================
# Backup Command
#===============================================================================

function Start-Backup {
    Write-Banner
    Write-Header "Backup Shell Environment"
    
    if (-not (Test-Dependencies)) {
        return
    }
    
    # Get available WSL distributions
    $distros = Get-WSLDistributions
    
    if (-not $distros -or $distros.Count -eq 0) {
        Write-Status "No WSL distributions found" "error"
        Write-Host ""
        Write-Host "    Install a WSL distribution first:" -ForegroundColor Yellow
        Write-Host "    wsl --install Ubuntu" -ForegroundColor White
        Write-Host ""
        return
    }
    
    Write-Section "Select WSL Distribution"
    Write-Host ""
    Write-Host "    Available distributions:" -ForegroundColor White
    
    $distroList = @($distros)
    $choice = Read-Choice "Choose distribution to backup" $distroList 1
    $selectedDistro = $distroList[$choice - 1]
    
    Write-Status "Selected: $selectedDistro" "info"
    
    # Run bash script inside WSL
    Write-Section "Running Backup"
    Write-Host ""
    Write-Host "    Executing backup script inside WSL..." -ForegroundColor Gray
    Write-Host ""
    
    wsl -d $selectedDistro -- bash -c "bash <(curl -sL $Script:GITHUB_RAW/shellpack.sh) backup"
}

#===============================================================================
# Restore Command
#===============================================================================

function Start-Restore {
    Write-Banner
    Write-Header "Restore Shell Environment"
    
    if (-not (Test-Dependencies)) {
        return
    }
    
    Write-Section "Restore Options"
    Write-Host ""
    Write-Host "    How do you want to restore?" -ForegroundColor White
    
    $choice = Read-Choice "Select option" @(
        "Create NEW WSL instance (recommended - safe)",
        "Restore to EXISTING WSL instance"
    ) 1
    
    if ($choice -eq 1) {
        Start-RestoreNewWSL
    } else {
        Start-RestoreExistingWSL
    }
}

function Start-RestoreNewWSL {
    # List existing distributions
    Write-Section "Existing WSL Instances"
    Write-Host ""
    
    $existingDistros = Get-WSLDistributions
    if ($existingDistros) {
        foreach ($distro in $existingDistros) {
            Write-Item $distro
        }
    } else {
        Write-Host "        (none)" -ForegroundColor DarkGray
    }
    
    # Get new instance name
    Write-Section "New WSL Instance"
    Write-Host ""
    
    $wslName = ""
    do {
        $wslName = Read-Input "Enter name for new WSL instance"
        
        if ([string]::IsNullOrWhiteSpace($wslName)) {
            Write-Host "        Name is required" -ForegroundColor Yellow
            continue
        }
        
        if (Test-WSLDistributionExists $wslName) {
            Write-Host "        '$wslName' already exists! Choose a different name." -ForegroundColor Yellow
            $wslName = ""
        }
    } while ([string]::IsNullOrWhiteSpace($wslName))
    
    Write-Status "Name '$wslName' is available" "ok"
    
    # Create WSL instance
    Write-Section "Creating WSL Instance"
    Write-Host ""
    Write-Host "    Installing Ubuntu 24.04 as '$wslName'..." -ForegroundColor White
    Write-Host "    This may take a few minutes..." -ForegroundColor Gray
    Write-Host ""
    
    if (-not $DryRun) {
        wsl --install Ubuntu-24.04 --name $wslName 2>&1 | Out-Null
        Start-Sleep -Seconds 3
    }
    
    # User setup
    Write-Section "User Setup"
    Write-Host ""
    
    $username = Read-Input "Enter username"
    
    $password = ""
    $confirmPassword = ""
    do {
        $password = Read-Password "Enter password"
        $confirmPassword = Read-Password "Confirm password"
        
        if ($password -ne $confirmPassword) {
            Write-Host "        Passwords don't match! Try again." -ForegroundColor Yellow
        }
    } while ($password -ne $confirmPassword)
    
    # Create user
    Write-Host ""
    Write-Host "    Creating user..." -ForegroundColor Gray
    
    if (-not $DryRun) {
        wsl -d $wslName -- bash -c "useradd -m -s /bin/bash -G sudo $username 2>/dev/null; echo '${username}:${password}' | chpasswd" 2>&1 | Out-Null
        wsl -d $wslName -- bash -c "echo '[user]' > /etc/wsl.conf; echo 'default=$username' >> /etc/wsl.conf" 2>&1 | Out-Null
        
        # Restart WSL to apply user
        wsl --terminate $wslName 2>&1 | Out-Null
        Start-Sleep -Seconds 2
    }
    
    Write-Status "User '$username' created with sudo privileges" "ok"
    
    # Run restore script
    Write-Section "Running Restore"
    Write-Host ""
    Write-Host "    Executing restore script inside new WSL..." -ForegroundColor Gray
    Write-Host ""
    
    if (-not $DryRun) {
        wsl -d $wslName -u $username -- bash -c "bash <(curl -sL $Script:GITHUB_RAW/shellpack.sh) restore"
    }
    
    # Success
    Write-Host ""
    Write-Host "  ╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "  ║                                                              ║" -ForegroundColor Green
    Write-Host "  ║   RESTORE COMPLETE!                                         ║" -ForegroundColor Green
    Write-Host "  ║                                                              ║" -ForegroundColor Green
    Write-Host "  ║   Your new WSL instance is ready:                           ║" -ForegroundColor Green
    Write-Host "  ║   wsl -d $wslName" -ForegroundColor White
    Write-Host "  ║                                                              ║" -ForegroundColor Green
    Write-Host "  ║   Or set it as default:                                     ║" -ForegroundColor Green
    Write-Host "  ║   wsl --set-default $wslName" -ForegroundColor White
    Write-Host "  ║                                                              ║" -ForegroundColor Green
    Write-Host "  ╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
}

function Start-RestoreExistingWSL {
    $distros = Get-WSLDistributions
    
    if (-not $distros -or $distros.Count -eq 0) {
        Write-Status "No WSL distributions found" "error"
        return
    }
    
    Write-Section "Select WSL Distribution"
    Write-Host ""
    
    $distroList = @($distros)
    $choice = Read-Choice "Choose distribution to restore to" $distroList 1
    $selectedDistro = $distroList[$choice - 1]
    
    Write-Host ""
    Write-Host "    WARNING: This will modify '$selectedDistro'" -ForegroundColor Yellow
    
    if (-not (Read-YesNo "Are you sure?" $false)) {
        Write-Host "    Restore cancelled." -ForegroundColor Yellow
        return
    }
    
    Write-Section "Running Restore"
    Write-Host ""
    
    wsl -d $selectedDistro -- bash -c "bash <(curl -sL $Script:GITHUB_RAW/shellpack.sh) restore"
}

#===============================================================================
# Help & Version
#===============================================================================

function Show-Help {
    Write-Banner
    
    Write-Host "USAGE" -ForegroundColor Yellow
    Write-Host "    .\shellpack.ps1 <command> [options]"
    Write-Host ""
    
    Write-Host "COMMANDS" -ForegroundColor Yellow
    Write-Host "    backup              Backup WSL shell environment"
    Write-Host "    restore             Restore to new or existing WSL"
    Write-Host "    help                Show this help message"
    Write-Host "    version             Show version information"
    Write-Host ""
    
    Write-Host "OPTIONS" -ForegroundColor Yellow
    Write-Host "    -DryRun             Show what would be done"
    Write-Host "    -Verbose            Enable verbose output"
    Write-Host ""
    
    Write-Host "EXAMPLES" -ForegroundColor Yellow
    Write-Host "    # Run from GitHub (interactive menu)"
    Write-Host "    iex (irm $Script:GITHUB_RAW/shellpack.ps1)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    # Backup"
    Write-Host "    .\shellpack.ps1 backup" -ForegroundColor Gray
    Write-Host ""
    Write-Host "    # Restore to new WSL instance"
    Write-Host "    .\shellpack.ps1 restore" -ForegroundColor Gray
    Write-Host ""
    
    Write-Host "MORE INFO" -ForegroundColor Yellow
    Write-Host "    Repository: $Script:GITHUB_REPO"
    Write-Host "    Version:    $Script:VERSION"
    Write-Host ""
}

function Show-Version {
    Write-Host "$Script:SCRIPT_NAME version $Script:VERSION"
}

#===============================================================================
# Interactive Menu
#===============================================================================

function Show-Menu {
    Write-Banner
    
    Write-Host "    What would you like to do?" -ForegroundColor White
    
    $choice = Read-Choice "Select action" @(
        "Backup WSL environment",
        "Restore to WSL",
        "Show help"
    ) 1
    
    switch ($choice) {
        1 { Start-Backup }
        2 { Start-Restore }
        3 { Show-Help }
    }
}

#===============================================================================
# Main Entry Point
#===============================================================================

if ([string]::IsNullOrWhiteSpace($Action)) {
    Show-Menu
} else {
    switch ($Action) {
        'backup'  { Start-Backup }
        'restore' { Start-Restore }
        'help'    { Show-Help }
        'version' { Show-Version }
    }
}
