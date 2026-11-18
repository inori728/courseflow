param(
    [string]$File = '',
    [string]$DataDir = $env:COURSEFLOW_HOME,
    [switch]$Demo
)

$ErrorActionPreference = 'Stop'
$taskRoot = $PSScriptRoot
$pythonPath = Join-Path $taskRoot '.dev\venv\Scripts\pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Project environment not found. Run scripts/bootstrap.ps1 with your existing Anaconda Python first.'
}
$env:TEMP = Join-Path $taskRoot '.dev\tmp'
$env:TMP = $env:TEMP
if ($Demo) {
    $DataDir = Join-Path $taskRoot '.dev\harness-demo'
    if (-not $File) { $File = Join-Path $DataDir '演示课表.yaml' }
}
if (-not $DataDir) { $DataDir = Join-Path $taskRoot '.dev\user-data' }
$env:COURSEFLOW_HOME = [System.IO.Path]::GetFullPath($DataDir)
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:COURSEFLOW_HOME | Out-Null
if ($Demo -and -not (Test-Path -LiteralPath $File)) {
    $env:COURSEFLOW_SOURCE = $File
    & (Join-Path $taskRoot '.dev\venv\Scripts\python.exe') -m courseflow.harness --demo-source (Join-Path $taskRoot 'courseflow\data\示例课表.yaml')
    if ($LASTEXITCODE -ne 0) { throw 'The CourseFlow demo timetable could not be prepared.' }
}
$arguments = @((Join-Path $taskRoot 'launch_gui.py'))
if ($File) { $arguments += @('--file', $File) }
& $pythonPath @arguments
