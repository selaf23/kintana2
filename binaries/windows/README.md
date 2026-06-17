Binaries for Windows
====================

This folder is intended to hold prebuilt Windows executables (optional). If you want to provide a ready-to-run `.exe` for a Windows user, place the file here as `autoclicker-windows.exe` and push it to the repository (preferably on a separate branch like `binaries` or in a release).

If you are a Windows user and want to build the exe locally (recommended):

Prerequisites
- Windows 10/11
- Python 3.11 installed (download from https://www.python.org/downloads/windows/)
- Optional: Administrator privileges to install packages (not required if you use a virtualenv)

Build steps (PowerShell)
1. Open PowerShell and navigate to the repository root (where `build_windows.ps1` is located).

2. Run the helper script (this creates a virtualenv, installs deps and runs PyInstaller):

   powershell -ExecutionPolicy Bypass -File .\build_windows.ps1

3. If the build succeeds, the generated executable will be in `artifact\autoclicker-windows.exe`.

4. You can then place the exe in this folder if you want to commit it to the repo, or just distribute the `artifact\autoclicker-windows.exe` directly to other Windows users.

Manual build steps (if you prefer to control everything):

   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install pyinstaller
   pyinstaller --clean --noconfirm --onefile --add-data "targets;targets" --name autoclicker autoclick_gui.py

After that `dist\autoclicker.exe` will be created; move/rename it to `artifact\autoclicker-windows.exe`.

Notes and tips
- The GUI uses Tkinter; if the bundled exe fails to start it may be due to missing system libraries or SmartScreen — try running the exe directly or looking at Windows Event Viewer.
- If you run into build issues, open `pyinstaller-windows.log` (the build script writes this file) and share it for debugging.
- Putting executables into Git makes the repo large; consider creating a GitHub release or hosting the exe separately if you plan to distribute it widely.

If you want, I can:
- walk you step-by-step while you run the PowerShell on your Windows machine,
- or, if you upload the built exe here (or to a cloud link), I can add it to the repo for you (on request).