@echo off
REM Alternative Build-Methode mit auto-py-to-exe

echo ========================================
echo PiServer Backup - Alternative Builder
echo ========================================
echo.

REM Installiere erforderliche Pakete
echo [*] Installiere erforderliche Pakete...
pip install --upgrade pip
pip install tqdm winotify auto-py-to-exe

REM Starte auto-py-to-exe GUI
echo.
echo [*] Starte auto-py-to-exe GUI...
echo.
echo ANLEITUNG:
echo 1. Klicke auf "Browse" und waehle: WindowsRuntime.py
echo 2. Setze den Haken bei "One File"
echo 3. Waehle Console Window: "Window Based (hide the console)"
echo 4. Klicke auf "Convert .py to .exe"
echo.
python -m auto_py_to_exe

echo.
echo [+] Wenn erfolgreich, findest du die .exe im "output" Ordner
pause
