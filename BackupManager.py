import os
import shutil
import json
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest import case
import tqdm as tqdm_
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter


class BackupManager:

    log_dir = r"\\pi4\Share\Backup"
    log_file = os.path.join(log_dir, "backup.log")
    THREADS = 8
    VERSION = "1.0"  # Aktuelle Version

    setup_done = False

    # ----------------------------
    # Logging
    # ----------------------------
    @staticmethod
    def log(message):
        time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{time}] {message}"
        print(entry)

        os.makedirs(BackupManager.log_dir, exist_ok=True)

        with open(BackupManager.log_file, "a", encoding="utf-8") as f:
            f.write(entry + "\n")

    
    # ----------------------------
    # setup
    # ----------------------------    
    @staticmethod
    def setup():
        setup_file = "setup.json"
        
        # Lade existierende Konfiguration
        config = {}
        if os.path.exists(setup_file):
            with open(setup_file, "r", encoding="utf-8") as f:
                config = json.load(f)
        
        BackupManager.setup_done = True


    # ----------------------------
    # Update-Verwaltung
    # ----------------------------
    @staticmethod
    def get_current_version():
        """Gibt die aktuelle Version zurück"""
        return BackupManager.VERSION
    
    @staticmethod
    def compare_versions(current, available):
        """Vergleicht zwei Versionsnummern (z.B. '1.0.0' und '1.0.1')
        Gibt True zurück wenn eine neuere Version verfügbar ist"""
        try:
            current_parts = [int(x) for x in current.split('.')]
            available_parts = [int(x) for x in available.split('.')]
            
            # Pad with zeros if lengths differ
            max_len = max(len(current_parts), len(available_parts))
            current_parts += [0] * (max_len - len(current_parts))
            available_parts += [0] * (max_len - len(available_parts))
            
            return available_parts > current_parts
        except:
            return False
    
    @staticmethod
    def check_for_update():
        """Prüfe auf neue Version auf GitHub"""
        try:
            import requests
            
            GITHUB_REPO = "Dari0o/Backup-Manager"
            GITHUB_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
            
            response = requests.get(GITHUB_API, timeout=5)
            response.raise_for_status()
            release_data = response.json()
            
            tag = release_data.get("tag_name", "").lstrip('v')
            if not tag:
                return None
            
            return {
                "version": tag,
                "release_name": release_data.get("name", ""),
                "download_url": release_data.get("zipball_url", ""),
                "body": release_data.get("body", ""),
            }
        except Exception as e:
            BackupManager.log(f"Update Check Fehler: {e}")
            return None
    
    @staticmethod
    def install_update(release_info):
        """Installiere neuen Release"""
        try:
            import requests
            import zipfile
            
            BackupManager.log(f"Installiere Update {release_info['version']}...")
            
            script_dir = os.path.dirname(os.path.abspath(__file__))
            zip_path = os.path.join(script_dir, "update.zip")
            response = requests.get(release_info["download_url"], timeout=30)
            response.raise_for_status()
            
            with open(zip_path, "wb") as f:
                f.write(response.content)
            
            extract_dir = os.path.join(script_dir, "update_temp")
            os.makedirs(extract_dir, exist_ok=True)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            extracted_contents = os.listdir(extract_dir)
            if extracted_contents:
                source_dir = os.path.join(extract_dir, extracted_contents[0])
            else:
                BackupManager.log("Fehler: ZIP ist leer")
                return False
    
            
            for item in os.listdir(script_dir):
                if item.startswith('.') or item in ['update.zip', 'update_temp']:
                    continue
                item_path = os.path.join(script_dir, item)
            
            for item in os.listdir(source_dir):
                src = os.path.join(source_dir, item)
                dst = os.path.join(script_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            shutil.rmtree(extract_dir)
            os.remove(zip_path)
            
            BackupManager.log(f"Update erfolgreich installiert")
            return True
        except Exception as e:
            BackupManager.log(f"Update Installation Fehler: {e}")
            return False



    @staticmethod
    def copy_file(src, dst_base, src_base, progress):
        rel = os.path.relpath(src, src_base)
        dst = os.path.join(dst_base, rel)

        os.makedirs(os.path.dirname(dst), exist_ok=True)

        shutil.copy2(src, dst)

        progress.update(os.path.getsize(src))


    # ----------------------------
    # Prüfen ob Datei ersetzt werden muss
    # ----------------------------
    @staticmethod
    def needs_update(src_size, src_mtime, target_info):

        if target_info is None:
            return True

        dst_size, dst_mtime = target_info

        if src_size != dst_size:
            return True

        if abs(src_mtime - dst_mtime) > 2:
            return True

        return False


    # ----------------------------
    # Stat für Multithreading
    # ----------------------------
    @staticmethod
    def stat_file(path):

        try:
            stat = os.stat(path)
            return (path, stat.st_size, stat.st_mtime)

        except:
            return None


    # ----------------------------
    # Quelle scannen
    # ----------------------------
    @staticmethod
    def scan_files_multithread(base, desc):

        files = []

        file_list = []

        for root, dirs, filenames in os.walk(base):
            for name in filenames:
                file_list.append(os.path.join(root, name))

        total_size = 0

        with tqdm_.tqdm(total=len(file_list), desc=desc, unit=" files") as pbar:

            with ThreadPoolExecutor(max_workers=BackupManager.THREADS) as executor:

                futures = {
                    executor.submit(BackupManager.stat_file, f): f
                    for f in file_list
                }

                for future in as_completed(futures):

                    res = future.result()

                    if res:
                        files.append(res)
                        total_size += res[1]

                    pbar.update(1)

        return files, total_size


    # ----------------------------
    # Ziel indexieren
    # ----------------------------
    @staticmethod
    def load_target_index_multithread(target_dir, desc):

        index = {}

        file_list = []

        for root, dirs, filenames in os.walk(target_dir):
            for name in filenames:
                file_list.append(os.path.join(root, name))

        total_size = 0

        with tqdm_.tqdm(total=len(file_list), desc=desc, unit=" files") as pbar:

            with ThreadPoolExecutor(max_workers=BackupManager.THREADS) as executor:

                futures = {
                    executor.submit(BackupManager.stat_file, f): f
                    for f in file_list
                }

                for future in as_completed(futures):

                    res = future.result()

                    if res:
                        rel = os.path.relpath(res[0], target_dir)
                        index[rel] = (res[1], res[2])
                        total_size += res[1]

                    pbar.update(1)

        return index, total_size


    # ----------------------------
    # MAIN
    # ----------------------------
    @staticmethod
    def main():

        try:

            print(r"""
        .~~.   .~~.
       '. \ ' ' / .'
        .~ .~~~..~.
       : .~.'~'.~. :
      ~ (   ) (   ) ~
     ( : '~'.~.'~' : )
      ~ .~ (   ) ~. ~
       (  : '~' :  )
        '~ .~~~. ~'
            '~'


R A S P B E R R Y   P I   N A S   
        B A C K U P   
      
        """)

            BackupManager.setup()

            source_dir = prompt(
                "Bitte den Source-Ordner eingeben: ",
                completer=PathCompleter(expanduser=True, only_directories=True),
                complete_while_typing=True
            ).strip()

            if not os.path.exists(source_dir):
                BackupManager.log(
                    f"FEHLER: Source-Ordner existiert nicht: {source_dir}"
                )
                return

            while True:

                user_input = prompt(
                    f"Bitte den Ziel-Ordner angeben: ",
                    completer=PathCompleter(expanduser=True, only_directories=True),
                    complete_while_typing=True
                ).strip()

                target_dir = os.path.join(user_input)

                if os.path.commonpath(
                    [os.path.abspath(target_dir)]
                ) != os.path.abspath(target_dir):

                    BackupManager.log(
                        f"FEHLER: Ziel-Ordner ungültig: {target_dir}"
                    )
                    continue

                os.makedirs(target_dir, exist_ok=True)

                break

            BackupManager.log(f"Zielordner gesetzt: {target_dir}")
            BackupManager.log("=== Script gestartet ===")

            source_files, source_size = BackupManager.scan_files_multithread(
                source_dir, "Scan Quelle"
            )

            BackupManager.log(f"Gefundene Dateien in Quelle: {len(source_files)}")
            BackupManager.log("Bitte warten, Scan Ziel wird gestartet...")

            target_index, target_size = BackupManager.load_target_index_multithread(
                target_dir, "Scan Ziel"
            )

            files_to_copy = []

            copy_size = 0
            new_files = 0
            replace_files = 0

            with tqdm_.tqdm(
                total=source_size,
                unit="B",
                unit_scale=True,
                desc="Vergleiche Dateien",
            ) as pbar:

                for src, size, mtime in source_files:

                    rel = os.path.relpath(src, source_dir)

                    target_info = target_index.get(rel)

                    if BackupManager.needs_update(size, mtime, target_info):

                        files_to_copy.append((src, size))

                        copy_size += size

                        if target_info is None:
                            new_files += 1
                        else:
                            replace_files += 1

                    pbar.update(size)

            BackupManager.log(f"Neue Dateien: {new_files}")
            BackupManager.log(f"Bestehende Dateien ersetzen: {replace_files}")

            if len(files_to_copy) > 0:

                BackupManager.log("Kopieren startet")

                with tqdm_.tqdm(
                    total=copy_size,
                    unit="B",
                    unit_scale=True,
                    desc="Copy",
                ) as pbar:

                    with ThreadPoolExecutor(
                        max_workers=BackupManager.THREADS
                    ) as executor:

                        futures = []

                        for path, size in files_to_copy:

                            futures.append(
                                executor.submit(
                                    BackupManager.copy_file,
                                    path,
                                    target_dir,
                                    source_dir,
                                    pbar,
                                )
                            )

                        for f in futures:
                            f.result()

                BackupManager.log("Kopieren abgeschlossen")

            else:

                BackupManager.log("Keine Dateien zu kopieren")

            BackupManager.log("=== Script beendet ===")

        except KeyboardInterrupt:

            BackupManager.log("Abgebrochen durch Benutzer")

        except Exception as e:

            BackupManager.log(f"FEHLER: {e}")


# Script direkt startbar
if __name__ == "__main__":
    # Prüfe ob Update-Modus (mit --update Flag)
    is_update = "--update" in sys.argv
    
    if is_update:
        # Update-Modus: Prüfe auf Updates und installiere sie
        BackupManager.setup()
        print("Prüfe auf Updates...")
        release_info = BackupManager.check_for_update()
        if release_info:
            print(f"Update verfügbar: {release_info['version']}")
            print(f"Installiere Update...")
            if BackupManager.install_update(release_info):
                print("Update erfolgreich installiert!")
            else:
                print("Update-Installation fehlgeschlagen!")
        else:
            print("Keine neuen Updates verfügbar.")
    else:
        # Normaler Modus: Führe Backup durch
        current_version = BackupManager.get_current_version()
        print(f"BackupManager v{current_version}")
        
        release_info = BackupManager.check_for_update()
        if release_info:
            # Prüfe ob verfügbare Version neuer ist als aktuelle
            if BackupManager.compare_versions(current_version, release_info['version']):
                print(f"\n✓ Update verfügbar: v{release_info['version']}")
                print(f"Um das Update zu installieren, führen Sie BackupManager.exe --update aus\n")
        
        BackupManager.main()
        print("Programm beendet.") 

        
