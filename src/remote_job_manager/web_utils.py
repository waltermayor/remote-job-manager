import subprocess
from pathlib import Path
from rich import print
import typer

def clone_repo(repo_url: str, target_dir: Path):
    """
    Clones a git repository into a target directory.
    """
    print(f"Cloning repository: {repo_url}")
    try:
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True)
    except FileNotFoundError:
        print("Error: 'git' command not found. Please ensure Git is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository. Return code: {e.returncode}")
        raise typer.Exit(code=1)

def download_dataset(dataset_command: str, target_dir: Path):
    """
    Executes a command to download a dataset into a target directory.
    """
    if not dataset_command:
        return

    print(f"Executing dataset download command:\n{dataset_command}")
    print("\n--- WARNING: Executing arbitrary shell command. Ensure you trust the source of this command. ---\n")
    try:
        subprocess.run(dataset_command, shell=True, check=True, cwd=target_dir)
    except subprocess.CalledProcessError as e:
        print(f"Error executing dataset download command. Return code: {e.returncode}")
        raise typer.Exit(code=1)
