import typer
from rich import print
from pathlib import Path
from .utils import ensure_project_initialized

app = typer.Typer()

@app.command()
def init(project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to initialize.")):
    """
    Initialize a new project by creating an output directory.
    """
    ensure_project_initialized(project_name)
    print(f"Project '{project_name}' is initialized.")

@app.command()
def build(
    config_file: str,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Build a container image using a configuration file.
    """
    ensure_project_initialized(project_name)
    print(f"Building with config: {config_file} for project: {project_name}")

@app.command()
def convert(
    image_name: str,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Convert a Docker image to Singularity format.
    """
    ensure_project_initialized(project_name)
    print(f"Converting image: {image_name} for project: {project_name}")

@app.command()
def submit(
    config_file: str,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Submit a job to the cluster using a configuration file.
    """
    ensure_project_initialized(project_name)
    print(f"Submitting job with config: {config_file} for project: {project_name}")


@app.command()
def template(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to create the Dockerfile for."),
):
    """
    Create a new Dockerfile from a template for a Python project.
    """
    ensure_project_initialized(project_name)
    template_path = Path(__file__).parent / "templates" / "Dockerfile.template"
    with open(template_path, "r") as f:
        template_content = f.read()

    dockerfile_content = template_content.replace("{{ project_name }}", project_name)

    output_dir = Path("output_"+project_name)
    dockerfile_path = output_dir / "Dockerfile"

    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)
    print(f"Dockerfile created successfully from template at: {dockerfile_path}")


if __name__ == "__main__":
    app()
