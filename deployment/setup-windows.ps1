[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ApiUrl,
    [Parameter(Mandatory)][string]$ApiKeyFile,
    [string]$SshHost = 'feiniu',
    [int]$DesktopRemotePort = 16080,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$python = Get-Command python.exe -ErrorAction Stop
& $python.Source -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ required' }
if (-not (Test-Path (Join-Path $projectRoot '.venv\Scripts\python.exe'))) {
    & $python.Source -m venv (Join-Path $projectRoot '.venv')
    if ($LASTEXITCODE -ne 0) { throw 'venv failed' }
}
$venv = Join-Path $projectRoot '.venv\Scripts\python.exe'
& $venv -m pip install -r (Join-Path $projectRoot 'requirements.lock.txt')
if ($LASTEXITCODE -ne 0) { throw 'pip failed' }
$runtime = Join-Path $projectRoot 'desktop\runtime'
$archive = Join-Path $projectRoot 'desktop\ahk-v2.zip'
if (-not (Test-Path (Join-Path $runtime 'AutoHotkey64.exe'))) {
    Invoke-WebRequest 'https://www.autohotkey.com/download/2.0/AutoHotkey_2.0.31.zip' -OutFile $archive
    $expected = 'CA1A595ACA4528755D8D4CD7FED23D497A37BD9A0B6892072612D68DEE1BD00A'
    if ((Get-FileHash $archive -Algorithm SHA256).Hash -ne $expected) { throw 'AutoHotkey checksum mismatch' }
    Expand-Archive -LiteralPath $archive -DestinationPath $runtime -Force
}
$targetKey = Join-Path $projectRoot '.wenxinyiyan-api-key'
$sourceKey = (Resolve-Path -LiteralPath $ApiKeyFile).Path
if ($sourceKey -ne $targetKey) { Copy-Item -LiteralPath $sourceKey -Destination $targetKey }
$state = Join-Path $projectRoot 'desktop\state'
New-Item -ItemType Directory -Path $state -Force | Out-Null
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
foreach ($private in @($state,$targetKey)) {
    $grant = if ($private -eq $state) { "${account}:(OI)(CI)F" } else { "${account}:F" }
    & icacls.exe $private /inheritance:r /grant:r $grant | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Failed to restrict private files' }
}
$config = @{api_url=$ApiUrl.TrimEnd('/');api_key_file='.wenxinyiyan-api-key';automatic_login_assistance=$true;ssh_host=$SshHost;desktop_local_port=16080;desktop_remote_port=$DesktopRemotePort}
$config | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $projectRoot 'desktop\settings.json') -Encoding utf8NoBOM
& $venv (Join-Path $PSScriptRoot 'verify-service.py') --url $ApiUrl
if ($LASTEXITCODE -ne 0) { throw 'Service validation failed; check login/network before enabling startup' }
if (-not $NoStart) { & (Join-Path $projectRoot 'desktop\install.ps1') }
Write-Output 'wenxinyiyan client configured.'
