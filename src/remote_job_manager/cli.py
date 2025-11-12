import typer
from rich import print
from pathlib import Path
import subprocess
import shutil
import uuid
from .utils import ensure_project_initialized
from .config import load_project_config, save_project_config
from .web_utils import clone_repo, download_dataset
from .docker_utils import run_test_in_container, list_images, run_command_in_container

app = typer.Typer()

@app.command()
def init(project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to initialize.")):
    """
    Initialize a new project by creating an output directory and a config.yaml file.
    """
    ensure_project_initialized(project_name)
    
    config = {
        "general": {
            "project_name": project_name,
        },
        "test": {
            "repo_url": "",
            "dataset_command": "",
            "run_command": "",
            "gpus": False,
        }
    }

    if typer.confirm("Do you want to configure the test information now?"):
        print("Please provide the following information for your project's test setup:")
        repo_url = typer.prompt("Git repository URL")
        dataset_command = typer.prompt("Dataset download command (optional)", default="")
        run_command = typer.prompt("Test run command")
        use_gpus = typer.confirm("Enable GPU support for tests?")
        config["test"] = {
            "repo_url": repo_url,
            "dataset_command": dataset_command,
            "run_command": run_command,
            "gpus": use_gpus,
        }

    save_project_config(project_name, config)
    print(f"Project '{project_name}' initialized successfully.")

@app.command()
def configure(project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to configure.")):
    """
    Configure the test information for an existing project.
    """
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    print("Please provide the new test information (press Enter to keep the current value):")
    
    repo_url = typer.prompt("Git repository URL", default=config.get("test", {}).get("repo_url", ""))
    dataset_command = typer.prompt("Dataset download command (optional)", default=config.get("test", {}).get("dataset_command", ""))
    run_command = typer.prompt("Test run command", default=config.get("test", {}).get("run_command", ""))
    use_gpus = typer.confirm("Enable GPU support for tests?", default=config.get("test", {}).get("gpus", False))

    config["test"] = {
        "repo_url": repo_url,
        "dataset_command": dataset_command,
        "run_command": run_command,
        "gpus": use_gpus,
    }

    save_project_config(project_name, config)
    print(f"Configuration for project '{project_name}' updated successfully.")

@app.command()
def build(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Build a Docker image from the Dockerfile in the project's output directory.
    """
    ensure_project_initialized(project_name)
    
    project_dir = Path("output") / project_name
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

    output_dir = Path("output") / project_name
    dockerfile_path = output_dir / "Dockerfile"
    requirements_path = output_dir / "requirements.txt"

    with open(dockerfile_path, "w") as f:
        f.write(dockerfile_content)

    with open(requirements_path, "w") as f:
        pass  # Create an empty file

    print(f"Dockerfile and requirements.txt created successfully in: {output_dir}")

@app.command()
def test(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to test."),
):
    """
    Test a Docker image by cloning a repository, downloading a dataset, and running a command from the project's config.yaml.
    """
    ensure_project_initialized(project_name)
    
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    test_config = config.get("test", {})
    repo_url = test_config.get("repo_url")
    dataset_command = test_config.get("dataset_command")
    run_command = test_config.get("run_command")
    use_gpus = test_config.get("gpus", False)

    if not repo_url or not run_command:
        print("Error: 'repo_url' and 'run_command' must be defined in the 'test' section of config.yaml.")
        print("You can set them by running 'job-manager configure --project-name <project_name>'")
        raise typer.Exit(code=1)

    test_dir = Path("output") / project_name / "test"
    if test_dir.exists():
        shutil.rmtree(test_dir)
    test_dir.mkdir()

    clone_repo(repo_url, test_dir)
    download_dataset(dataset_command, test_dir)

    # Replace placeholder in run_command
    run_command = run_command.replace("<YOUR_DATA_DIRECTORY>", str(test_dir.resolve()))

    image_tag = f"{project_name}:latest"
    run_test_in_container(image_tag, test_dir, run_command, use_gpus)

@app.command(name="list-images")
def list_images_command():
    """
    List all Docker images created by this tool.
    """
    list_images()

@app.command(name="fix-and-rerun")
def fix_and_rerun(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to fix and rerun."),
):
    """
    Interactively fix a project's dependencies and re-run the test.
    """
    ensure_project_initialized(project_name)
    
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    test_config = config.get("test", {})
    run_command = test_config.get("run_command")
    use_gpus = test_config.get("gpus", False)

    if not run_command:
        print("Error: 'run_command' must be defined in the 'test' section of config.yaml.")
        raise typer.Exit(code=1)

    image_tag = f"{project_name}:latest"
    container_name = f"fix-container-{uuid.uuid4()}"
    test_dir = Path("output") / project_name / "test"
    workdir = "/test"

    # Initial setup from test command
    if not test_dir.exists():
        test_dir.mkdir(parents=True)
    
    repo_url = test_config.get("repo_url")
    dataset_command = test_config.get("dataset_command")
    clone_repo(repo_url, test_dir)
    download_dataset(dataset_command, test_dir)
    
    run_command = run_command.replace("<YOUR_DATA_DIRECTORY>", str(test_dir.resolve()))

    print(f"Starting a live container '{container_name}' for interactive testing...")
    docker_run_cmd = [
        "docker", "run", "-d", "--name", container_name,
        "-v", f"{test_dir.resolve()}:{workdir}",
    ]
    if use_gpus:
        docker_run_cmd.extend(["--runtime=nvidia", "--gpus", "all"])
    docker_run_cmd.extend([image_tag, "tail", "-f", "/dev/null"])

    try:
        subprocess.run(docker_run_cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        print(f"Error starting live container: {e.stderr.decode()}")
        raise typer.Exit(code=1)

    try:
        while True:
            fix_cmd = typer.prompt(
                "Enter a command to fix dependencies (e.g., 'pip install numpy'), or press Enter to re-run",
                default="", show_default=False
            )
            if fix_cmd:
                fix_return_code = run_command_in_container(container_name, fix_cmd, workdir)
                if fix_return_code != 0:
                    print("[bold yellow]The fix command failed. Please try another command.[/bold yellow]")
                    continue
            
            print("--- Running Test ---")
            run_command_in_container(container_name, run_command, workdir)
            print("--- Test Finished ---")

            if not typer.confirm("Do you want to try another fix?"):
                break
    finally:
        print(f"Stopping and removing live container '{container_name}'...")
        subprocess.run(["docker", "stop", container_name], check=False, capture_output=True)
        subprocess.run(["docker", "rm", container_name], check=False, capture_output=True)

    print("\n[bold yellow]Reminder:[/bold yellow] The fixes you made were temporary.")
    print("For a permanent fix, please update your 'requirements.txt' and run the 'build' command.")

if __name__ == "__main__":
    app()
