@echo off
REM Script zum Bauen der .exe mit PyInstaller

echo ========================================
echo PiServer Backup Reminder - .exe Builder
echo ========================================
echo.

REM Prüfen ob PyInstaller installiert ist
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo [!] PyInstaller nicht gefunden. Installiere...
    pip install pyinstaller
)

REM Prüfen ob erforderliche Pakete installiert sind
echo.
echo [*] Installiere erforderliche Pakete...
pip install --upgrade pip
pip install tqdm winotify pyinstaller

REM .exe bauen
echo.
echo [*] Baue .exe-Datei...
python -m PyInstaller build_exe.spec --distpath . --buildpath __build__ --specpath .

echo.
if exist "PiServerBackupReminder.exe" (
    echo [+] Erfolg! .exe erstellt: PiServerBackupReminder.exe
    echo.
    echo [*] Starten Sie die .exe einmalig als Administrator, um:
    echo     - Die Autostart-Registrierung zu setzen
    echo     - Den Hintergrund-Service zu starten
    echo.
    echo [*] Nach dem ersten Start:
    echo     - Das Programm läuft unsichtbar im Hintergrund
    echo     - Bei jedem Neustart wird es automatisch gestartet
    echo     - Sie sehen nur Toast-Benachrichtigungen
) else (
    echo [-] Fehler beim Erstellen der .exe!
)

pause
