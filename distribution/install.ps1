# Download this script to a file to pass options. Windows support is experimental.
[CmdletBinding()]
param(
    [ValidatePattern('^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$')]
    [string]$Version,
    [switch]$Font,
    [switch]$NoFont,
    [switch]$NonInteractive
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ($Font -and $NoFont) { throw 'Choose only one of -Font and -NoFont.' }
if ($env:OS -ne 'Windows_NT') { throw 'Use install.sh on Linux and macOS.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$work = Join-Path ([IO.Path]::GetTempPath()) ('42tui-install-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $work | Out-Null
function Assert-Hash([string]$Path, [string]$Expected) {
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() -ne $Expected) {
        throw "SHA-256 verification failed for $Path"
    }
}
try {
    $uvCommand = Get-Command uv -ErrorAction SilentlyContinue
    $uv = if ($uvCommand) { $uvCommand.Source } else { Join-Path $HOME '.local\bin\uv.exe' }
    if (-not (Test-Path -LiteralPath $uv)) {
        $bootstrap = Join-Path $work 'uv.ps1'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/astral-sh/uv/releases/download/0.13.3/uv-installer.ps1' -OutFile $bootstrap
        Assert-Hash $bootstrap '7c53185c4e77cb3377782ad6f7120c2fffedcae0dcae09bad879743a7ca6eaa6'
        $priorInstall = $env:UV_INSTALL_DIR
        $priorModify = $env:UV_NO_MODIFY_PATH
        try {
            $env:UV_INSTALL_DIR = Join-Path $HOME '.local\bin'
            $env:UV_NO_MODIFY_PATH = '1'
            & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $bootstrap
            if ($LASTEXITCODE -ne 0) { throw 'uv bootstrap failed.' }
        } finally {
            $env:UV_INSTALL_DIR = $priorInstall
            $env:UV_NO_MODIFY_PATH = $priorModify
        }
    }
    $uvVersionText = & $uv --version
    if ($LASTEXITCODE -ne 0 -or $uvVersionText -notmatch '^uv (\d+\.\d+\.\d+)') { throw 'Cannot determine uv version.' }
    if ([version]$Matches[1] -lt [version]'0.13.3') { throw 'Upgrade your existing uv to >=0.13.3 and retry.' }
    # Windows PowerShell 5 can turn redirected native stderr into terminating
    # errors under Stop. A missing interpreter is expected here, so use its exit code.
    $priorErrorPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        $python = & $uv --no-config python find --no-project --no-python-downloads '>=3.12,<3.15' 2>$null
        $findExitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $priorErrorPreference
    }
    if ($findExitCode -ne 0) {
        & $uv --no-config python install --no-bin --no-registry 3.12
        if ($LASTEXITCODE -ne 0) { throw 'Python installation failed.' }
        $python = & $uv --no-config python find --no-project 3.12
        if ($LASTEXITCODE -ne 0) { throw 'Compatible Python not found.' }
    }
    $helper = Join-Path $work 'install.py'
    Invoke-WebRequest -UseBasicParsing -Uri 'https://tui.42wip.in/install.py' -OutFile $helper
    Assert-Hash $helper 'e0c3dda61ef55942b0ae33a3c8f92fb199603c0cda79eacb3326d45dddeebf76'
    $installerArgs = @($helper, '--uv', $uv)
    if ($Version) { $installerArgs += @('--version', $Version) }
    if ($Font) { $installerArgs += '--font' }
    if ($NoFont) { $installerArgs += '--no-font' }
    if ($NonInteractive) { $installerArgs += '--non-interactive' }
    & $python @installerArgs
    if ($LASTEXITCODE -ne 0) { throw '42TUI installation failed.' }
} finally {
    Remove-Item -LiteralPath $work -Recurse -Force
}
