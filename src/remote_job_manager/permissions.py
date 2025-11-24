import os
from pathlib import Path
from rich import print

def create_project_dir(path: Path):
    """
    Creates a directory with open permissions (777).
    """
    os.makedirs(path, mode=0o777, exist_ok=True)

def chown_to_sudo_user(path: Path):
    """
    Changes the ownership of a path to the user who invoked sudo.
    This is a no-op if not running under sudo.
    """
    sudo_uid_str = os.environ.get("SUDO_UID")
    sudo_gid_str = os.environ.get("SUDO_GID")

    if sudo_uid_str is None or sudo_gid_str is None:
        # Not running under sudo, so nothing to do
        return

    try:
        sudo_uid = int(sudo_uid_str)
        sudo_gid = int(sudo_gid_str)
    except ValueError:
        print(f"Warning: Invalid SUDO_UID or SUDO_GID environment variables.")
        return

    print(f"Changing ownership of {path} to UID={sudo_uid}, GID={sudo_gid}")
    try:
        os.chown(path, sudo_uid, sudo_gid)
        for root, dirs, files in os.walk(path):
            for d in dirs:
                os.chown(os.path.join(root, d), sudo_uid, sudo_gid)
            for f in files:
                os.chown(os.path.join(root, f), sudo_uid, sudo_gid)
    except OSError as e:
        print(f"Warning: Could not change ownership of {path}: {e}")
        print("Please ensure you have the necessary permissions.")

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