from pathlib import Path
from rich import print

def ensure_project_initialized(project_name: str):
    """
    Ensures that the output directory for a project exists.
    If the directory does not exist, it will be created with open permissions.
    """
    output_dir = Path("output") / project_name
    if not output_dir.exists():
        print(f"Project '{project_name}' not initialized. Creating output directory...")
        output_dir.mkdir(parents=True, exist_ok=True)
        print(f"Output directory created at: {output_dir}")
