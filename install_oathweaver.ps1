param(
    [switch]$SkipNode,
    [switch]$SkipPrereqInstall,
    [switch]$SkipModelPull,
    [switch]$NoGui
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
Set-Location $RepoRoot

$script:InstallerHasGui = $false
if (-not $NoGui) {
    try {
        Add-Type -AssemblyName System.Windows.Forms
        Add-Type -AssemblyName System.Drawing
        $script:InstallerHasGui = $true
    }
    catch {
        Write-Warning "GUI prompt libraries were not available. Falling back to terminal prompts."
    }
}

$script:PythonCommand = ""
$script:PythonPrefixArgs = @()
$script:OllamaExe = ""

function Write-Step {
    param([string]$Message)
    Write-Host "[Oathweaver Installer] $Message" -ForegroundColor Cyan
}

function Write-Item {
    param([string]$Message)
    Write-Host "  - $Message"
}

function Show-InfoDialog {
    param([string]$Message, [string]$Title = "Oathweaver Installer")
    if ($script:InstallerHasGui) {
        [void][System.Windows.Forms.MessageBox]::Show(
            $Message,
            $Title,
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        )
    }
}

function Show-ErrorDialog {
    param([string]$Message, [string]$Title = "Oathweaver Installer")
    if ($script:InstallerHasGui) {
        [void][System.Windows.Forms.MessageBox]::Show(
            $Message,
            $Title,
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        )
    }
}

function Confirm-Action {
    param(
        [string]$Message,
        [string]$Title = "Oathweaver Installer",
        [bool]$DefaultYes = $true
    )
    if ($script:InstallerHasGui) {
        $result = [System.Windows.Forms.MessageBox]::Show(
            $Message,
            $Title,
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Question
        )
        return $result -eq [System.Windows.Forms.DialogResult]::Yes
    }

    $hint = if ($DefaultYes) { "[Y/n]" } else { "[y/N]" }
    $reply = Read-Host "$Message $hint"
    $text = ""
    if (-not [string]::IsNullOrWhiteSpace($reply)) {
        $text = $reply.Trim().ToLowerInvariant()
    }
    if (-not $text) {
        return $DefaultYes
    }
    return $text -in @("y", "yes")
}

function Refresh-SessionPath {
    $machinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $userPath = [Environment]::GetEnvironmentVariable("Path", "User")
    $parts = @($machinePath, $userPath, $env:Path) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
    if ($parts.Count -gt 0) {
        $env:Path = ($parts -join ";")
    }
}

function Get-CommandPath {
    param([string]$Name)
    try {
        $cmd = Get-Command $Name -ErrorAction Stop
        return [string]$cmd.Source
    }
    catch {
        return ""
    }
}

function Ensure-WingetAvailable {
    $winget = Get-CommandPath "winget"
    if ($winget) {
        return $true
    }
    throw "winget was not found. Install prerequisites manually, then rerun this installer."
}

function Install-WithWinget {
    param(
        [string]$PackageId,
        [string]$DisplayName
    )
    Ensure-WingetAvailable | Out-Null
    Write-Step "Installing $DisplayName with winget..."
    & winget install --id $PackageId -e --accept-source-agreements --accept-package-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget install failed for $DisplayName ($PackageId)."
    }
    Refresh-SessionPath
}

function Resolve-PythonLauncher {
    $pythonPath = Get-CommandPath "python"
    if ($pythonPath) {
        return @{
            command = $pythonPath
            prefix  = @()
        }
    }
    $pyPath = Get-CommandPath "py"
    if ($pyPath) {
        return @{
            command = $pyPath
            prefix  = @("-3")
        }
    }
    return $null
}

function Ensure-Python {
    $launcher = Resolve-PythonLauncher
    if (-not $launcher) {
        if ($SkipPrereqInstall) {
            throw "Python 3.10+ is required but was not found."
        }
        $allowInstall = Confirm-Action "Python 3.10+ is required. Install it now?" "Install Python"
        if (-not $allowInstall) {
            throw "Python is required to run Oathweaver."
        }
        Install-WithWinget -PackageId "Python.Python.3.11" -DisplayName "Python 3.11"
        $launcher = Resolve-PythonLauncher
        if (-not $launcher) {
            throw "Python install completed, but python is still not available in this terminal. Open a new terminal and rerun."
        }
    }

    $script:PythonCommand = [string]$launcher.command
    $script:PythonPrefixArgs = @($launcher.prefix)
    Write-Item "Python launcher: $script:PythonCommand $($script:PythonPrefixArgs -join ' ')"
}

