<#
.SYNOPSIS
    Install the Setup silently, check the result, run --self-test, uninstall and check the cleanup.
.PARAMETER Setup
    Path to EasyYtDlp-Setup-<version>.exe.
.PARAMETER NoPath
    Install without the "addtopath" task and check that the user PATH is left unchanged.
.PARAMETER LogDir
    Where to write the install and uninstall logs.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)] [string]$Setup,
    [switch]$NoPath,
    [string]$LogDir = (Join-Path ([IO.Path]::GetTempPath()) "easyytdlp-smoke")
)

$ErrorActionPreference = "Stop"
$AppId = "{5BEE2B42-3B29-4957-9193-056DF2C789F4}_is1"
$UninstallKey = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\$AppId"
$InstallDir = Join-Path $env:LOCALAPPDATA "Programs\Easy yt-dlp"
$Exe = Join-Path $InstallDir "EasyYtDlp.exe"
$Shortcut = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Easy yt-dlp.lnk"
$ToolsDir = Join-Path $env:LOCALAPPDATA "EasyYtDlp\bin"
$failures = [System.Collections.Generic.List[string]]::new()

function Get-UserPath {
    $value = (Get-Item "HKCU:\Environment").GetValue("Path", "", "DoNotExpandEnvironmentNames")
    if ($null -eq $value) { return "" }
    return [string]$value
}

function Test-InPath([string]$PathValue, [string]$Entry) {
    $target = $Entry.TrimEnd("\").ToLowerInvariant()
    foreach ($part in $PathValue.Split(";")) {
        $expanded = [Environment]::ExpandEnvironmentVariables($part.Trim().Trim('"')).TrimEnd("\").ToLowerInvariant()
        if ($expanded -and $expanded -eq $target) { return $true }
    }
    return $false
}

function Format-PathEntries([string]$PathValue) {
    return (($PathValue.Split(";") | Where-Object { $_.Trim() }) -join ";")
}

function Check([bool]$Condition, [string]$Message) {
    if ($Condition) { Write-Host "  ok   $Message" }
    else { Write-Host "  FAIL $Message"; $failures.Add($Message) }
}

function Invoke-Process([string]$File, [string[]]$Arguments) {
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -Wait -PassThru
    return $process.ExitCode
}

New-Item -ItemType Directory -Force $LogDir | Out-Null
$Setup = (Resolve-Path $Setup).Path
if (Test-Path $UninstallKey) { throw "Easy yt-dlp is already installed; uninstall it first" }
$pathBefore = Get-UserPath

Write-Host "Installing $Setup (PATH task: $(-not $NoPath))"
$tasks = if ($NoPath) { '/TASKS=""' } else { '/TASKS="addtopath"' }
$code = Invoke-Process $Setup @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/CURRENTUSER", "/NORESTART", $tasks, "/LOG=`"$LogDir\install.log`"")
Check ($code -eq 0) "installer exit code is 0 (got $code)"
Check (Test-Path $Exe) "EasyYtDlp.exe installed"
Check (Test-Path $Shortcut) "Start Menu shortcut created"
Check (Test-Path $UninstallKey) "uninstall registry key created"
$pathAfter = Get-UserPath
if ($NoPath) {
    Check ((Format-PathEntries $pathAfter) -eq (Format-PathEntries $pathBefore)) "user PATH unchanged"
}
else {
    Check (Test-InPath $pathAfter $ToolsDir) "tools folder added to the user PATH"
}

Write-Host "Running --self-test"
# Keep the self-test away from the real user data.
$env:EASYYTDLP_DATA_DIR = Join-Path $LogDir "data"
$env:EASYYTDLP_TOOLS_DIR = Join-Path $LogDir "tools"
$code = Invoke-Process $Exe @("--self-test")
Check ($code -eq 0) "--self-test exit code is 0 (got $code)"
Remove-Item Env:\EASYYTDLP_DATA_DIR, Env:\EASYYTDLP_TOOLS_DIR

Write-Host "Uninstalling"
if (Test-Path $UninstallKey) {
    $uninstaller = ((Get-ItemProperty $UninstallKey).UninstallString).Trim('"')
    $code = Invoke-Process $uninstaller @("/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/LOG=`"$LogDir\uninstall.log`"")
    Check ($code -eq 0) "uninstaller exit code is 0 (got $code)"
    # The uninstaller copies itself to a temp folder and finishes there; wait for the key to go.
    for ($i = 0; $i -lt 60 -and (Test-Path $UninstallKey); $i++) { Start-Sleep -Milliseconds 500 }
    for ($i = 0; $i -lt 60 -and (Test-Path $InstallDir); $i++) { Start-Sleep -Milliseconds 500 }
}
Check (-not (Test-Path $InstallDir)) "install folder removed"
Check (-not (Test-Path $Shortcut)) "Start Menu shortcut removed"
Check (-not (Test-Path $UninstallKey)) "uninstall registry key removed"
Check (-not (Test-InPath (Get-UserPath) $ToolsDir)) "tools folder not in the user PATH"
Check ((Format-PathEntries (Get-UserPath)) -eq (Format-PathEntries $pathBefore)) "other user PATH entries preserved"

if ($failures.Count -gt 0) {
    Write-Host "`n$($failures.Count) check(s) failed. Logs: $LogDir"
    exit 1
}
Write-Host "`nInstall smoke test passed."
exit 0
