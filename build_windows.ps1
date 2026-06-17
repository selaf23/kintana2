# Script de ayuda PowerShell para construir el exe en Windows usando PyInstaller
# Uso: ejecutar en la raíz del repositorio (no requiere permisos de Administrador)

# Mostrar versión de Python
python -V

# Crear carpeta targets si no existe (evita errores de PyInstaller cuando se usa --add-data)
if (!(Test-Path targets)) { New-Item -ItemType Directory targets | Out-Null }

# Crear virtualenv
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Actualizar pip e instalar dependencias
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install pyinstaller==5.11

# Construir el exe (incluye targets/ como datos) y guardar log
pyinstaller --clean --noconfirm --onefile --add-data "targets;targets" --hidden-import positions_clicker --name autoclicker autoclick_gui.py 2>&1 | Tee-Object -FilePath pyinstaller-windows.log

# Preparar carpeta artifact y mover el exe si existe
if (!(Test-Path artifact)) { New-Item -ItemType Directory artifact | Out-Null }
if (Test-Path .\dist\autoclicker.exe) { Copy-Item -Path .\dist\autoclicker.exe -Destination .\artifact\autoclicker-windows.exe -Force }
if (Test-Path targets) { Copy-Item -Path .\targets -Destination .\artifact\targets -Recurse -Force }

Write-Host "Compilación finalizada. Artefacto en: .\artifact\autoclicker-windows.exe" -ForegroundColor Green
