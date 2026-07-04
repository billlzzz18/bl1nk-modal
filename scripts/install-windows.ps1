<#
.SYNOPSIS
    Bootstrap everything needed to work on bl1nk-modal from a clean Windows machine.

.DESCRIPTION
    Installs uv (Python + venv manager), the Rust toolchain (rustup, needed by
    modal-apps/modal-opencode/engine), the Modal CLI, and pre-commit, then runs
    `uv sync` in every independent Python project directory and installs the
    repo's pre-commit hooks. Safe to re-run — every step is skipped if the tool
    is already on PATH.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\install-windows.ps1
#>

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $RepoRoot

function Test-CommandExists {
    param([string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

Write-Host "== bl1nk-modal Windows setup ==" -ForegroundColor Cyan
Write-Host "Repo root: $RepoRoot"
Write-Host ""

# 1. uv — manages Python versions and per-project venvs; see CLAUDE.md.
if (Test-CommandExists "uv") {
    Write-Host "[1/5] uv already installed ($(uv --version))" -ForegroundColor Green
} else {
    Write-Host "[1/5] Installing uv..." -ForegroundColor Yellow
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 2. Rust toolchain — only modal-apps/modal-opencode/engine needs this.
if (Test-CommandExists "cargo") {
    Write-Host "[2/5] Rust already installed ($(cargo --version))" -ForegroundColor Green
} else {
    Write-Host "[2/5] Installing Rust toolchain via rustup..." -ForegroundColor Yellow
    if (Test-CommandExists "winget") {
        winget install --id Rustlang.Rustup -e --source winget --accept-package-agreements --accept-source-agreements
    } else {
        $rustupInit = Join-Path $env:TEMP "rustup-init.exe"
        Invoke-WebRequest -Uri "https://win.rustup.rs/x86_64" -OutFile $rustupInit
        & $rustupInit -y --default-toolchain stable
        Remove-Item $rustupInit -ErrorAction SilentlyContinue
    }
    $env:Path = "$env:USERPROFILE\.cargo\bin;$env:Path"
}

# 3. Modal CLI
if (Test-CommandExists "modal") {
    Write-Host "[3/5] Modal CLI already installed" -ForegroundColor Green
} else {
    Write-Host "[3/5] Installing Modal CLI..." -ForegroundColor Yellow
    uv tool install modal
}

# 4. pre-commit
if (Test-CommandExists "pre-commit") {
    Write-Host "[4/5] pre-commit already installed" -ForegroundColor Green
} else {
    Write-Host "[4/5] Installing pre-commit..." -ForegroundColor Yellow
    uv tool install pre-commit
}

# 5. Sync every independent Python project (no shared root pyproject.toml/workspace).
Write-Host "[5/5] Syncing Python projects..." -ForegroundColor Yellow
$pythonProjects = @(
    "modal-apps\modal-runner",
    "modal-apps\modal-agy",
    "modal-apps\modal-sandbox",
    "modal-images"
)

foreach ($proj in $pythonProjects) {
    $projPath = Join-Path $RepoRoot $proj
    if (-not (Test-Path $projPath)) {
        Write-Host "  Skipping $proj (not found)" -ForegroundColor DarkYellow
        continue
    }
    Write-Host "  uv sync -> $proj"
    Push-Location $projPath
    try {
        uv sync
    } finally {
        Pop-Location
    }
}

Write-Host ""
Write-Host "Installing pre-commit hooks..." -ForegroundColor Yellow
pre-commit install

Write-Host ""
Write-Host "== Done ==" -ForegroundColor Cyan
Write-Host "Next steps:"
Write-Host "  1. Copy each .env.example to .env (repo root, modal-apps/modal-runner, modal-images, modal-apps/modal-opencode) and fill in values."
Write-Host "  2. Run 'modal setup' to authenticate with Modal, or set MODAL_TOKEN_ID / MODAL_TOKEN_SECRET for headless auth."
Write-Host "  3. cd into a project directory (e.g. modal-apps\modal-runner) and run 'uv run pytest' to confirm the setup works."
