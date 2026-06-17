# kantana

Image autoclicker project — GUI and helpers.

Windows users: if you don't want to use GitHub Actions, you can build the Windows exe locally. See `binaries/windows/README.md` for step-by-step instructions.

Key files
- `autoclick_gui.py` - Tkinter GUI application (cross-platform).
- `autoclick_image.py` - headless image-based autoclicker.
- `add_target.py` - helper to add images to `targets/` and update `targets/config.json`.
- `build_windows.ps1` - PowerShell helper to build the Windows exe with PyInstaller.
- `binaries/windows/README.md` - instructions for Windows users (how to build or where to place prebuilt exe).

If you want me to place a built .exe inside the repo so a Windows user can directly download it, upload the exe (or give me a public link) and I will add it into the `binaries/windows/` folder on a separate branch named `binaries` to avoid cluttering `main`.

If you'd prefer I keep iterating on the GitHub Actions build until it works automatically, I can continue debugging the CI logs — but building locally on Windows is usually the fastest route.