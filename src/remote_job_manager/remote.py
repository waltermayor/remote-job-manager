import subprocess
from pathlib import Path
from rich import print
import typer

def run_remote_command(remote_config: dict, command: str):
    """
    Executes a command on a remote server via SSH and streams the output.
    """
    host = remote_config["host"]
    user = remote_config["user"]
    port = remote_config["port"]

    ssh_command = [
        "ssh",
        "-A",
        f"{user}@{host}",
        "-p", str(port),
        "-o", "StrictHostKeyChecking=no",
        command
    ]

    print(f"Executing on remote '{host}': {' '.join(ssh_command)}")
    
    try:
        process = subprocess.Popen(
            ssh_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
    except FileNotFoundError:
        print("Error: 'ssh' command not found. Please ensure OpenSSH client is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError executing remote command. Return code: {e.returncode}")
        raise typer.Exit(code=1)

def sync_project_to_remote(remote_config: dict, project_name: str):
    """
    Syncs the local project output directory to the remote server using rsync.
    """
    host = remote_config["host"]
    user = remote_config["user"]
    port = remote_config["port"]
    
    local_project_dir = Path("output") / project_name
    if not local_project_dir.is_dir():
        print(f"Warning: Local project directory {local_project_dir} not found. Nothing to sync.")
        return

    remote_workspace = remote_config.get("workspace_dir", f"~/remote-job-manager-workspace")
    remote_dest = f"{user}@{host}:{remote_workspace}/output/"

    # Ensure the destination directory exists on the remote
    setup_command = f"mkdir -p {remote_workspace}/output"
    run_remote_command(remote_config, setup_command)

    rsync_command = [
        "rsync",
        "-avz",
        "-e", f"ssh -p {port} -o StrictHostKeyChecking=no",
        str(local_project_dir),
        remote_dest,
    ]

    print(f"Syncing project '{project_name}' to remote '{host}'...")
    try:
        subprocess.run(rsync_command, check=True, capture_output=True, text=True)
        print("Sync completed successfully.")
    except FileNotFoundError:
        print("Error: 'rsync' command not found. Please ensure rsync is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error syncing project to remote. Return code: {e.returncode}\n{e.stderr}")
        raise typer.Exit(code=1)
