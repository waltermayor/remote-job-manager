import typer
from rich import print
from pathlib import Path
import subprocess
import shutil
import uuid
import os
from .utils import ensure_project_initialized
from .config import load_project_config, save_project_config
from .web_utils import clone_repo, download_dataset
from .docker_utils import run_test_in_container, list_images, run_command_in_container
from .singularity_utils import convert_docker_to_singularity, run_test_in_singularity
from .wandb_utils import add_wandb_volumes
from . import remote as remote_manager

app = typer.Typer()

def dispatch_to_remote_if_needed(ctx: typer.Context, remote: str, project_name: str):
    """
    If a remote is specified, syncs the project and runs the command there.
    Then exits the local execution.
    """
    if not remote:
        return

    config = load_project_config(project_name)
    if "remotes" not in config or remote not in config["remotes"]:
        print(f"Error: Remote '{remote}' not configured for project '{project_name}'.")
        raise typer.Exit(code=1)
    
    remote_config = config["remotes"][remote]
    
    remote_base_path = remote_config.get("remote_base_path", "~/remote-job-manager-workspace")
    remote_project_dir = f"{remote_base_path}/{project_name}"

    # Reconstruct the command string to be run remotely.
    command_str = f"cd {remote_project_dir} && job-manager {ctx.invoked_subcommand} --project-name {project_name}"

    print(f"Dispatching command to remote '{remote}'...")
    remote_manager.sync_project_to_remote(remote_config, project_name)
    remote_manager.run_remote_command(remote_config, command_str)
    raise typer.Exit()

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
            "wandb_mode": "offline",
        },
        "remotes": {}
    }

    if typer.confirm("Do you want to configure the test information now?"):
        print("Please provide the following information for your project's test setup:")
        repo_url = typer.prompt("Git repository URL")
        dataset_command = typer.prompt("Dataset download command (optional)", default="")
        run_command = typer.prompt("Test run command")
        use_gpus = typer.confirm("Enable GPU support for tests?")
        print("Remember to log in to W&B on the host, and avoid hardcoding the mode in the repo config.")
        wandb_mode = typer.prompt("W&B mode (offline, online)", default="offline")
        config["test"] = {
            "repo_url": repo_url,
            "dataset_command": dataset_command,
            "run_command": run_command,
            "gpus": use_gpus,
            "wandb_mode": wandb_mode,
        }

    if typer.confirm("Do you want to configure a remote server for this project?"):
        while True:
            remote_name = typer.prompt("Enter a name for the remote (e.g., 'my-cluster')")
            remote_host = typer.prompt("Remote host address")
            remote_user = typer.prompt("Remote user")
            remote_port = typer.prompt("Remote port", default="22")
            remote_base_path = typer.prompt("Remote base path", default="~/remote-job-manager-workspace")
            
            config["remotes"][remote_name] = {
                "host": remote_host,
                "user": remote_user,
                "port": int(remote_port),
                "remote_base_path": remote_base_path,
            }

            if typer.confirm("Do you want to add initial commands for this remote?"):
                init_commands = []
                print("Enter initial commands one by one (press Enter on an empty line to finish):")
                while True:
                    command = typer.prompt("", default="", show_default=False)
                    if not command:
                        break
                    init_commands.append(command)
                config["remotes"][remote_name]["init_commands"] = init_commands
            
            if not typer.confirm("Do you want to add another remote?"):
                break

    save_project_config(project_name, config)
    print(f"Project '{project_name}' initialized successfully.")

