$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeDir = Join-Path $projectRoot 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
$guestHelper = Join-Path $projectRoot 'deploy\guest.ps1'
& $guestHelper -RestoreNetwork
& $guestHelper -Script (Join-Path $projectRoot 'deploy\start-hdfs.sh') -Output '/tmp/evcharge-stage2-start.txt' -Destination (Join-Path $runtimeDir 'hdfs-start.log')
if (-not (Test-Path -LiteralPath (Join-Path $runtimeDir 'hdfs-start.log'))) { throw 'No guest startup report was returned.' }
Get-Content -LiteralPath (Join-Path $runtimeDir 'hdfs-start.log') | Select-String -Pattern 'Safe mode|Live datanodes|NameNode|DataNode|ens33'
Write-Host 'HDFS startup report: runtime/hdfs-start.log. Use the displayed Ubuntu IP for the WebHDFS endpoint.'
