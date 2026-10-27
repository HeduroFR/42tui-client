# Exercise the real entry point under Windows PowerShell 5 with fake native tools.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$work = Join-Path ([IO.Path]::GetTempPath()) ('42tui-ps-test-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
$originalPath = $env:PATH
$env:FAKE_HELPER = Join-Path $root 'distribution\install.py'
$env:FAKE_PYTHON = Join-Path $work 'python.cmd'
$env:FAKE_LOG = Join-Path $work 'calls.txt'
$env:PATH = "$work;$env:PATH"
function Invoke-WebRequest {
    param([switch]$UseBasicParsing, [string]$Uri, [string]$OutFile)
    if ($env:FAKE_DOWNLOAD_FAIL -eq '1') { throw 'Fixture download failure' }
    Copy-Item -LiteralPath $env:FAKE_HELPER -Destination $OutFile
}
try {
    @'
@echo off
if "%1"=="--version" (echo uv 0.13.3&exit /b 0)
echo %* | findstr /C:"--no-python-downloads" >nul
if not errorlevel 1 (echo No suitable Python found 1>&2&exit /b 1)
echo %* | findstr /C:"python install" >nul
if not errorlevel 1 (echo installed>>"%FAKE_LOG%"&exit /b 0)
echo %* | findstr /C:"python find" >nul
if not errorlevel 1 (echo %FAKE_PYTHON%&exit /b 0)
exit /b 9
'@ | Set-Content -LiteralPath (Join-Path $work 'uv.cmd') -Encoding ASCII
    @'
@echo off
echo helper>>"%FAKE_LOG%"
exit /b 0
'@ | Set-Content -LiteralPath $env:FAKE_PYTHON -Encoding ASCII
    & (Join-Path $root 'distribution\install.ps1') -NoFont -NonInteractive -Version '0.2.0'
    $calls = Get-Content -LiteralPath $env:FAKE_LOG
    if (($calls -join ',') -ne 'installed,helper') { throw "Missing-Python fallback did not run correctly: $calls" }
    Remove-Item -LiteralPath $env:FAKE_LOG
    $env:FAKE_DOWNLOAD_FAIL = '1'
    $failed = $false
    try { & (Join-Path $root 'distribution\install.ps1') -NoFont -NonInteractive } catch { $failed = $true }
    if (-not $failed) { throw 'Failed download was treated as success.' }
    if (Test-Path -LiteralPath $env:FAKE_LOG) {
        if ((Get-Content -LiteralPath $env:FAKE_LOG) -contains 'helper') { throw 'Helper ran after failed download.' }
    }
    Write-Host 'PowerShell missing-Python and download-failure checks passed.'
} finally {
    $env:PATH = $originalPath
    Remove-Item Env:FAKE_HELPER, Env:FAKE_PYTHON, Env:FAKE_LOG -ErrorAction SilentlyContinue
    Remove-Item Env:FAKE_DOWNLOAD_FAIL -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $work -Recurse -Force
}