@app.command()
def configure(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to configure."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Configure the test information for an existing project.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    if 'remotes' not in config:
        config['remotes'] = {}

    if typer.confirm("Do you want to configure the test information?"):
        print("Please provide the new test information (press Enter to keep the current value):")
        
        repo_url = typer.prompt("Git repository URL", default=config.get("test", {}).get("repo_url", ""))
        dataset_command = typer.prompt("Dataset download command (optional)", default=config.get("test", {}).get("dataset_command", ""))
        run_command = typer.prompt("Test run command", default=config.get("test", {}).get("run_command", ""))
        use_gpus = typer.confirm("Enable GPU support for tests?", default=config.get("test", {}).get("gpus", False))
        print("Remember to log in to W&B on the host, and avoid hardcoding the mode in the repo config.")
        wandb_mode = typer.prompt("W&B mode (offline, online)", default=config.get("test", {}).get("wandb_mode", "offline"))

        config["test"] = {
            "repo_url": repo_url,
            "dataset_command": dataset_command,
            "run_command": run_command,
            "gpus": use_gpus,
            "wandb_mode": wandb_mode,
        }

    if typer.confirm("Do you want to manage remote configurations?"):
        while True:
            print("\n[bold]Current Remotes:[/bold]")
            if not config["remotes"]:
                print("  No remotes configured.")
            else:
                for name, details in config["remotes"].items():
                    print(f"  - [bold cyan]{name}[/bold cyan]: {details['user']}@{details['host']}:{details['port']}")
                    print(f"    Remote Path: {details.get('remote_base_path', '~/remote-job-manager-workspace')}")
                    if "init_commands" in details:
                        print("    [italic]Initial commands:[/italic]")
                        for cmd in details["init_commands"]:
                            print(f"      - {cmd}")
            
            action = typer.prompt("\n[A]dd, [U]pdate, [R]emove, or [F]inish?", default="F").upper()

            if action == "F":
                break
            
            if action == "A":
                remote_name = typer.prompt("Enter a name for the new remote")
                remote_host = typer.prompt("Remote host address")
                remote_user = typer.prompt("Remote user")
                remote_port = typer.prompt("Remote port", default="22")
                remote_base_path = typer.prompt("Remote base path", default="~/remote-job-manager-workspace")
                config["remotes"][remote_name] = {
                    "host": remote_host, 
                    "user": remote_user, 
                    "port": int(remote_port),
                    "remote_base_path": remote_base_path,
                }
                
                if typer.confirm("Do you want to add initial commands for this remote?"):
                    init_commands = []
                    print("Enter initial commands one by one (press Enter on an empty line to finish):")
                    while True:
                        command = typer.prompt("", default="", show_default=False)
                        if not command:
                            break
                        init_commands.append(command)
                    config["remotes"][remote_name]["init_commands"] = init_commands

                print(f"Remote '{remote_name}' added.")

            elif action == "U":
                remote_name = typer.prompt("Enter the name of the remote to update")
                if remote_name in config["remotes"]:
                    print("Enter new values (press Enter to keep current):")
                    current = config["remotes"][remote_name]
                    remote_host = typer.prompt("Remote host address", default=current["host"])
                    remote_user = typer.prompt("Remote user", default=current["user"])
                    remote_port = typer.prompt("Remote port", default=str(current["port"]))
                    remote_base_path = typer.prompt("Remote base path", default=current.get("remote_base_path", "~/remote-job-manager-workspace"))
                    config["remotes"][remote_name] = {
                        "host": remote_host, 
                        "user": remote_user, 
                        "port": int(remote_port),
                        "remote_base_path": remote_base_path,
                    }

                    if typer.confirm("Do you want to update the initial commands for this remote?"):
                        init_commands = []
                        print("Current initial commands:", current.get("init_commands", "None"))
                        print("Enter new initial commands one by one (press Enter on an empty line to finish):")
                        while True:
                            command = typer.prompt("", default="", show_default=False)
                            if not command:
                                break
                            init_commands.append(command)
                        config["remotes"][remote_name]["init_commands"] = init_commands

                    print(f"Remote '{remote_name}' updated.")
                else:
                    print(f"Error: Remote '{remote_name}' not found.")

            elif action == "R":
                remote_name = typer.prompt("Enter the name of the remote to remove")
                if remote_name in config["remotes"]:
                    del config["remotes"][remote_name]
                    print(f"Remote '{remote_name}' removed.")
                else:
                    print(f"Error: Remote '{remote_name}' not found.")

    save_project_config(project_name, config)
    print(f"Configuration for project '{project_name}' updated successfully.")

@app.command()
def build(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Build a Docker image from the Dockerfile in the project's output directory.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)
    
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
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Convert the project's Docker image to Singularity format.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

    ensure_project_initialized(project_name)
    image_name = f"{project_name}:latest"
    output_dir = Path("output") / project_name
    
    convert_docker_to_singularity(image_name, output_dir)

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
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to create the Dockerfile for."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Create a new Dockerfile and an empty requirements.txt file from a template for a Python project.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

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
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to test."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Test a Docker image by cloning a repository, downloading a dataset, and running a command from the project's config.yaml.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

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
    wandb_mode = test_config.get("wandb_mode", "offline")

    if not repo_url or not run_command:
        print("Error: 'repo_url' and 'run_command' must be defined in the 'test' section of config.yaml.")
        print("You can set them by running 'job-manager configure --project-name <project_name>'")
        raise typer.Exit(code=1)

    test_dir = Path("output") / project_name / "test"
    test_dir.mkdir(parents=True, exist_ok=True)

    clone_repo(repo_url, test_dir)
    download_dataset(dataset_command, test_dir)

    image_tag = f"{project_name}:latest"
    run_test_in_container(image_tag, test_dir, run_command, project_name, use_gpus, wandb_mode)

@app.command(name="test-singularity")
def test_singularity(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to test with Singularity."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Test a Singularity image using the project's test configuration.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

    ensure_project_initialized(project_name)
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    sif_path = Path("output") / project_name / f"{project_name}.sif"
    if not sif_path.exists():
        print(f"Error: Singularity image not found at {sif_path}. Please run 'convert' first.")
        raise typer.Exit(code=1)

    test_config = config.get("test", {})
    repo_url = test_config.get("repo_url")
    dataset_command = test_config.get("dataset_command")
    run_command = test_config.get("run_command")
    use_gpus = test_config.get("gpus", False)
    wandb_mode = test_config.get("wandb_mode", "offline")

    if not repo_url or not run_command:
        print("Error: 'repo_url' and 'run_command' must be defined in the 'test' section of config.yaml.")
        raise typer.Exit(code=1)

    test_dir = Path("output") / project_name / "test"
    test_dir.mkdir(parents=True, exist_ok=True)

    clone_repo(repo_url, test_dir)
    download_dataset(dataset_command, test_dir)

    run_command = run_command.replace("<YOUR_DATA_DIRECTORY>", str(test_dir.resolve()))

    run_test_in_singularity(sif_path, test_dir, run_command, use_gpus, wandb_mode, project_name)

@app.command(name="list-images")
def list_images_command(
    ctx: typer.Context,
    project_name: str = typer.Option(None, "--project-name", "-n", help="The project context (needed for remote execution)."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    List all Docker images created by this tool.
    """
    if remote and not project_name:
        print("Error: --project-name is required when using --remote for this command.")
        raise typer.Exit(code=1)
    dispatch_to_remote_if_needed(ctx, remote, project_name)
    
    list_images()

@app.command(name="fix-and-rerun")
def fix_and_rerun(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project to fix and rerun."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Interactively fix a project's dependencies and re-run the test.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)

    ensure_project_initialized(project_name)
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    test_config = config.get("test", {})
    run_command = test_config.get("run_command")
    use_gpus = test_config.get("gpus", False)
    wandb_mode = test_config.get("wandb_mode", "offline")

    if not run_command:
        print("Error: 'run_command' must be defined in the 'test' section of config.yaml.")
        raise typer.Exit(code=1)

    image_tag = f"{project_name}:latest"
    container_name = f"fix-container-{uuid.uuid4()}"
    test_dir = Path("output") / project_name / "test"
    workdir = f"/{project_name}"

    print(f"Starting a live container '{container_name}' for interactive testing...")
    
    uid = os.getuid()
    gid = os.getgid()
    
    docker_run_cmd = [
        "docker", "run", "-d", "--name", container_name,
        "-u", f"{uid}:{gid}",
        "-v", f"{test_dir.resolve()}:{workdir}",
    ]
    docker_run_cmd = add_wandb_volumes(docker_run_cmd, wandb_mode)
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

@app.command(name="setup-remote-test-env")
def setup_remote_test_env(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    remote: str = typer.Option(..., "--remote", "-r", help="The name of the remote server to set up."),
):
    """
    Prepare the test environment on a remote server.
    """
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)

    if "remotes" not in config or remote not in config["remotes"]:
        print(f"Error: Remote '{remote}' not configured for project '{project_name}'.")
        raise typer.Exit(code=1)
    
    remote_config = config["remotes"][remote]
    
    remote_manager.prepare_remote_test_env(remote_config, project_name, config)

if __name__ == "__main__":
    app()
