[CmdletBinding()]
param([switch]$Uninstall)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$startupPath = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startupPath 'wenxinyiyan.lnk'
$legacyShortcut = Join-Path $startupPath 'WorkBuddy提示词优化.lnk'
if (Test-Path -LiteralPath $legacyShortcut) { Remove-Item -LiteralPath $legacyShortcut }
if ($Uninstall) {
    if (Test-Path -LiteralPath $shortcutPath) { Remove-Item -LiteralPath $shortcutPath }
    Write-Output '已取消开机启动。当前进程请在托盘菜单退出。'
    return
}
$pythonWindowless = Join-Path $projectRoot '.venv\Scripts\pythonw.exe'
$runtime = Join-Path $PSScriptRoot 'runtime\AutoHotkey64.exe'
foreach ($required in @($pythonWindowless, $runtime, (Join-Path $projectRoot '.wenxinyiyan-api-key'))) {
    if (-not (Test-Path -LiteralPath $required)) { throw "缺少文件：$required" }
}
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonWindowless
$shortcut.Arguments = '"' + (Join-Path $PSScriptRoot 'agent.py') + '"'
$shortcut.WorkingDirectory = $projectRoot
$shortcut.Description = 'Ctrl+Alt+O 优化选中文字；Ctrl+Alt+P 粘贴最近结果'
$shortcut.Save()
Start-Process -FilePath $pythonWindowless -ArgumentList $shortcut.Arguments -WorkingDirectory $projectRoot -WindowStyle Hidden
Write-Output '已启用当前用户登录自启，并启动快捷键工具。'
