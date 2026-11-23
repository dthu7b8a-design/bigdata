$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$npm = (Get-Command npm.cmd -ErrorAction Stop).Source
Push-Location (Join-Path $projectRoot 'frontend')
try {
    & $npm ci
    if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    & $npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
} finally { Pop-Location }
