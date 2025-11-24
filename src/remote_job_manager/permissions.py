import os
from pathlib import Path

def create_project_dir(path: Path):
    """
    Creates a directory with open permissions (777).
    """
    os.makedirs(path, mode=0o777, exist_ok=True)

def set_permissions_recursive(path: Path):
    """
    Sets permissions to 777 recursively for a directory and its contents.
    """
    if not path.exists():
        return
        
    # Set permissions for the directory itself
    try:
        os.chmod(path, 0o777)
    except OSError as e:
        print(f"Warning: Could not change permissions for {path}: {e}")

    # Set permissions for all files and subdirectories
    for root, dirs, files in os.walk(path):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o777)
            except OSError as e:
                print(f"Warning: Could not change permissions for {os.path.join(root, d)}: {e}")
        for f in files:
            try:
                os.chmod(os.path.join(root, f), 0o777)
            except OSError as e:
                print(f"Warning: Could not change permissions for {os.path.join(root, f)}: {e}")
