param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$pythonExe = Join-Path $projectRoot '.venv\Scripts\python.exe'
$runtimeDir = Join-Path $projectRoot 'runtime'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) {
    throw 'Frontend is not built. Run scripts/build_frontend.ps1 first.'
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'data\ads\dashboard.json'))) {
    throw 'No analysis result. Run python -m jobs.pipeline first.'
}
New-Item -ItemType Directory -Path $runtimeDir -Force | Out-Null
Push-Location $projectRoot
try {
    $databaseProbe = @'
from api import db
try:
    with db.connect():
        pass
except db.DatabaseUnavailable:
    raise SystemExit(1)
'@
    & $pythonExe -c $databaseProbe
    if ($LASTEXITCODE -ne 0) {
        & $pythonExe -m api.bootstrap_mysql
        if ($LASTEXITCODE -ne 0) { throw 'MySQL is unavailable. See api/README.md and runtime logs.' }
    }
    & $pythonExe -m api.import_results
    if ($LASTEXITCODE -ne 0) { throw 'MySQL result import failed.' }
    $health = $null
    try { $health = Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 3 } catch {}
    if (-not $health.ready) {
        $server = Start-Process -FilePath $pythonExe -ArgumentList @('-m','api.run') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDir 'flask.stdout.log') -RedirectStandardError (Join-Path $runtimeDir 'flask.stderr.log')
        $state = @{ pid=$server.Id; started=$server.StartTime.ToUniversalTime().ToString('o'); executable=$pythonExe }
        $state | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $runtimeDir 'flask-process.json') -Encoding UTF8
        for ($attempt=0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Milliseconds 300
            try { $health = Invoke-RestMethod 'http://127.0.0.1:5000/api/health' -TimeoutSec 2 } catch {}
            if ($health.ready) { break }
            $server.Refresh()
            if ($server.HasExited) { throw 'Flask exited. Read runtime/flask.stderr.log.' }
        }
    }
    if (-not $health.ready) { throw 'Dashboard did not become ready.' }
    Write-Host 'READY: http://127.0.0.1:5000'
    Write-Host 'Stop this launcher-owned Flask process with scripts/stop.ps1.'
    if (-not $NoBrowser) { Start-Process 'http://127.0.0.1:5000' }
} finally { Pop-Location }
