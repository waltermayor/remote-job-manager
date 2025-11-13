import subprocess
from pathlib import Path
from rich import print
import typer

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
