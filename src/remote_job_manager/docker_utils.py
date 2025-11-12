import subprocess
from pathlib import Path
from rich import print
import typer
import os

def run_test_in_container(image_tag: str, test_dir: Path, run_command: str, use_gpus: bool = False):
    """
    Runs a test command inside a Docker container.
    """
    print(f"Running test command in Docker container for image: {image_tag}")

    docker_command = ["docker", "run", "--rm"]
    if use_gpus:
        docker_command.extend(["--runtime=nvidia", "--gpus", "all"])
    
    # Get host user's UID and GID to run the container with the same user
    # This avoids permission issues with files created in the mounted volume
    uid = os.getuid()
    gid = os.getgid()
    docker_command.extend(["-u", f"{uid}:{gid}"])

    docker_command.extend([
        "-v", f"{test_dir.resolve()}:/test",
        image_tag,
        "sh", "-c", f"cd /test && {run_command}"
    ])

    try:
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        print("\nTest command executed successfully.")
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError running test command in Docker. Return code: {e.returncode}")
        raise typer.Exit(code=1)

def run_command_in_container(container_name: str, command: str, workdir: str) -> int:
    """
    Runs a command inside a running Docker container and returns the exit code.
    """
    print(f"Running command in container '{container_name}': {command}")
    
    docker_command = [
        "docker", "exec",
        "-w", workdir,
        container_name,
        "sh", "-c", command
    ]

    try:
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            print(f"\n[bold red]Error running command. Exit code: {process.returncode}[/bold red]")
        else:
            print("\nCommand executed successfully.")
        return process.returncode
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.")
        raise typer.Exit(code=1)

def list_images():
    """
    Lists all Docker images created by this tool.
    """
    print("Listing Docker images created by remote_job_manager...")
    try:
        subprocess.run(
            ["docker", "images", "--filter", "label=created_by=remote_job_manager"],
            check=True,
        )
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error listing Docker images. Return code: {e.returncode}")
        raise typer.Exit(code=1)
