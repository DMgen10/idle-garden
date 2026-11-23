# Build dist\IdleGarden.exe: one file, no console window, needs no Python to run.
#   powershell -ExecutionPolicy Bypass -File packaging\windows\build_exe.ps1
$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..\..')

python -m pip install --upgrade pyinstaller pillow
python packaging\windows\make_icon.py
python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name IdleGarden `
    --icon packaging\windows\idle-garden.ico `
    --paths . `
    --hidden-import idle_garden.winscreen --hidden-import idle_garden.winsetup `
    --hidden-import idle_garden.terminal `
    packaging\windows\idle_garden_app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }
Get-Item dist\IdleGarden.exe | Format-List Name, Length
