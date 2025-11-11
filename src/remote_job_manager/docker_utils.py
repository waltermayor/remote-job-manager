import subprocess
from pathlib import Path
from rich import print
import typer

def run_test_in_container(image_tag: str, test_dir: Path, run_command: str):
    """
    Runs a test command inside a Docker container.
    """
    print(f"Running test command in Docker container for image: {image_tag}")

    try:
        process = subprocess.Popen(
            ["docker", "run", "--rm", "-v", f"{test_dir.resolve()}:/test", image_tag, "sh", "-c", f"cd /test && {run_command}"],
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
