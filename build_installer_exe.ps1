param(
    [string]$OutputExe = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = if ($PSScriptRoot) { $PSScriptRoot } else { (Get-Location).Path }
$versionFile = Join-Path $RepoRoot "VERSION"
$packageVersion = "0.0.0-dev"
if (Test-Path $versionFile) {
    $rawVersion = (Get-Content -Path $versionFile -TotalCount 1).Trim()
    if ($rawVersion) {
        $packageVersion = $rawVersion
    }
}
else {
    Write-Warning "VERSION file not found. Falling back to version label: $packageVersion"
}

$installScriptPath = Join-Path $RepoRoot "install_oathweaver.ps1"
if (-not (Test-Path $installScriptPath)) {
    throw "install_oathweaver.ps1 not found at: $installScriptPath"
}

if (-not $OutputExe) {
    $OutputExe = Join-Path $RepoRoot ("OathweaverInstaller_{0}.exe" -f $packageVersion)
}
$OutputExe = [System.IO.Path]::GetFullPath($OutputExe)
$outDir = Split-Path $OutputExe -Parent
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

if ((Test-Path $OutputExe) -and (-not $Force)) {
    throw "Output already exists: $OutputExe (use -Force to overwrite)."
}
if (Test-Path $OutputExe) {
    Remove-Item -Path $OutputExe -Force
}

$launcherSource = @'
using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string scriptAtSameLevel = Path.Combine(baseDir, "install_oathweaver.ps1");
            string scriptAtParent = Path.GetFullPath(Path.Combine(baseDir, "..", "install_oathweaver.ps1"));
            string scriptPath = File.Exists(scriptAtSameLevel) ? scriptAtSameLevel : (File.Exists(scriptAtParent) ? scriptAtParent : string.Empty);

            if (string.IsNullOrWhiteSpace(scriptPath))
            {
                MessageBox.Show(
                    "Could not find install_oathweaver.ps1 near this launcher.\nPlace this installer launcher in the project root (or a child folder).",
                    "Oathweaver Installer",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 2;
            }

            bool noGui = false;
            foreach (string raw in args ?? Array.Empty<string>())
            {
                string token = (raw ?? string.Empty).Trim().ToLowerInvariant();
                if (token == "--help" || token == "-h" || token == "/?")
                {
                    MessageBox.Show(
                        "Oathweaver Installer Launcher\n\nDouble-click runs the GUI installer.\n\nOptional flags:\n  --cli   Run installer in terminal mode (-NoGui)\n  --help  Show this help\n\nTechnical users can also run install_oathweaver.ps1 directly in PowerShell.",
                        "Oathweaver Installer",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Information
                    );
                    return 0;
                }
                if (token == "--cli")
                {
                    noGui = true;
                }
            }

            string arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + scriptPath + "\"";
            if (noGui)
            {
                arguments += " -NoGui";
            }

            ProcessStartInfo psi = new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = arguments,
                WorkingDirectory = Path.GetDirectoryName(scriptPath) ?? baseDir,
                UseShellExecute = true,
                WindowStyle = ProcessWindowStyle.Normal
            };

            Process p = Process.Start(psi);
            return p == null ? 3 : 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                ex.Message,
                "Oathweaver Installer",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }
    }
}
'@

Add-Type `
    -TypeDefinition $launcherSource `
    -Language CSharp `
    -OutputAssembly $OutputExe `
    -OutputType WindowsApplication `
    -ReferencedAssemblies @(
        "System.dll",
        "System.Windows.Forms.dll"
    )

Write-Host "Built installer launcher EXE:" -ForegroundColor Green
Write-Host "  $OutputExe"
Write-Host ""
Write-Host "Double-click the EXE to run GUI setup."
Write-Host "CLI mode from terminal: `"$OutputExe`" --cli"
