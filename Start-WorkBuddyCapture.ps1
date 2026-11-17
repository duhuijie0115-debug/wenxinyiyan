param([Parameter(Mandatory)][string]$Executable)
$ErrorActionPreference = 'Stop'
if (Get-Process WorkBuddy -ErrorAction SilentlyContinue) {
    throw '请先从托盘彻底退出 WorkBuddy，避免启动参数被现有进程忽略。'
}
$launchInfo = [System.Diagnostics.ProcessStartInfo]::new((Resolve-Path -LiteralPath $Executable).Path)
$launchInfo.UseShellExecute = $false
$launchInfo.WorkingDirectory = Split-Path (Resolve-Path -LiteralPath $Executable).Path -Parent
$launchInfo.Environment['WORKBUDDY_REMOTE_DEBUGGING_PORT'] = '19222'
# Packaged Electron rejects --require through NODE_OPTIONS. Attach the
# temporary recorder to the daemon's Node inspector after startup instead.
$launchInfo.Environment.Remove('NODE_OPTIONS') > $null
$launchInfo.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden
$launched = [System.Diagnostics.Process]::Start($launchInfo)
[pscustomobject]@{ProcessId=$launched.Id; CaptureFile=(Join-Path $PSScriptRoot 'capture\traffic.jsonl'); DebugPort=19222}
