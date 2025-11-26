import subprocess
from pathlib import Path
from rich import print
import typer
import os
import uuid
from .wandb_utils import add_wandb_volumes
from .utils import ensure_project_initialized

def run_test_in_container(image_tag: str, test_dir: Path, run_command: str, project_name:str, use_gpus: bool = False, wandb_mode: str = "offline") -> None:
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

    docker_command = add_wandb_volumes(docker_command, wandb_mode)
    docker_command.extend([
        "-v", f"{test_dir.resolve()}:/{project_name}",
        image_tag,
        "sh", "-c", run_command
    ])

    # Wandb-related error patterns to detect
    wandb_error_patterns = [
        "failed to get API key",
        "Unable to verify login",
        "netrc",
        "permission denied",
        "ERROR main: failed to get logger path"
    ]

    wandb_error_detected = False

    try:
        process = subprocess.Popen(
            docker_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for line in iter(process.stdout.readline, ''):

            # If first W&B error already triggered → stop printing logs
            if wandb_error_detected:
                continue

            # Print normal logs until error appears
            print(line, end='')

            # Detect error and stop logs
            if any(pattern in line for pattern in wandb_error_patterns):

                wandb_error_detected = True

                print(
                    "\033[91m\n"
                    "⚠️  WARNING: W&B authentication failed inside the container.\n"
                    "\033[93mRemember to log in to W&B on the host,\n"
                    "and avoid hardcoding the mode in the repo config.\033[0m\n"
                )

                # Stop reading further logs but allow container to finish
                break

        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        
        if not wandb_error_detected:
            print("\nTest command executed successfully.")
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError running test command in Docker. Return code: {e.returncode}")
        raise typer.Exit(code=1)

def run_command_in_container(container_name: str, command: str, workdir: str) -> None:
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

def interactive_shell(project_name: str, config: dict):
    """
    Starts an interactive shell in a new container for the given project,
    and allows committing the changes to the image.
    """
    image_tag = f"{project_name}:latest"
    container_name = f"interactive-shell-{uuid.uuid4()}"
    
    test_config = config.get("test", {})
    use_gpus = test_config.get("gpus", False)
    wandb_mode = test_config.get("wandb_mode", "offline")
    
    test_dir = Path("output") / project_name / "test"
    workdir = f"/home/devuser/{project_name}"  # devuser home
    
    docker_run_cmd = [
        "docker", "run", "-it", "--name", container_name,
        "-v", f"{test_dir.resolve()}:{workdir}",
        "-w", workdir,
    ]
    docker_run_cmd = add_wandb_volumes(docker_run_cmd, wandb_mode)
    if use_gpus:
        docker_run_cmd.extend(["--runtime=nvidia", "--gpus", "all"])
    docker_run_cmd.extend([image_tag, "/bin/bash"])

    print(f"Starting interactive shell in a new container '{container_name}'...")
    print("Exit the shell to save or discard changes.")
    
    try:
        subprocess.run(docker_run_cmd, check=True)
        
        if typer.confirm(f"Do you want to save the changes to the image '{image_tag}'?"):
            print(f"Committing changes to image '{image_tag}'...")
            subprocess.run(["docker", "commit", container_name, image_tag], check=True)
            print("Changes saved successfully.")
        else:
            print("Changes discarded.")
            
    except subprocess.CalledProcessError as e:
        print(f"\nError during interactive session. Return code: {e.returncode}")
    finally:
        print(f"Removing container '{container_name}'...")
        subprocess.run(["docker", "rm", container_name], check=False, capture_output=True)


def create_docker_template( project_name: str ):
    """
    Create a new Dockerfile and an empty requirements.txt file from a template for a Python project.
    """
    ensure_project_initialized(project_name)
    template_path = Path(__file__).parent / "templates" / "Dockerfile.template"
    with open(template_path, "r") as f:
        template_content = f.read()

    dockerfile_content = template_content.replace("{{ project_name }}", project_name)

    output_dir = Path("output") / project_name
    dockerfile_path = output_dir / "Dockerfile"
    requirements_path = output_dir / "requirements.txt"

    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    with open(requirements_path, "w") as f:
        pass  # Create an empty file

    print(f"Dockerfile and requirements.txt created successfully in: {output_dir}")
