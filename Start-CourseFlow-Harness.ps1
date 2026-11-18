param(
    [string]$HarnessExe = $env:COURSEFLOW_HARNESS_EXE,
    [string]$DataDir = $env:COURSEFLOW_HOME,
    [switch]$Demo,
    [switch]$Desktop,
    [switch]$InstallDesktop,
    [switch]$NoOpen,
    [ValidateRange(0, 65535)][int]$Port = 0
)

$ErrorActionPreference = 'Stop'
$courseFlowRoot = $PSScriptRoot
if (-not $HarnessExe) {
    $courseFlowDrive = [System.IO.Path]::GetPathRoot($courseFlowRoot)
    $HarnessExe = Join-Path $courseFlowDrive 'Deepseek Harness\DeepSeek Harness.exe'
}
if (-not (Test-Path -LiteralPath $HarnessExe -PathType Leaf)) {
    throw 'DeepSeek Harness was not found. Pass its executable path with -HarnessExe.'
}
$courseFlowHarness = (Resolve-Path -LiteralPath $HarnessExe).Path
$courseFlowResources = Join-Path (Split-Path -Parent $courseFlowHarness) 'resources'
$courseFlowCli = Join-Path $courseFlowResources 'runtime\cli\bin\dsh.cmd'
if (-not (Test-Path -LiteralPath $courseFlowCli -PathType Leaf)) {
    throw 'The installed DeepSeek Harness does not have its bundled dsh CLI.'
}

$courseFlowDev = Join-Path $courseFlowRoot '.dev'
$courseFlowPortable = Test-Path -LiteralPath (Join-Path $courseFlowRoot 'harness-release.json') -PathType Leaf
if ($courseFlowPortable) {
    $env:COURSEFLOW_BACKEND = Join-Path $courseFlowRoot 'CourseFlow-Harness.exe'
    if (-not (Test-Path -LiteralPath $env:COURSEFLOW_BACKEND -PathType Leaf)) {
        throw 'CourseFlow-Harness.exe was not found. Extract the entire plugin package first.'
    }
} else {
    if (-not $env:COURSEFLOW_PYTHON) {
        $env:COURSEFLOW_PYTHON = Join-Path $courseFlowDev 'venv\Scripts\python.exe'
    }
    if (-not (Test-Path -LiteralPath $env:COURSEFLOW_PYTHON -PathType Leaf)) {
        throw 'The CourseFlow Python environment was not found. Use the project Anaconda environment or set COURSEFLOW_PYTHON.'
    }
}

$env:TEMP = Join-Path $courseFlowDev 'tmp'
$env:TMP = $env:TEMP
$env:COURSEFLOW_HARNESS_APP = Join-Path $courseFlowResources 'app.asar'
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

if ($InstallDesktop) {
    if ($Demo -or $Desktop) {
        throw 'InstallDesktop cannot be combined with Demo or Desktop.'
    }
    if ($courseFlowPortable -and -not $DataDir) {
        $DataDir = Join-Path $courseFlowRoot 'data'
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    }
    if (-not $DataDir) {
        throw 'Use -InstallDesktop with -DataDir pointing to your CourseFlow data directory.'
    }
    if (-not (Test-Path -LiteralPath $DataDir -PathType Container)) {
        throw 'The CourseFlow data directory was not found.'
    }
    $courseFlowData = (Resolve-Path -LiteralPath $DataDir).Path
    $courseFlowLink = 'link:' + (Join-Path $courseFlowRoot 'integrations\deepseek-harness').Replace('\', '/')
    & $courseFlowCli plugin --profile desktop add $courseFlowLink --offline --ignore-scripts
    if ($LASTEXITCODE -ne 0) { throw 'The desktop plugin installation did not complete.' }
    $courseFlowBinding = @{ dataDir = $courseFlowData; appArchive = $env:COURSEFLOW_HARNESS_APP }
    if ($courseFlowPortable) { $courseFlowBinding.backend = $env:COURSEFLOW_BACKEND }
    $courseFlowBindingPath = Join-Path $courseFlowDev 'courseflow-harness-binding.json'
    [System.IO.File]::WriteAllText($courseFlowBindingPath, ($courseFlowBinding | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
    return
}

$env:DSH_HOME = Join-Path $courseFlowDev 'courseflow-harness'
if ($Demo) { $env:DSH_HOME = Join-Path $courseFlowDev 'courseflow-harness-demo' }
New-Item -ItemType Directory -Force -Path $env:DSH_HOME | Out-Null
if ($Demo) {
    $DataDir = Join-Path $courseFlowDev 'harness-demo'
}
if (-not $DataDir) {
    $DataDir = if ($courseFlowPortable) { Join-Path $courseFlowRoot 'data' } else { Join-Path $courseFlowDev 'user-data' }
}
$env:COURSEFLOW_HOME = [System.IO.Path]::GetFullPath($DataDir)
if ($Demo) {
    $env:COURSEFLOW_SOURCE = Join-Path $env:COURSEFLOW_HOME '演示课表.yaml'
    New-Item -ItemType Directory -Force -Path $env:COURSEFLOW_HOME | Out-Null
    if (-not (Test-Path -LiteralPath $env:COURSEFLOW_SOURCE)) {
        if ($courseFlowPortable) {
            & $env:COURSEFLOW_BACKEND --demo
        } else {
            $courseFlowSample = Join-Path $courseFlowRoot 'courseflow\data\示例课表.yaml'
            & $env:COURSEFLOW_PYTHON -m courseflow.harness --demo-source $courseFlowSample
        }
        if ($LASTEXITCODE -ne 0) { throw 'The CourseFlow demo timetable could not be prepared.' }
    }
}

$courseFlowPlugin = [System.Uri]::new((Join-Path $courseFlowRoot 'integrations\deepseek-harness\host.js')).AbsoluteUri
$courseFlowPatch = Join-Path $env:DSH_HOME 'courseflow.patch.yml'
$courseFlowOverlay = @"
- insert:
    - id: courseflow
      name: "$courseFlowPlugin"
"@
[System.IO.File]::WriteAllText($courseFlowPatch, $courseFlowOverlay, [System.Text.UTF8Encoding]::new($false))
if ($Desktop) {
    $courseFlowDesktopPatch = Join-Path $env:DSH_HOME 'cordis.patch.yml'
    [System.IO.File]::WriteAllText($courseFlowDesktopPatch, $courseFlowOverlay, [System.Text.UTF8Encoding]::new($false))
    $courseFlowDesktopData = Join-Path $env:DSH_HOME 'electron'
    & $courseFlowHarness "--user-data-dir=$courseFlowDesktopData"
    return
}
$courseFlowArgs = @('web', '--patch', $courseFlowPatch, '--host', '127.0.0.1', '--port', [string]$Port)
if ($NoOpen) { $courseFlowArgs += '--no-open' }
Push-Location -LiteralPath $courseFlowRoot
try {
    & $courseFlowCli @courseFlowArgs
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
