$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$env:PYTHONUTF8 = '1'
Push-Location $projectRoot
try {
    & $pythonExe -m jobs.pipeline
    if ($LASTEXITCODE -ne 0) { throw 'Spark pipeline failed; previous published result was preserved.' }
    & $pythonExe -m api.import_results
    if ($LASTEXITCODE -ne 0) { throw 'MySQL import failed.' }
    & $pythonExe -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Verification failed.' }
} finally { Pop-Location }
