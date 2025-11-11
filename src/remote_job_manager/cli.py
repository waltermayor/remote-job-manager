import typer
from rich import print
from pathlib import Path

app = typer.Typer()

@app.command()
def build(config_file: str):
    """
    Build a container image using a configuration file.
    """
    print(f"Building with config: {config_file}")

@app.command()
def convert(image_name: str):
    """
    Convert a Docker image to Singularity format.
    """
    print(f"Converting image: {image_name}")

@app.command()
def submit(config_file: str):
    """
    Submit a job to the cluster using a configuration file.
    """
    print(f"Submitting job with config: {config_file}")


@app.command()
def template(project_name: str = "my-python-app"):
    """
    Create a new Dockerfile from a template for a Python project.
    """
    template_path = Path(__file__).parent / "templates" / "Dockerfile.template"
    with open(template_path, "r") as f:
        template_content = f.read()

    dockerfile_content = template_content.replace("{{ project_name }}", project_name)

    with open("Dockerfile", "w") as f:
        f.write(dockerfile_content)
    print("Dockerfile created successfully from template.")


if __name__ == "__main__":
    app()
