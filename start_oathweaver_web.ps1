param(
    [string]$OllamaExe = "",
    [string]$OllamaModels = "",
    [string]$OllamaHost = "0.0.0.0:11434",
    [string]$OllamaLogLevel = "info",
    [string]$WebHost = "0.0.0.0",
    [int]$WebPort = 5050,
    [string]$WebPassword = "",
    [switch]$EnableVulkan,
    [switch]$NoRestartOllama
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }

function Resolve-OllamaExe {
    param([string]$Preferred)

    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        $candidates.Add($Preferred.Trim())
    }

    try {
        $cmd = Get-Command ollama -ErrorAction Stop
        if ($cmd -and $cmd.Source) {
            $candidates.Add([string]$cmd.Source)
        }
    }
    catch {}

    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe"))
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "Ollama\ollama.exe"))
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidates.Add((Join-Path $programFilesX86 "Ollama\ollama.exe"))
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return ""
}

function Resolve-OllamaModels {
    param([string]$Preferred)

    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        $candidates.Add($Preferred.Trim())
    }

    foreach ($value in @(
        $env:OLLAMA_MODELS,
        [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "User"),
        [Environment]::GetEnvironmentVariable("OLLAMA_MODELS", "Machine")
    )) {
        if (-not [string]::IsNullOrWhiteSpace($value)) {
            $candidates.Add($value.Trim())
        }
    }

    if ($env:USERPROFILE) {
        $candidates.Add((Join-Path $env:USERPROFILE ".ollama\models"))
    }
    if ($env:LOCALAPPDATA) {
        $candidates.Add((Join-Path $env:LOCALAPPDATA "Ollama\models"))
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }

    if ($env:USERPROFILE) {
        return (Join-Path $env:USERPROFILE ".ollama\models")
    }
    return ""
}

function Test-ModelStore {
    param([string]$Path)
    $blobs = Join-Path $Path "blobs"
    $manifests = Join-Path $Path "manifests"
    return (Test-Path $blobs) -and (Test-Path $manifests)
}

$ResolvedOllamaExe = Resolve-OllamaExe -Preferred $OllamaExe
if (-not $ResolvedOllamaExe) {
    throw "Ollama executable not found. Install Ollama or pass -OllamaExe <path>."
}

$ResolvedOllamaModels = Resolve-OllamaModels -Preferred $OllamaModels
if (-not $ResolvedOllamaModels) {
    throw "Could not resolve an Ollama model directory. Pass -OllamaModels <path>."
}

if (-not (Test-Path $ResolvedOllamaModels)) {
    New-Item -ItemType Directory -Force -Path $ResolvedOllamaModels | Out-Null
    Write-Warning "Created model directory: $ResolvedOllamaModels"
}

if (-not (Test-ModelStore -Path $ResolvedOllamaModels)) {
    Write-Warning "Model directory does not yet contain both 'blobs' and 'manifests'. Pull models if this is first run."
}

$env:OLLAMA_MODELS = $ResolvedOllamaModels
$env:OLLAMA_HOST = $OllamaHost
$env:OLLAMA_LOG_LEVEL = $OllamaLogLevel
$env:OATHWEAVER_WEB_HOST = $WebHost
$env:OATHWEAVER_WEB_PORT = "$WebPort"
if ($WebPassword) {
    $env:OATHWEAVER_WEB_PASSWORD = $WebPassword
}
if ($EnableVulkan) {
    $env:OLLAMA_VULKAN = "1"
}

[Environment]::SetEnvironmentVariable("OLLAMA_MODELS", $ResolvedOllamaModels, "User")

if (-not $NoRestartOllama) {
    Get-Process | Where-Object { $_.ProcessName -like "ollama*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Start-Process -FilePath $ResolvedOllamaExe -ArgumentList "serve" -WindowStyle Hidden

$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2
        $ready = $true
        break
    }
    catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    throw "Ollama did not become ready on http://127.0.0.1:11434"
}

Write-Host "Ollama started from: $ResolvedOllamaExe"
Write-Host "OLLAMA_MODELS: $env:OLLAMA_MODELS"
Write-Host "OLLAMA_HOST: $env:OLLAMA_HOST"
Write-Host "OATHWEAVER_WEB_PASSWORD set: $([bool]$env:OATHWEAVER_WEB_PASSWORD)"
Write-Host "Local models:"
& $ResolvedOllamaExe list

$webApp = Join-Path $RepoRoot "SourceCode\web_gui\app.py"
if (-not (Test-Path $webApp)) {
    throw "Web app not found: $webApp"
}

$webAppNormalized = $webApp.ToLowerInvariant()
$existingWeb = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match "^python(\.exe)?$" -and
        $_.CommandLine -and
        $_.CommandLine.ToLowerInvariant().Contains($webAppNormalized)
    }
if ($existingWeb) {
    $existingWeb | ForEach-Object {
        try {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
        catch {}
    }
    Start-Sleep -Milliseconds 500
}

$portUsers = Get-NetTCPConnection -LocalPort $WebPort -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
if ($portUsers) {
    foreach ($portPid in $portUsers) {
        try {
            Stop-Process -Id $portPid -Force -ErrorAction SilentlyContinue
        }
        catch {}
    }
    Start-Sleep -Milliseconds 400
}

Write-Host ""
Write-Host "Starting Oathweaver Web UI..."
Write-Host "OATHWEAVER_WEB_HOST: $env:OATHWEAVER_WEB_HOST"
Write-Host "OATHWEAVER_WEB_PORT: $env:OATHWEAVER_WEB_PORT"
if ($WebHost -eq "0.0.0.0") {
    $allIps = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -ExpandProperty IPAddress -Unique
    $tailscaleIps = @($allIps | Where-Object { $_ -like "100.*" })
    $lanIps       = @($allIps | Where-Object { $_ -notlike "100.*" })

    Write-Host "Open from this PC:  http://127.0.0.1:$WebPort"

    if ($lanIps) {
        Write-Host "Open from LAN:"
        foreach ($ip in $lanIps) { Write-Host "  http://$ip`:$WebPort" }
    }
    if ($tailscaleIps) {
        Write-Host "Open via Tailscale (approved devices / cellular):"
        foreach ($ip in $tailscaleIps) { Write-Host "  http://$ip`:$WebPort" }
    } else {
        Write-Host "Tailscale not detected - install Tailscale to enable remote/cellular access."
    }
} else {
    Write-Host "Open URL: http://$WebHost`:$WebPort"
}
Write-Host "If phone cannot connect, allow inbound TCP port $WebPort in Windows Firewall."
python $webApp