function Invoke-Python {
    param([string[]]$Args)
    if (-not $script:PythonCommand) {
        throw "Python launcher is not initialized."
    }
    $invokeArgs = @($script:PythonPrefixArgs + $Args)
    & $script:PythonCommand @invokeArgs
    return $LASTEXITCODE
}

function Invoke-PythonSnippet {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [string[]]$Arguments = @()
    )
    $tempPath = Join-Path $env:TEMP ("oathweaver_installer_{0}.py" -f ([Guid]::NewGuid().ToString("N")))
    Set-Content -Path $tempPath -Value $Code -Encoding UTF8
    try {
        $invokeArgs = @($script:PythonPrefixArgs + @($tempPath) + $Arguments)
        $output = & $script:PythonCommand @invokeArgs 2>&1
        $exitCode = $LASTEXITCODE
        return @{
            output = @($output)
            code   = $exitCode
        }
    }
    finally {
        Remove-Item -Path $tempPath -Force -ErrorAction SilentlyContinue
    }
}

function Resolve-OllamaExePath {
    $commandPath = Get-CommandPath "ollama"
    if ($commandPath) {
        return $commandPath
    }

    $candidates = @()
    if ($env:LOCALAPPDATA) {
        $candidates += (Join-Path $env:LOCALAPPDATA "Programs\Ollama\ollama.exe")
    }
    if ($env:ProgramFiles) {
        $candidates += (Join-Path $env:ProgramFiles "Ollama\ollama.exe")
    }
    $programFilesX86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
    if ($programFilesX86) {
        $candidates += (Join-Path $programFilesX86 "Ollama\ollama.exe")
    }

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path $candidate)) {
            return (Resolve-Path $candidate).Path
        }
    }
    return ""
}

function Ensure-Ollama {
    $resolved = Resolve-OllamaExePath
    if (-not $resolved) {
        if ($SkipPrereqInstall) {
            throw "Ollama is required but not found."
        }
        $allowInstall = Confirm-Action "Ollama is required. Install it now?" "Install Ollama"
        if (-not $allowInstall) {
            throw "Ollama is required to run Oathweaver."
        }
        Install-WithWinget -PackageId "Ollama.Ollama" -DisplayName "Ollama"
        $resolved = Resolve-OllamaExePath
        if (-not $resolved) {
            throw "Ollama install completed, but the executable was not found. Reopen terminal and rerun."
        }
    }

    $script:OllamaExe = $resolved
    Write-Item "Ollama executable: $script:OllamaExe"
}

function Ensure-NodeIfRequested {
    if ($SkipNode) {
        Write-Item "Skipping Node.js checks because -SkipNode was used."
        return
    }

    $nodePath = Get-CommandPath "node"
    if ($nodePath) {
        Write-Item "Node.js found at $nodePath"
        return
    }

    if ($SkipPrereqInstall) {
        Write-Warning "Node.js was not found. It is optional for Oathweaver runtime, but useful for dev workflows."
        return
    }

    $installNode = Confirm-Action "Node.js is optional but recommended for developer tooling. Install Node.js LTS now?" "Install Node.js"
    if (-not $installNode) {
        Write-Item "Node.js install skipped."
        return
    }

    Install-WithWinget -PackageId "OpenJS.NodeJS.LTS" -DisplayName "Node.js LTS"
    $nodePath = Get-CommandPath "node"
    if ($nodePath) {
        Write-Item "Node.js found at $nodePath"
    }
    else {
        Write-Warning "Node.js install completed but command was not detected in this terminal session."
    }
}

