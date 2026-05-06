param(
    [string]$OutputZip = "",
    [switch]$BuildInstallerExe,
    [bool]$IncludeInstallerExe = $true,
    [switch]$IncludeDocsAndImages
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

if (-not $OutputZip) {
    $OutputZip = Join-Path $RepoRoot ("Oathweaver_clean_{0:yyyyMMdd_HHmmss}.zip" -f (Get-Date))
}

$OutputZip = [System.IO.Path]::GetFullPath($OutputZip)
$outputDir = Split-Path $OutputZip -Parent
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$stageRoot = Join-Path $env:TEMP ("oathweaver_clean_stage_{0}" -f ([Guid]::NewGuid().ToString("N")))
New-Item -ItemType Directory -Path $stageRoot -Force | Out-Null

function Copy-RelativePath {
    param([string]$RelativePath)
    $sourcePath = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path $sourcePath)) {
        Write-Warning "Skipping missing path: $RelativePath"
        return
    }
    $destPath = Join-Path $stageRoot $RelativePath
    $item = Get-Item $sourcePath
    if ($item.PSIsContainer) {
        Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
    }
    else {
        $destDir = Split-Path $destPath -Parent
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Copy-Item -Path $sourcePath -Destination $destPath -Force
    }
}

try {
    Write-Host "Creating clean Oathweaver ZIP..." -ForegroundColor Cyan
    Write-Host "Stage: $stageRoot"

    $installerExeRelative = "OathweaverInstaller.exe"
    $installerExePath = Join-Path $RepoRoot $installerExeRelative
    if ($BuildInstallerExe) {
        $buildScript = Join-Path $RepoRoot "build_installer_exe.ps1"
        if (-not (Test-Path $buildScript)) {
            throw "build_installer_exe.ps1 not found at $buildScript"
        }
        Write-Host "Building installer launcher EXE..." -ForegroundColor Cyan
        & powershell -ExecutionPolicy Bypass -File $buildScript -OutputExe $installerExePath -Force
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to build installer EXE."
        }
    }

    $includeDirectories = @(
        "SourceCode",
        "tools",
        "tests",
        "Fonts"
    )
    if ($IncludeDocsAndImages) {
        $includeDirectories += @(
            "docs",
            "Images"
        )
    }
    $includeFiles = @(
        ".gitignore",
        "README.md",
        "INSTALL_GUIDE.md",
        "LICENSE",
        "THIRD_PARTY_NOTICES.md",
        "CONTRIBUTING.md",
        "requirements.txt",
        "start_oathweaver.ps1",
        "start_oathweaver_web.ps1",
        "start_web_foraging_stack.ps1",
        "install_oathweaver.ps1",
        "build_installer_exe.ps1",
        "create_clean_zip.ps1",
        "run_integration_tests.py",
        "smoke_test.py"
    )
    if ($IncludeInstallerExe) {
        if (Test-Path $installerExePath) {
            $includeFiles += $installerExeRelative
        }
        else {
            Write-Warning "Installer EXE not found ($installerExeRelative). Run with -BuildInstallerExe to generate it."
        }
    }

    foreach ($relative in $includeDirectories) {
        Copy-RelativePath -RelativePath $relative
    }
    foreach ($relative in $includeFiles) {
        Copy-RelativePath -RelativePath $relative
    }

    # Add empty runtime/project folders for first boot, without user data.
    New-Item -ItemType Directory -Path (Join-Path $stageRoot "Runtime") -Force | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $stageRoot "Projects") -Force | Out-Null

    # Remove cache and compiled artifacts if any were copied.
    Get-ChildItem -Path $stageRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $stageRoot -Recurse -File -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue

    if (Test-Path $OutputZip) {
        Remove-Item -Path $OutputZip -Force
    }

    Compress-Archive -Path (Join-Path $stageRoot "*") -DestinationPath $OutputZip -Force

    Write-Host ""
    Write-Host "Clean package created:" -ForegroundColor Green
    Write-Host "  $OutputZip"
    Write-Host ""
    Write-Host "Excluded by design:"
    Write-Host "  - Runtime user data"
    Write-Host "  - Projects outputs"
    Write-Host "  - Conversation history and generated source files"
}
finally {
    Remove-Item -Path $stageRoot -Recurse -Force -ErrorAction SilentlyContinue
}
