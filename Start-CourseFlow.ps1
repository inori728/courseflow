param([string]$File = '')

$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.dev\venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project environment not found. Run scripts/bootstrap.ps1 with your existing Anaconda Python first.'
}
$env:TEMP = Join-Path $taskRoot '.dev\tmp'
$env:TMP = $env:TEMP
$env:COURSEFLOW_HOME = Join-Path $taskRoot '.dev\user-data'
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:COURSEFLOW_HOME | Out-Null
$arguments = @((Join-Path $taskRoot 'launch_gui.py'))
if ($File) { $arguments += @('--file', $File) }
& $pythonPath @arguments