function Install-PythonDependencies {
    Write-Step "Installing Python dependencies..."
    $pipUpgradeExit = Invoke-Python -Args @("-m", "pip", "install", "--upgrade", "pip")
    if ($pipUpgradeExit -ne 0) {
        throw "Failed to upgrade pip."
    }
    $requirementsPath = Join-Path $RepoRoot "requirements.lock"
    if (-not (Test-Path $requirementsPath)) {
        Write-Warning "requirements.lock was not found at $requirementsPath. Falling back to requirements.txt (some dependencies may be missing)."
        $requirementsPath = Join-Path $RepoRoot "requirements.txt"
    }
    if (-not (Test-Path $requirementsPath)) {
        throw "No requirements file was found at $RepoRoot"
    }
    $depsExit = Invoke-Python -Args @("-m", "pip", "install", "-r", $requirementsPath)
    if ($depsExit -ne 0) {
        throw "Failed to install Python dependencies."
    }
}

function Invoke-Ollama {
    param([string[]]$Args)
    & $script:OllamaExe @Args
    return $LASTEXITCODE
}

function Test-OllamaReady {
    param([int]$TimeoutSec = 3)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -Method Get -TimeoutSec 2
            return $true
        }
        catch {
            Start-Sleep -Milliseconds 400
        }
    }
    return $false
}

function Ensure-OllamaRunning {
    if (Test-OllamaReady -TimeoutSec 2) {
        Write-Item "Ollama API already reachable on http://127.0.0.1:11434"
        return
    }

    Write-Step "Starting Ollama service..."
    Start-Process -FilePath $script:OllamaExe -ArgumentList "serve" -WindowStyle Hidden
    if (-not (Test-OllamaReady -TimeoutSec 90)) {
        throw "Ollama did not become ready in time."
    }
    Write-Item "Ollama is ready."
}

