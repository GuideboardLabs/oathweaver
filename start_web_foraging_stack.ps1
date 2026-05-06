param(
    [switch]$Recreate,
    [string]$DockerExe = "",
    [string]$DockerDesktopExe = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$SearxSettingsPath = Join-Path $RepoRoot "Runtime\services\searxng\settings.yml"

function Resolve-DockerExe {
    param([string]$Preferred)
    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        $candidates.Add($Preferred.Trim())
    }
    try {
        $cmd = Get-Command docker -ErrorAction Stop
        if ($cmd -and $cmd.Source) {
            $candidates.Add([string]$cmd.Source)
        }
    }
    catch {}
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "Docker\Docker\resources\bin\docker.exe"))
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return ""
}

function Resolve-DockerDesktopExe {
    param([string]$Preferred)
    $candidates = New-Object System.Collections.Generic.List[string]
    if (-not [string]::IsNullOrWhiteSpace($Preferred)) {
        $candidates.Add($Preferred.Trim())
    }
    if ($env:ProgramFiles) {
        $candidates.Add((Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"))
    }
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return ""
}

$ResolvedDockerExe = Resolve-DockerExe -Preferred $DockerExe
$ResolvedDockerDesktopExe = Resolve-DockerDesktopExe -Preferred $DockerDesktopExe

function Ensure-DockerReady {
    if (-not $ResolvedDockerExe) {
        throw "Docker CLI not found. Install Docker Desktop first."
    }

    $dockerBin = Split-Path $ResolvedDockerExe -Parent
    if ($dockerBin -and ($env:Path -notlike "*$dockerBin*")) {
        $env:Path += ";$dockerBin"
    }
    $ready = $false
    try {
        & $ResolvedDockerExe info *> $null
        if ($LASTEXITCODE -eq 0) {
            $ready = $true
        }
    }
    catch {}

    if ($ready) { return }

    if (-not $ResolvedDockerDesktopExe) {
        throw "Docker Desktop app not found. Install Docker Desktop first."
    }

    Write-Host "Starting Docker Desktop..."
    Start-Process -FilePath $ResolvedDockerDesktopExe
    for ($i = 0; $i -lt 60; $i++) {
        try {
            & $ResolvedDockerExe info *> $null
            if ($LASTEXITCODE -eq 0) {
                $ready = $true
                break
            }
        }
        catch {}
        Start-Sleep -Seconds 3
    }
    if (-not $ready) {
        throw "Docker daemon did not become ready in time."
    }
}

function Ensure-SearxSettings {
    New-Item -ItemType Directory -Force -Path (Split-Path $SearxSettingsPath) | Out-Null

    if (-not (Test-Path $SearxSettingsPath) -or $Recreate) {
        Write-Host "Creating baseline SearXNG settings file..."
        & $ResolvedDockerExe run -d --name searxng_seed_tmp searxng/searxng | Out-Null
        Start-Sleep -Seconds 5
        & $ResolvedDockerExe cp "searxng_seed_tmp:/etc/searxng/settings.yml" $SearxSettingsPath
        & $ResolvedDockerExe rm -f searxng_seed_tmp | Out-Null
    }

    $settings = Get-Content -Raw $SearxSettingsPath
    if ($settings -match "(?ms)^\s*formats:\s*\r?\n") {
        if ($settings -notmatch "(?ms)^\s*-\s*json\s*$") {
            $settings = $settings.Replace("  formats:`n    - html`n", "  formats:`n    - html`n    - json`n")
            Set-Content -Path $SearxSettingsPath -Value $settings -Encoding UTF8
            Write-Host "Enabled JSON format in SearXNG settings."
        }
    }
}

function Ensure-Container {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$RunArgs
    )

    $exists = (& $ResolvedDockerExe ps -a --format "{{.Names}}" | Select-String -SimpleMatch $Name) -ne $null
    if ($Recreate -and $exists) {
        & $ResolvedDockerExe rm -f $Name | Out-Null
        $exists = $false
    }

    if (-not $exists) {
        Write-Host "Creating container: $Name"
        Invoke-Expression "& `"$ResolvedDockerExe`" run -d $RunArgs" | Out-Null
    }
    else {
        $running = (& $ResolvedDockerExe ps --format "{{.Names}}" | Select-String -SimpleMatch $Name) -ne $null
        if (-not $running) {
            Write-Host "Starting container: $Name"
            & $ResolvedDockerExe start $Name | Out-Null
        }
    }
}

function Test-Url {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [int]$TimeoutSec = 20
    )
    try {
        $resp = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec $TimeoutSec
        return $resp.StatusCode
    }
    catch {
        return "ERR: $($_.Exception.Message)"
    }
}

Ensure-DockerReady
Ensure-SearxSettings

Ensure-Container -Name "searxng" -RunArgs "-p 8080:8080 --name searxng -v `"$($SearxSettingsPath):/etc/searxng/settings.yml`" searxng/searxng"
Ensure-Container -Name "crawl4ai" -RunArgs "--platform linux/amd64 -p 11235:11235 --name crawl4ai --shm-size=2g --cpus=4 --memory=4g -e MAX_CONCURRENT_TASKS=5 -e BROWSER_POOL_SIZE=10 unclecode/crawl4ai:latest"

Start-Sleep -Seconds 4
Write-Host ""
Write-Host "Container status:"
& $ResolvedDockerExe ps --filter "name=searxng" --filter "name=crawl4ai" --format "table {{.Names}}`t{{.Status}}`t{{.Ports}}"

Write-Host ""
Write-Host "Health checks:"
Write-Host "SearXNG /search json: $(Test-Url -Url 'http://127.0.0.1:8080/search?q=oathweaver&format=json')"
Write-Host "Crawl4AI /health: $(Test-Url -Url 'http://127.0.0.1:11235/health')"
Write-Host ""
Write-Host "Web foraging stack ready."
