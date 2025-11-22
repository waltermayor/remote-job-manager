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
    remote_dest = f"{user}@{host}:{remote_base_path}/"

    # Ensure the destination directory exists on the remote
    setup_command = f"mkdir -p {remote_base_path}"
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

def prepare_remote_test_env(remote_config: dict, project_name: str, project_config: dict):

    """

    Prepares the test environment on a remote server.

    """

    remote_base_path = remote_config.get("remote_base_path", "~/remote-job-manager-workspace")

    project_dir = f"{remote_base_path}/{project_name}"

    test_dir = f"{project_dir}/test"

    sif_path = f"{project_dir}/{project_name}.sif"

    

    repo_url = project_config["test"]["repo_url"]

    dataset_command = project_config["test"]["dataset_command"]



    # Construct the remote command

    command = f"""

    set -e

    echo "---- Preparing remote test environment for {project_name} ----"

    

    echo "Checking for Singularity image..."

    if [ ! -f {sif_path} ]; then

        echo "Error: Singularity image not found at {sif_path} on remote."

        exit 1

    fi

    

    echo "Creating test directory..."

    rm -rf {test_dir}

    mkdir -p {test_dir}

    

    echo "Copying Singularity image..."

    cp {sif_path} {test_dir}/

    

    cd {test_dir}

    

    echo "Cloning repository..."

    git clone {repo_url}

    

    echo "Downloading dataset..."

    {dataset_command}

    

    echo "---- Remote test environment setup complete ----"

    """

    

    run_remote_command(remote_config, command)