function Get-RequiredModelsFromRouting {
    $configPath = Join-Path $RepoRoot "SourceCode\configs\model_routing.json"
    if (-not (Test-Path $configPath)) {
        throw "Model routing config not found: $configPath"
    }

    $scriptCode = @'
import json
import sys
from pathlib import Path

config_path = Path(sys.argv[1]).resolve()
data = json.loads(config_path.read_text(encoding="utf-8"))
models: set[str] = set()

def walk(node):
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "model" and isinstance(value, str) and value.strip():
                models.add(value.strip())
            elif key == "fallback_models" and isinstance(value, list):
                for item in value:
                    if isinstance(item, str) and item.strip():
                        models.add(item.strip())
            else:
                walk(value)
    elif isinstance(node, list):
        for item in node:
            walk(item)

walk(data)
for name in sorted(models):
    print(name)
'@

    $result = Invoke-PythonSnippet -Code $scriptCode -Arguments @($configPath)
    if ($result.code -ne 0) {
        throw "Failed to read required models from model_routing.json. Output: $($result.output -join [Environment]::NewLine)"
    }

    $models = @($result.output | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    if ($models.Count -eq 0) {
        throw "No models were found in model_routing.json."
    }
    return @($models | Sort-Object -Unique)
}

function Get-InstalledOllamaModels {
    $output = & $script:OllamaExe list 2>$null
    if ($LASTEXITCODE -ne 0) {
        return @()
    }
    $models = New-Object System.Collections.Generic.List[string]
    foreach ($line in @($output)) {
        $text = [string]$line
        if ([string]::IsNullOrWhiteSpace($text)) {
            continue
        }
        if ($text -match "^\s*NAME\s+") {
            continue
        }
        $name = ($text.Trim() -split "\s+")[0]
        if ($name -and $name -ne "NAME") {
            $models.Add($name)
        }
    }
    return @($models | Sort-Object -Unique)
}

function Ensure-RequiredModels {
    $required = Get-RequiredModelsFromRouting
    Write-Step "Required models from routing config:"
    foreach ($name in $required) {
        Write-Item $name
    }

    $installed = Get-InstalledOllamaModels
    $installedSet = New-Object 'System.Collections.Generic.HashSet[string]' ([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($name in $installed) {
        [void]$installedSet.Add($name)
    }

    $missing = New-Object System.Collections.Generic.List[string]
    foreach ($name in $required) {
        if (-not $installedSet.Contains($name)) {
            $missing.Add($name)
        }
    }

    if ($missing.Count -eq 0) {
        Write-Item "All required models are already installed."
        return
    }

    Write-Step "Missing models:"
    foreach ($name in $missing) {
        Write-Item $name
    }

    if ($SkipModelPull) {
        Write-Warning "Skipping model pulls because -SkipModelPull was used."
        return
    }

    $pullNow = Confirm-Action "Pull missing models now? (Can take a while and use large disk space.)" "Pull Ollama Models"
    if (-not $pullNow) {
        Write-Warning "Model pulls skipped. Oathweaver may fail to answer until these models are pulled."
        return
    }

    foreach ($model in $missing) {
        Write-Step "Pulling model: $model"
        $exitCode = Invoke-Ollama -Args @("pull", $model)
        if ($exitCode -ne 0) {
            throw "Failed to pull model: $model"
        }
    }
}

function Get-OwnerCredentials {
    if (-not $script:InstallerHasGui) {
        while ($true) {
            $username = (Read-Host "Enter owner username (letters/numbers/_/-)").Trim().ToLowerInvariant()
            $pin = (Read-Host "Enter owner 4-digit PIN").Trim()
            $confirm = (Read-Host "Confirm owner 4-digit PIN").Trim()

            if ($username -notmatch "^[a-z0-9_-]{1,32}$") {
                Write-Warning "Username must be 1-32 chars using letters, numbers, underscore, or hyphen."
                continue
            }
            if ($pin -notmatch "^[0-9]{4}$") {
                Write-Warning "PIN must be exactly 4 digits."
                continue
            }
            if ($pin -ne $confirm) {
                Write-Warning "PIN values do not match."
                continue
            }
            return @{
                Username = $username
                Pin = $pin
            }
        }
    }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = "Oathweaver - First Owner Setup"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(430, 270)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.MaximizeBox = $false
    $form.MinimizeBox = $false
    $form.TopMost = $true

    $labelIntro = New-Object System.Windows.Forms.Label
    $labelIntro.Text = "Create your first owner account."
    $labelIntro.AutoSize = $true
    $labelIntro.Location = New-Object System.Drawing.Point(20, 15)
    $form.Controls.Add($labelIntro)

    $labelUser = New-Object System.Windows.Forms.Label
    $labelUser.Text = "Username"
    $labelUser.AutoSize = $true
    $labelUser.Location = New-Object System.Drawing.Point(20, 52)
    $form.Controls.Add($labelUser)

    $usernameBox = New-Object System.Windows.Forms.TextBox
    $usernameBox.Location = New-Object System.Drawing.Point(20, 72)
    $usernameBox.Size = New-Object System.Drawing.Size(370, 24)
    $usernameBox.Text = "owner"
    $form.Controls.Add($usernameBox)

    $labelPin = New-Object System.Windows.Forms.Label
    $labelPin.Text = "PIN (4 digits)"
    $labelPin.AutoSize = $true
    $labelPin.Location = New-Object System.Drawing.Point(20, 106)
    $form.Controls.Add($labelPin)

    $pinBox = New-Object System.Windows.Forms.TextBox
    $pinBox.Location = New-Object System.Drawing.Point(20, 126)
    $pinBox.Size = New-Object System.Drawing.Size(170, 24)
    $pinBox.UseSystemPasswordChar = $true
    $form.Controls.Add($pinBox)

    $labelConfirm = New-Object System.Windows.Forms.Label
    $labelConfirm.Text = "Confirm PIN"
    $labelConfirm.AutoSize = $true
    $labelConfirm.Location = New-Object System.Drawing.Point(220, 106)
    $form.Controls.Add($labelConfirm)

    $confirmBox = New-Object System.Windows.Forms.TextBox
    $confirmBox.Location = New-Object System.Drawing.Point(220, 126)
    $confirmBox.Size = New-Object System.Drawing.Size(170, 24)
    $confirmBox.UseSystemPasswordChar = $true
    $form.Controls.Add($confirmBox)

    $hint = New-Object System.Windows.Forms.Label
    $hint.Text = "Username: a-z, 0-9, _ or -    |    PIN: exactly 4 digits"
    $hint.AutoSize = $true
    $hint.Location = New-Object System.Drawing.Point(20, 160)
    $form.Controls.Add($hint)

    $okButton = New-Object System.Windows.Forms.Button
    $okButton.Text = "Create"
    $okButton.Location = New-Object System.Drawing.Point(220, 192)
    $okButton.Size = New-Object System.Drawing.Size(80, 32)
    $form.Controls.Add($okButton)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = "Cancel"
    $cancelButton.Location = New-Object System.Drawing.Point(310, 192)
    $cancelButton.Size = New-Object System.Drawing.Size(80, 32)
    $form.Controls.Add($cancelButton)

    $cancelButton.Add_Click({
        $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
        $form.Close()
    })

    $okButton.Add_Click({
        $username = $usernameBox.Text.Trim().ToLowerInvariant()
        $pin = $pinBox.Text.Trim()
        $confirm = $confirmBox.Text.Trim()

        if ($username -notmatch "^[a-z0-9_-]{1,32}$") {
            [void][System.Windows.Forms.MessageBox]::Show(
                "Username must be 1-32 chars using letters, numbers, underscore, or hyphen.",
                "Invalid Username",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            )
            return
        }
        if ($pin -notmatch "^[0-9]{4}$") {
            [void][System.Windows.Forms.MessageBox]::Show(
                "PIN must be exactly 4 digits.",
                "Invalid PIN",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            )
            return
        }
        if ($pin -ne $confirm) {
            [void][System.Windows.Forms.MessageBox]::Show(
                "PIN values do not match.",
                "PIN Mismatch",
                [System.Windows.Forms.MessageBoxButtons]::OK,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            )
            return
        }

        $form.Tag = @{
            Username = $username
            Pin = $pin
        }
        $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
        $form.Close()
    })

    $form.AcceptButton = $okButton
    $form.CancelButton = $cancelButton

    $dialogResult = $form.ShowDialog()
    if ($dialogResult -ne [System.Windows.Forms.DialogResult]::OK) {
        return $null
    }
    return $form.Tag
}

function Test-OwnerExists {
    $scriptCode = @'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root / "SourceCode"))

from shared_tools.family_auth import FamilyAuthStore

store = FamilyAuthStore(root)
rows = store.list_profiles()
print("1" if any(bool(row.get("is_owner")) for row in rows) else "0")
'@

    $result = Invoke-PythonSnippet -Code $scriptCode -Arguments @($RepoRoot)
    if ($result.code -ne 0) {
        throw "Unable to inspect owner profiles. Output: $($result.output -join [Environment]::NewLine)"
    }
    $first = if ($result.output.Count -gt 0) { [string]$result.output[0] } else { "0" }
    return $first.Trim() -eq "1"
}

function Ensure-OwnerAccount {
    if (Test-OwnerExists) {
        Write-Item "Owner account already exists. Skipping first-user creation."
        return
    }

    Write-Step "No owner account found. Collecting owner username and PIN..."
    $credentials = Get-OwnerCredentials
    if (-not $credentials) {
        throw "Installer canceled before owner account creation."
    }

    $setupScript = @'
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
username = sys.argv[2].strip()
pin = sys.argv[3].strip()

sys.path.insert(0, str(root / "SourceCode"))
from shared_tools.family_auth import FamilyAuthStore

store = FamilyAuthStore(root)
owner = store.ensure_owner(owner_password=pin, owner_username=username)
print(owner.get("username", "owner"))
'@

    $result = Invoke-PythonSnippet -Code $setupScript -Arguments @(
        $RepoRoot,
        [string]$credentials.Username,
        [string]$credentials.Pin
    )
    if ($result.code -ne 0) {
        throw "Owner setup failed. Output: $($result.output -join [Environment]::NewLine)"
    }

    $finalUser = if ($result.output.Count -gt 0) { [string]$result.output[0] } else { [string]$credentials.Username }
    Write-Item "Owner account created for username '$($finalUser.Trim())'."
}

try {
    Write-Step "Starting setup in $RepoRoot"

    Ensure-Python
    Ensure-Ollama
    Ensure-NodeIfRequested
    Install-PythonDependencies
    Ensure-OllamaRunning
    Ensure-RequiredModels
    Ensure-OwnerAccount

    $startHint = "Setup complete.`r`n`r`nNext step:`r`n  powershell -ExecutionPolicy Bypass -File .\start_oathweaver_web.ps1"
    Write-Step "Setup complete."
    Write-Host ""
    Write-Host $startHint -ForegroundColor Green
    Show-InfoDialog -Message $startHint -Title "Oathweaver Ready"
}
catch {
    $message = "Installer failed: $($_.Exception.Message)"
    Write-Error $message
    Show-ErrorDialog -Message $message
    exit 1
}
