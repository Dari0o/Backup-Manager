# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Spec-Datei zum Bauen einer .exe ohne Konsole-Fenster

a = Analysis(
    ['WindowsRuntime.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('BackupManager.py', '.'),      # BackupManager.py ins Root-Verzeichnis
        ('snooze_reminder.py', '.'),    # snooze_reminder.py ins Root-Verzeichnis
        ('backup_now.py', '.'),         # backup_now.py ins Root-Verzeichnis
    ],
    hiddenimports=['winotify', 'tqdm'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PiServerBackupReminder',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # WICHTIG: False = Kein Konsolen-Fenster!
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PiServerBackupReminder',
)
