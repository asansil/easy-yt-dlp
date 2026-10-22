<#
.SYNOPSIS
    Build dist\EasyYtDlp (PyInstaller), dist\EasyYtDlp-Setup-<version>.exe (Inno Setup) and its .sha256.
.DESCRIPTION
    The version comes from pyproject.toml. Used locally and by the CI and release workflows.
#>
[CmdletBinding()]
param(
    [string]$Iscc = ""
)

$ErrorActionPreference = "Stop"
$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
Push-Location $Root
try {
    $Version = (uv run --frozen python -c "import tomllib; print(tomllib.load(open('pyproject.toml','rb'))['project']['version'])").Trim()
    if ($LASTEXITCODE -ne 0) { throw "Could not read the version from pyproject.toml" }
    $Numbers = @([regex]::Matches(($Version -split '(\.dev|a|b|rc)')[0], '\d+') | ForEach-Object { $_.Value })
    while ($Numbers.Count -lt 4) { $Numbers += "0" }
    $NumericVersion = ($Numbers[0..3]) -join "."
    Write-Host "Building Easy yt-dlp $Version ($NumericVersion)"

    uv run --frozen python scripts/i18n.py compile
    if ($LASTEXITCODE -ne 0) { throw "Translation compilation failed" }

    uv run --frozen pyinstaller packaging/pyinstaller/easy_ytdlp.spec --noconfirm --clean
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

    if (-not $Iscc) {
        $Candidates = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
            "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
        )
        $Iscc = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not $Iscc) { throw "ISCC.exe not found; install Inno Setup 6" }
    }
    & $Iscc "/DAppVersion=$Version" "/DAppNumericVersion=$NumericVersion" "packaging\inno\setup.iss"
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed" }

    $SetupName = "EasyYtDlp-Setup-$Version.exe"
    $Setup = Join-Path $Root "dist\$SetupName"
    $Hash = (Get-FileHash $Setup -Algorithm SHA256).Hash.ToLower()
    "$Hash  $SetupName" | Out-File -Encoding ascii "$Setup.sha256"
    Write-Host "Built $Setup"
    Write-Host "SHA-256 $Hash"
}
finally {
    Pop-Location
}
