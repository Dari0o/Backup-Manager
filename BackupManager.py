import os
import shutil
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest import case
from tqdm import tqdm
from prompt_toolkit import prompt
from prompt_toolkit.completion import PathCompleter


class BackupManager:

    log_dir = r"\\pi4\Share\Backup"
    log_file = os.path.join(log_dir, "backup.log")
    THREADS = 8

    setup_done = False
    recieve_update_messages = True
    recieve_backup_messages = True
    backup_reminder_days = 7

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
        
        # Wenn setup.json nicht existiert oder unvollständig, frage
        if "recieve_update_messages" not in config or "recieve_backup_messages" not in config:
            print("\n=== Setup ===\n")
            
            if "recieve_update_messages" not in config:
                while True:
                    choice = prompt("Möchten Sie Update Benachrichtigungen erhalten? (y/n): ").strip().lower()
                    if choice in ["y", "n"]:
                        config["recieve_update_messages"] = choice == "y"
                        break
                    else:
                        print("Ungültige Eingabe. Bitte 'y' oder 'n' eingeben.")
            
            if "recieve_backup_messages" not in config:
                while True:
                    choice = prompt("Möchten Sie Backup-Erinnerungen erhalten? (y/n): ").strip().lower()
                    if choice in ["y", "n"]:
                        config["recieve_backup_messages"] = choice == "y"
                        break
                    else:
                        print("Ungültige Eingabe. Bitte 'y' oder 'n' eingeben.")
                
                # Wenn ja, frage nach Intervall
                if config["recieve_backup_messages"]:
                    while True:
                        try:
                            days_input = prompt("Nach wie vielen Tagen erinnern? (z.B. 7): ").strip()
                            days = int(days_input)
                            if days > 0:
                                config["backup_reminder_days"] = days
                                break
                            else:
                                print("Bitte geben Sie eine positive Zahl ein.")
                        except ValueError:
                            print("Ungültige Eingabe. Bitte geben Sie eine ganze Zahl ein.")
            
            # Speichere in JSON
            with open(setup_file, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        
        # Setze Klassenvariablen
        BackupManager.recieve_update_messages = config.get("recieve_update_messages", True)
        BackupManager.recieve_backup_messages = config.get("recieve_backup_messages", True)
        BackupManager.backup_reminder_days = config.get("backup_reminder_days", 7)
        BackupManager.setup_done = True


    # ----------------------------
    # Datei kopieren
    # ----------------------------
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

        with tqdm(total=len(file_list), desc=desc, unit=" files") as pbar:

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

        with tqdm(total=len(file_list), desc=desc, unit=" files") as pbar:

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

            with tqdm(
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

                with tqdm(
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

        except Exception as e:

            BackupManager.log(f"FEHLER: {e}")


# Script direkt startbar
if __name__ == "__main__":
    BackupManager.main()
    input("Drücken Sie Enter, um das Programm zu beenden...")