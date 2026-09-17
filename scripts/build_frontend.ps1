$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$env:PATH = 'D:\node;' + $env:PATH
Push-Location (Join-Path $projectRoot 'frontend')
try {
    & 'D:\node\npm.cmd' ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    & 'D:\node\npm.cmd' run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
