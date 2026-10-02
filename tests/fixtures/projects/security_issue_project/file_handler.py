import os

def process_file(file_path):
    # Vulnerable to command injection and path traversal
    command = f"cat {file_path} | wc -l"
    return os.system(command)
