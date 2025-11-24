from pathlib import Path
from rich import print
from .permissions import create_project_dir

def ensure_project_initialized(project_name: str):
    """
    Ensures that the output directory for a project exists.
    If the directory does not exist, it will be created with open permissions.
    """
    output_dir = Path("output") / project_name
    if not output_dir.exists():
        print(f"Project '{project_name}' not initialized. Creating output directory...")
        create_project_dir(output_dir)
        print(f"Output directory created at: {output_dir}")
