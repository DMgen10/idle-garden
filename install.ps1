# Idle Garden for Windows: download the latest IdleGarden.exe and install it
# for the current user (no admin rights). Run in PowerShell:
#
#   irm https://raw.githubusercontent.com/DMgen10/idle-garden/main/install.ps1 | iex
#
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$url = 'https://github.com/DMgen10/idle-garden/releases/latest/download/IdleGarden.exe'
$tmp = Join-Path $env:TEMP 'IdleGarden-setup.exe'

Write-Host 'Downloading Idle Garden...' -ForegroundColor Green
Invoke-WebRequest -Uri $url -OutFile $tmp -UseBasicParsing
Unblock-File -Path $tmp

# copies itself to %LOCALAPPDATA%\Programs\Idle Garden, adds autostart and Start menu entries
Start-Process -FilePath $tmp -ArgumentList '--install' -Wait
Remove-Item $tmp -ErrorAction SilentlyContinue

Write-Host 'Done. Leave the computer alone for 2 minutes and a tree starts to grow.' -ForegroundColor Green
Write-Host 'Start menu -> "Idle Garden" shows it right now; "Uninstall Idle Garden" removes it.'
