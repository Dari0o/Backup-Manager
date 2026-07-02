import os
import zipfile
import tqdm as tqdm_
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading


def compress_to_zip(source_path: str, output_zip: str, compression_level: int = 6, log_func=None, should_ignore_func=None, num_threads: int = 1) -> bool:
    """
    Compresses a directory or file into a ZIP archive using multithreading.
    
    Args:
        source_path: Path to source directory or file
        output_zip: Path to output ZIP file or directory (if directory, ZIP is created there)
        compression_level: Compression strength (0-9)
        log_func: Optional logging function
        should_ignore_func: Optional function to determine if a path should be ignored
        num_threads: Number of threads to use for compression (default: 1)
    
    Returns:
        True if successful, False on error
    """
    
    if not log_func:
        log_func = print
    
    if not should_ignore_func:
        should_ignore_func = lambda x: False
    
    try:
        # Validate input
        if not os.path.exists(source_path):
            log_func(f"ERROR: Source path does not exist: {source_path}")
            return False
        
        if compression_level < 0 or compression_level > 9:
            log_func(f"ERROR: Compression level must be between 0 and 9")
            return False
        
        # If output_zip is a directory, generate filename
        if os.path.isdir(output_zip):
            timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
            zip_filename = f"backup_{timestamp}.zip"
            output_zip = os.path.join(output_zip, zip_filename)
        
        # Collect files
        files_to_zip = []
        total_size = 0
        
        if os.path.isfile(source_path):
            files_to_zip.append(source_path)
            total_size = os.path.getsize(source_path)
        else:
            def scan_dir(path):
                try:
                    for entry in os.scandir(path):
                        if should_ignore_func(entry):
                            continue
                        
                        if entry.is_file(follow_symlinks=False):
                            files_to_zip.append(entry.path)
                            total_size += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            scan_dir(entry.path)
                except (PermissionError, OSError):
                    pass
            
            # Non-local to update total_size
            total_size_list = [0]
            
            def scan_dir_with_size(path):
                try:
                    for entry in os.scandir(path):
                        if should_ignore_func(entry):
                            continue
                        
                        if entry.is_file(follow_symlinks=False):
                            files_to_zip.append(entry.path)
                            total_size_list[0] += entry.stat(follow_symlinks=False).st_size
                        elif entry.is_dir(follow_symlinks=False):
                            scan_dir_with_size(entry.path)
                except (PermissionError, OSError):
                    pass
            
            scan_dir_with_size(source_path)
            total_size = total_size_list[0]
        
        if not files_to_zip:
            log_func("WARNING: No files found to compress")
            return False
        
        log_func(f"Starting compression with level {compression_level}...")
        log_func(f"Files: {len(files_to_zip)}, Total size: {_format_size(total_size)}")
        
        # Create ZIP file with multithreaded compression
        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED, compresslevel=compression_level) as zipf:
            with tqdm_.tqdm(total=total_size, unit="B", unit_scale=True, desc="Compressing") as pbar:
                lock = threading.Lock()
                
                def add_file_to_zip(file_path):
                    try:
                        if os.path.isfile(source_path):
                            arcname = os.path.basename(file_path)
                        else:
                            arcname = os.path.relpath(file_path, source_path)
                        
                        file_size = os.path.getsize(file_path)
                        
                        with lock:
                            zipf.write(file_path, arcname=arcname)
                        
                        return file_size
                    except Exception as e:
                        log_func(f"WARNING: Error compressing {file_path}: {e}")
                        return 0
                
                with ThreadPoolExecutor(max_workers=num_threads) as executor:
                    futures = {executor.submit(add_file_to_zip, f): f for f in files_to_zip}
                    
                    for future in as_completed(futures):
                        file_size = future.result()
                        pbar.update(file_size)
        
        output_size = os.path.getsize(output_zip)
        compression_ratio = (1 - output_size / total_size) * 100 if total_size > 0 else 0
        
        log_func(f"Compression completed!")
        log_func(f"Original size: {_format_size(total_size)}")
        log_func(f"ZIP size: {_format_size(output_size)}")
        log_func(f"Compression ratio: {compression_ratio:.1f}%")
        
        return True
        
    except Exception as e:
        log_func(f"ERROR: Compression failed: {e}")
        return False


def _format_size(bytes_size: int) -> str:
    """Format file size in readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} PB"



