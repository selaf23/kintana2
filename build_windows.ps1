# PowerShell helper to build the GUI exe on a Windows machine using PyInstaller
# Usage: run in the project root (PowerShell as Administrator not required but recommended)

python -V

# Create virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

# Build the one-file exe (includes targets/ as data)
pyinstaller --clean --noconfirm --onefile --add-data "targets;targets" --name autoclicker autoclick_gui.py

# Prepare artifact folder
if (!(Test-Path artifact)) { New-Item -ItemType Directory artifact | Out-Null }
Copy-Item -Path .\dist\autoclicker.exe -Destination .\artifact\autoclicker-windows.exe -Force
if (Test-Path targets) { Copy-Item -Path .\targets -Destination .\artifact\targets -Recurse -Force }

Write-Host "Build finished. Artifact is in: .\artifact\autoclicker-windows.exe" -ForegroundColor Green
