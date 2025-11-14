import subprocess
from pathlib import Path
from rich import print
import typer
import os

def convert_docker_to_singularity(image_name: str, output_dir: Path):
    """
    Converts a Docker image to a Singularity image (.sif).
    """
    sif_filename = f"{image_name.split(':')[0]}.sif"
    sif_path = output_dir / sif_filename
    docker_image_uri = f"docker-daemon://{image_name}"

    print(f"Converting Docker image '{image_name}' to Singularity image '{sif_path}'...")

    try:
        process = subprocess.Popen(
            ["singularity", "build", str(sif_path), docker_image_uri],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        print(f"\nSingularity image created successfully: {sif_path}")
    except FileNotFoundError:
        print("Error: 'singularity' command not found. Please ensure Singularity is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError converting Docker image to Singularity. Return code: {e.returncode}")
        raise typer.Exit(code=1)

def run_test_in_singularity(sif_path: Path, test_dir: Path, run_command: str, use_gpus: bool, wandb_mode: str, project_name: str):
    """
    Runs a test command inside a Singularity container using a copy-on-write strategy.
    """
    print(f"Running test command in Singularity container: {sif_path}")

    singularity_command = ["singularity", "exec", "--writable-tmpfs"]
    if use_gpus:
        singularity_command.append("--nv")
    
    # The command to run inside the container
    exec_command = (
        "mkdir -p /tmp/work && "
        "cp -r /src/. /tmp/work/ && "
        "cd /tmp/work && "
        f"{run_command}"
    )

    singularity_command.extend([
        "--bind", f"{test_dir.resolve()}:/src:ro",
        str(sif_path),
        "sh", "-c", exec_command
    ])

    env = os.environ.copy()
    if wandb_mode:
        env[f"SINGULARITYENV_WANDB_MODE"] = wandb_mode

    try:
        process = subprocess.Popen(
            singularity_command,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        print("\nTest command executed successfully in Singularity.")
    except FileNotFoundError:
        print("Error: 'singularity' command not found. Please ensure Singularity is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError running test command in Singularity. Return code: {e.returncode}")
        raise typer.Exit(code=1)
