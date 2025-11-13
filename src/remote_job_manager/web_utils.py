import subprocess
from pathlib import Path
from rich import print
import typer

def clone_repo(repo_url: str, target_dir: Path):
    """
    Clones a git repository into a target directory, skipping if it already exists.
    """
    git_dir = target_dir / ".git"
    if git_dir.is_dir():
        print(f"Repository already exists in {target_dir}, skipping clone.")
        return

    print(f"Cloning repository: {repo_url}")
    try:
        subprocess.run(["git", "clone", repo_url, str(target_dir)], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print("Error: 'git' command not found. Please ensure Git is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"Error cloning repository. Return code: {e.returncode}\n{e.stderr}")
        raise typer.Exit(code=1)

def download_dataset(dataset_command: str, target_dir: Path):
    """
    Executes a command to download a dataset into a target directory, skipping if already downloaded.
    """
    if not dataset_command:
        return

    marker_file = target_dir / ".dataset_downloaded"
    if marker_file.exists():
        print("Dataset already downloaded, skipping.")
        return

    print(f"Executing dataset download command:\n{dataset_command}")
    print("\n--- WARNING: Executing arbitrary shell command. Ensure you trust the source of this command. ---\n")
    try:
        subprocess.run(dataset_command, shell=True, check=True, cwd=target_dir)
        marker_file.touch()
        print("Dataset download command executed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error executing dataset download command. Return code: {e.returncode}")
        raise typer.Exit(code=1)
