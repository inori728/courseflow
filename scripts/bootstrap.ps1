param(
    [Parameter(Mandatory = $true)][string]$AnacondaPython,
    [switch]$Build
)

$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path -Parent $PSScriptRoot
$environmentPath = Join-Path $taskRoot '.dev\venv'
$pythonPath = Join-Path $environmentPath 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $AnacondaPython -PathType Leaf)) {
    throw 'Pass the path to an existing Anaconda Python executable.'
}
$env:TEMP = Join-Path $taskRoot '.dev\tmp'
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $taskRoot '.dev\pip-cache'
$env:COURSEFLOW_HOME = Join-Path $taskRoot '.dev\user-data'
New-Item -ItemType Directory -Force -Path $env:TEMP,$env:PIP_CACHE_DIR,$env:COURSEFLOW_HOME | Out-Null
if (-not (Test-Path -LiteralPath $pythonPath)) {
    & $AnacondaPython -m venv $environmentPath
    if ($LASTEXITCODE -ne 0) { throw 'Failed to create the isolated project environment.' }
}
& $pythonPath -m pip install --disable-pip-version-check 'setuptools>=77'
if ($LASTEXITCODE -ne 0) { throw 'Failed to install the project build backend.' }
$projectSpec = $taskRoot + $(if ($Build) { '[documents,build]' } else { '[documents]' })
& $pythonPath -m pip install --disable-pip-version-check --no-build-isolation -e $projectSpec
if ($LASTEXITCODE -ne 0) { throw 'Failed to install project dependencies.' }
Write-Output "Ready: $pythonPath"
Write-Output 'No global Python, conda configuration, or PATH was modified.'
