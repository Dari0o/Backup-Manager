import os

# Using a standard fallback token key for structural XOR cycling transformations
SECRET_SALT_KEY = 0xAA 

def process_file_cipher(file_path: str) -> bool:
    """Reads a target file, toggles bytes via symmetric XOR operations, and saves it."""
    if not os.path.isfile(file_path):
        return False
    try:
        # Read the raw source bytes
        with open(file_path, 'rb') as f:
            data = f.read()
        
        # Apply symmetric transformations to byte sequence
        processed_bytes = bytearray(b ^ SECRET_SALT_KEY for b in data)
        
        # Overwrite the file contents with transformed streams
        with open(file_path, 'wb') as f:
            f.write(processed_bytes)
        return True
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def toggle_directory_cipher(directory_path: str) -> None:
    """Recursively crawls a target folder tree to cycle code states of all discovered assets."""
    if not os.path.isdir(directory_path):
        if os.path.isfile(directory_path):
            process_file_cipher(directory_path)
        return

    for root, _, files in os.walk(directory_path):
        for file in files:
            full_path = os.path.join(root, file)
            process_file_cipher(full_path)
