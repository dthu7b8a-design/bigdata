$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$statePath = Join-Path $projectRoot 'runtime\flask-process.json'
if (-not (Test-Path -LiteralPath $statePath)) {
    Write-Host 'No launcher-owned Flask process. If started in PyCharm, use its red Stop button.'
    exit 0
}
$state = Get-Content -LiteralPath $statePath -Raw | ConvertFrom-Json
$server = Get-Process -Id $state.pid -ErrorAction SilentlyContinue
if ($null -eq $server) { Write-Host 'Flask is already stopped.'; exit 0 }
if ($server.StartTime.ToUniversalTime().ToString('o') -ne $state.started) {
    throw 'PID was reused; refusing to stop a different process.'
}
if ($server.Path -ne $state.executable) { throw 'Executable mismatch; no process was stopped.' }
Stop-Process -Id $server.Id
Write-Host 'Flask stopped. The dedicated MySQL instance and Ubuntu HDFS remain available.'
