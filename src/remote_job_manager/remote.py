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
    init_commands = remote_config.get("init_commands", [])

    if init_commands:
        command = " && ".join(init_commands) + " && " + command

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

    remote_base_path = remote_config.get("remote_base_path", str(Path.home()))
    
    # Ensure the destination directory exists on the remote
    setup_command = f"mkdir -p {remote_base_path}/{project_name}"
    run_remote_command(remote_config, setup_command)

    rsync_command = [
        "rsync",
        "-avz",
        "-e", f"ssh -p {port} -o StrictHostKeyChecking=no",
        f"{local_project_dir}/",
        f"{user}@{host}:{remote_base_path}/{project_name}/",
    ]

    print(f"Syncing project '{project_name}' to remote '{host}' at '{remote_base_path}'...")
    try:
        subprocess.run(rsync_command, check=True, capture_output=True, text=True)
        print("Sync completed successfully.")
    except FileNotFoundError:
        print("Error: 'rsync' command not found. Please ensure rsync is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error syncing project to remote. Return code: {e.returncode}\n{e.stderr}")
        raise typer.Exit(code=1)

def sync_file_to_remote(remote_config: dict, local_file_path: Path, remote_dest_path: str):
    """
    Syncs a single local file to the remote server using rsync.
    """
    host = remote_config["host"]
    user = remote_config["user"]
    port = remote_config["port"]

    if not local_file_path.is_file():
        print(f"Error: Local file {local_file_path} not found.")
        raise typer.Exit(code=1)

    rsync_command = [
        "rsync",
        "-avz",
        "-e", f"ssh -p {port} -o StrictHostKeyChecking=no",
        str(local_file_path),
        f"{user}@{host}:{remote_dest_path}/",
    ]

    print(f"Syncing file '{local_file_path.name}' to remote '{host}' at '{remote_dest_path}'...")
    try:
        subprocess.run(rsync_command, check=True, capture_output=True, text=True)
        print("Sync completed successfully.")
    except FileNotFoundError:
        print("Error: 'rsync' command not found. Please ensure rsync is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error syncing file to remote. Return code: {e.returncode}\n{e.stderr}")
        raise typer.Exit(code=1)

def prepare_remote_test_env(remote_config: dict, project_name: str, project_config: dict):
    """
    Prepares the test environment on a remote server by syncing the SIF file
    and then running setup commands on the remote.
    """
    # Define local and remote paths
    local_sif_path = Path(f"output/{project_name}/{project_name}.sif")
    remote_base_path = remote_config.get("remote_base_path", str(Path.home()))
    remote_project_dir = f"{remote_base_path}/{project_name}"
    remote_test_dir = f"{remote_project_dir}/test"

    # Step 1: Create directories on remote
    print("--- Creating directories on remote server ---")
    command = f"mkdir -p {remote_test_dir}"
    run_remote_command(remote_config, command)

    # Step 2: Copy .sif file from local to remote
    print(f"--- Syncing Singularity image to {remote_project_dir} ---")
    sync_file_to_remote(remote_config, local_sif_path, remote_project_dir)

    # Step 3: Clone repo and download dataset on remote
    print("--- Cloning repository and downloading dataset on remote ---")
    repo_url = project_config["test"]["repo_url"]
    dataset_command = project_config["test"]["dataset_command"]
    
    command = f"""
    set -e
    cd {remote_test_dir}
    
    echo "Cloning repository..."
    git clone {repo_url}
    
    echo "Downloading dataset..."
    {dataset_command}
    
    echo "---- Remote test environment setup complete ----"
    """
    run_remote_command(remote_config, command)