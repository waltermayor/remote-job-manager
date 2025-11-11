import typer
from rich import print
from pathlib import Path
import subprocess
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
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Build a Docker image from the Dockerfile in the project's output directory.
    """
    ensure_project_initialized(project_name)
    
    project_dir = Path("output_"+project_name)
    dockerfile_path = project_dir / "Dockerfile"
    image_tag = f"{project_name}:latest"

    if not dockerfile_path.exists():
        print(f"Error: Dockerfile not found at {dockerfile_path}")
        raise typer.Exit(code=1)

    print(f"Building Docker image for project: {project_name}")
    print(f"Image tag: {image_tag}")

    try:
        process = subprocess.Popen(
            ["docker", "build", "-t", image_tag, "-f", str(dockerfile_path), str(project_dir)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        for line in iter(process.stdout.readline, ''):
            print(line, end='')
        process.wait()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, process.args)
        print(f"\nDocker image built successfully: {image_tag}")
    except FileNotFoundError:
        print("Error: 'docker' command not found. Please ensure Docker is installed and in your PATH.")
        raise typer.Exit(code=1)
    except subprocess.CalledProcessError as e:
        print(f"\nError building Docker image. Return code: {e.returncode}")
        raise typer.Exit(code=1)

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
    Create a new Dockerfile and an empty requirements.txt file from a template for a Python project.
    """
    ensure_project_initialized(project_name)
    template_path = Path(__file__).parent / "templates" / "Dockerfile.template"
    with open(template_path, "r") as f:
        template_content = f.read()

    dockerfile_content = template_content.replace("{{ project_name }}", project_name)

    output_dir = Path("output_"+project_name)
    dockerfile_path = output_dir / "Dockerfile"
    requirements_path = output_dir / "requirements.txt"

    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    with open(requirements_path, "w") as f:
        pass  # Create an empty file

    print(f"Dockerfile and requirements.txt created successfully in: {output_dir}")


if __name__ == "__main__":
    app()
