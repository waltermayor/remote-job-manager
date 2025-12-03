import typer
import questionary
from rich import print
from pathlib import Path
from omegaconf import DictConfig, OmegaConf
import subprocess
import shutil
import uuid
import os
from .utils import ensure_project_initialized
from .config import load_project_config, save_project_config
from .web_utils import clone_repo, download_dataset
from .docker_utils import run_test_in_container, list_images, run_command_in_container, create_docker_template
from .singularity_utils import convert_docker_to_singularity, run_test_in_singularity
from .wandb_utils import add_wandb_volumes
from . import remote as remote_manager
import yaml

app = typer.Typer()

def _add_cluster_command():
    """
    Adds a new global cluster configuration with slurm/remote sections.
    """
    print("Adding a new global cluster configuration...")
    cluster_name = typer.prompt("Cluster name")

    # -------------------------
    # SLURM CONFIG SECTION
    # -------------------------
    slurm_config = {
        "time": typer.prompt("Default job time (e.g., 01:00:00)"),
        "memory": typer.prompt("Default memory (e.g., 32G)"),
        "gres": typer.prompt("GPU type (e.g., gpu:a100:1 or gpu:1)"),
        "cpus-per-task": typer.prompt("Default number of CPUs", type=int),
        "mail-user": typer.prompt("SLURM Email"),
        "mail-type": typer.prompt("email type (BEGIN,END,FAIL,ALL)", default="ALL"),        
        "modules": typer.prompt(
            "Modules to load (separate by commas)", 
            default=""
        ).split(","),
        "path_to_project_main": typer.prompt("Path to project main (ex, /path/to/project/main)", default=""),
    }


    # -------------------------
    # REMOTE CONFIG SECTION
    # -------------------------
    remote_host = typer.prompt("Remote host")
    remote_user = typer.prompt("Remote user")
    remote_port = typer.prompt("Remote port", default="22")
    remote_base_path = typer.prompt(
        "Remote base path", 
        default="~/remote-job-manager-workspace"
    )

    remote_cfg = {
        "host": remote_host,
        "user": remote_user,
        "port": int(remote_port),
        "remote_base_path": remote_base_path,
    }

    if typer.confirm("Add initial commands for this remote?"):
        cmds = []
        print("Enter commands one per line (empty line to finish):")
        while True:
            cmd = typer.prompt("", default="", show_default=False)
            if not cmd:
                break
            cmds.append(cmd)
        remote_cfg["init_commands"] = cmds

    full_config = {
        "slurm": slurm_config,
        "remote": remote_cfg,
    }
   
    # -------------------------
    # SAVE CONFIG
    # -------------------------
    config_dir = Path.home() / ".config" / "remote-job-manager" / "clusters"
    config_dir.mkdir(parents=True, exist_ok=True)

    config_file = config_dir / f"{cluster_name}.yaml"
    with open(config_file, "w") as f:
        yaml.dump(full_config, f, sort_keys=False)

    print(f"[green]Cluster configuration saved to {config_file}[/green]")
    return cluster_name


@app.command(name="add-cluster")
def add_cluster_command():
    _add_cluster_command()

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
        }
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

    # Create Hydra config structure
    conf_dir = Path("output") / project_name / "conf"
    (conf_dir / "cluster").mkdir(parents=True, exist_ok=True)
    (conf_dir / "experiment").mkdir(parents=True, exist_ok=True)
    (conf_dir / "grid").mkdir(parents=True, exist_ok=True)
    (conf_dir / "project").mkdir(parents=True, exist_ok=True)

    # Create a main config.yaml as the entry point for Hydra
    with open(conf_dir / "config.yaml", "w") as f:
        f.write(
        """# disable struct mode globally
        _hydra_enable_legacy_struct_: true
        
        defaults:
        - project: default
        - cluster: default
        - experiment: default
        - grid: default
        - _self_

        # These keys are used internally by the CLI
        no_submit: false
        slurm_output_dir: null
        job_index: 0
        hydra:
        run:
            dir: .
        sweep:
            dir: .
        output_subdir: null
                """)

    # Create a default project config
    with open(conf_dir / "project" / "default.yaml", "w") as f:
        yaml.dump({"general": config["general"], "test": config["test"]}, f, sort_keys=False)

    # Create placeholder default configs
    with open(conf_dir / "cluster" / "default.yaml", "w") as f:
        f.write("# Default cluster config (can be overridden, e.g., cluster=mila)\n")
    with open(conf_dir / "experiment" / "default.yaml", "w") as f:
        f.write("# Default experiment config\nscript: echo 'No script specified.'\n")
    with open(conf_dir / "grid" / "default.yaml", "w") as f:
        f.write("# Default grid config\n")


    # Link global cluster configs
    global_cluster_dir = Path.home() / ".config" / "remote-job-manager" / "clusters"
    available_clusters = [f.stem for f in global_cluster_dir.glob("*.yaml")]
    choices = available_clusters + ["<Create new cluster config>"]

    selected = questionary.select(
        "Select a cluster config to associate with this project:",
        choices=choices
    ).ask()

    if selected is None:
        print("Cancelled.")
        raise typer.Exit()

    if selected == "<Create new cluster config>":
        print("Creating a new cluster config...")
        selected = _add_cluster_command()

    if selected: 
        src = global_cluster_dir / f"{selected}.yaml"
        dest = conf_dir / "cluster" / f"{selected}.yaml"
        shutil.copy(src, dest)
        print(f"Associated cluster '{selected}' with the project. You can use it with 'cluster={selected}'.")

    save_project_config(project_name, config)
    create_docker_template(project_name)

    test_dir = Path("output") / project_name / "test"
    test_dir.mkdir(parents=True, exist_ok=True)

    test_config = config.get("test", {})
    repo_url = test_config.get("repo_url")
    clone_repo(repo_url, test_dir)

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

    uid = os.getuid()
    gid = os.getgid()
    docker_cmd = [
        "docker", "build",
        "--build-arg", f"USER_ID={uid}",
        "--build-arg", f"GROUP_ID={gid}",
        "-t", image_tag,
        "-f", str(dockerfile_path),
        str(project_dir),
    ]

    try:
        process = subprocess.Popen(
            docker_cmd,
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

@app.command()
def shell(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Start an interactive shell inside the project's Docker container.
    """
    dispatch_to_remote_if_needed(ctx, remote, project_name)
    
    ensure_project_initialized(project_name)
    config = load_project_config(project_name)
    if not config:
        print(f"Error: config.yaml not found for project '{project_name}'. Please run 'init' first.")
        raise typer.Exit(code=1)
        
    from .docker_utils import interactive_shell
    interactive_shell(project_name, config)

def _create_experiment_config(project_name: str, config_name: str = None) -> str:
    """Internal function to create a base experiment config."""
    if not config_name:
        config_name = typer.prompt("Configuration name (e.g., 'bert_base')")

    print("\n--- Configuring Fixed Parameters ---")
    fixed_params = {}
    fixed_params['script'] = typer.prompt("Enter the base script to run (e.g., python train.py)")
    fixed_params['wandb_mode'] = typer.prompt("W&B mode (offline, online)", default="offline")
    print("Enter fixed parameters (key=value), one per line. Press Enter on an empty line to finish.")
    while True:
        param = typer.prompt("", default="", show_default=False)
        if not param:
            break
        if "=" not in param:
            print("Invalid format. Please use key=value.")
            continue
        key, value = param.split("=", 1)
        fixed_params[key.strip()] = value.strip()

    conf_dir = Path("output") / project_name / "conf"
    exp_dir = conf_dir / "experiment"
    exp_dir.mkdir(parents=True, exist_ok=True)
    exp_file = exp_dir / f"{config_name}.yaml"
    with open(exp_file, 'w') as f:
        yaml.dump(fixed_params, f, sort_keys=False)
    print(f"\n[green]Experiment configuration saved to {exp_file}[/green]")
    return config_name

def _create_grid_config(project_name: str, config_name: str = None) -> str:
    """Internal function to create a grid search config."""
    if not config_name:
        config_name = typer.prompt("Configuration name (e.g., 'lr_sweep')")

    print("\n--- Configuring Grid Search Parameters ---")
    grid_params = {}
    print("Enter grid parameters (key=value1,value2,...), one per line. Press Enter on an empty line to finish.")
    while True:
        param = typer.prompt("", default="", show_default=False)
        if not param:
            break
        if "=" not in param:
            print("Invalid format. Please use key=value1,value2,...")
            continue
        key, value_str = param.split("=", 1)
        values = [v.strip() for v in value_str.split(",")]
        grid_params[key.strip()] = values

    conf_dir = Path("output") / project_name / "conf"
    grid_dir = conf_dir / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    grid_file = grid_dir / f"{config_name}.yaml"
    with open(grid_file, 'w') as f:
        yaml.dump(grid_params, f, sort_keys=False)
    print(f"\n[green]Grid configuration saved to {grid_file}[/green]")
    return config_name

@app.command(name="add-experiment-config")
def add_experiment_config_command(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Adds a new reusable base experiment configuration.
    """
    print("Adding a new base experiment configuration...")
    _create_experiment_config(project_name)

@app.command(name="add-grid-config")
def add_grid_config_command(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Adds a new reusable grid search configuration.
    """
    print("Adding a new grid search configuration...")
    _create_grid_config(project_name)

@app.command(name="add-experiment")
def add_experiment_command(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
):
    """
    Wizard to create a new experiment run by combining an experiment config and a new grid config.
    """
    ensure_project_initialized(project_name)
    conf_dir = Path("output") / project_name / "conf"
    exp_dir = conf_dir / "experiment"

    # --- Step 1: Select or Create Base Experiment Config ---
    base_exp_config_name = ""
    available_exp_configs = [f.stem for f in exp_dir.glob("*.yaml")]
    choices = available_exp_configs + ["<Create new experiment config>"]

    selected = questionary.select(
        "Select a base experiment config:",
        choices=choices
    ).ask()

    if selected is None:
        print("Cancelled.")
        raise typer.Exit()

    if selected == "<Create new experiment config>":
        print("Creating a new experiment config...")
        base_exp_config_name = _create_experiment_config(project_name)

    else:
        base_exp_config_name = _create_experiment_config(project_name, selected)
    
    # --- Step 2: Create Grid Config for this Run ---
    print(f"\nNow, let's create a grid search for the '{base_exp_config_name}' experiment.")
    grid_name_suggestion = f"{base_exp_config_name}_grid_{uuid.uuid4().hex[:4]}"
    grid_config_name = typer.prompt(f"Enter a name for this new grid configuration", default=grid_name_suggestion)
    
    _create_grid_config(project_name, grid_config_name)

    # --- Step 3: Show launch command ---
    print("\n[bold green]Experiment run created successfully![/bold green]")
    print("You can now launch this run with a command like this:")
    print(f"  job-manager generate-jobs --project-name {project_name} cluster=<your_cluster> experiment={base_exp_config_name} grid={grid_config_name} --multirun")


@app.command(name="generate-slurm")
def generate_slurm_command(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    experiment_config: str = typer.Option(..., "--experiment-config", "-e", help="Name of the experiment config file (without .yaml)."),
    grid_config: str = typer.Option(..., "--grid-config", "-g", help="Name of the grid config file (without .yaml)."),
    cluster: str = typer.Option(..., "--cluster", "-c", help="Name of the cluster config file (without .yaml)."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Generate SLURM scripts for an experiment run without submitting them.
    """
    ensure_project_initialized(project_name)

    # ----- Load config files manually (NO multirun) -----
    conf_dir = Path("output") / project_name / "conf"
    
    experiment = OmegaConf.load(conf_dir / "experiment" / f"{experiment_config}.yaml")
    grid = OmegaConf.load(conf_dir / "grid" / f"{grid_config}.yaml")
    cluster_conf = OmegaConf.load(conf_dir / "cluster" / f"{cluster}.yaml")
    project_conf = OmegaConf.load(conf_dir / "project" / "default.yaml")

    # ----- Create output dir -----
    experiment_name = f"{experiment_config}__{grid_config}"
    slurm_output_dir = Path("output") / project_name / "slurm_runs" / experiment_name
    slurm_output_dir.mkdir(parents=True, exist_ok=True)

    # ----- Cartesian product of grid -----
    from itertools import product

    grid_keys = list(grid.keys())
    grid_values = [grid[k] for k in grid_keys]
    combinations = list(product(*grid_values))

    print(f"Generating {len(combinations)} SLURM scripts...")

    job_launcher_script = Path(__file__).parent / "job_launcher.py"

    for job_idx, combo in enumerate(combinations):

        cli_args = []
        for key, val in zip(grid_keys, combo):
            cli_args.append(f"+{key}={val}")

        command = [
            "python",
            str(job_launcher_script.resolve()),
            f"--config-dir={conf_dir}",
            "--config-name=config",
            f"experiment={experiment_config}",
            f"cluster={cluster}",
            "no_submit=True",
            f"slurm_output_dir={slurm_output_dir}",
            f"job_index={job_idx}",
        ] + cli_args

        command_str = " ".join(command)
        print(f"\n[blue]Running:[/blue] {command_str}\n")
        subprocess.run(command_str, shell=True)

    print(f"\n[green]All SLURM scripts saved into: {slurm_output_dir}[/green]")
@app.command(name="submit-slurm")
def submit_slurm_command(
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    experiment_name: str = typer.Option(..., "--experiment-name", "-en", help="The unique name of the experiment run (e.g., ppo__lr_up)."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use for submission."),
):
    """
    Submit previously generated SLURM scripts for an experiment run.
    """
    ensure_project_initialized(project_name)
    slurm_runs_dir = Path("output") / project_name / "slurm_runs" / experiment_name
    
    if not slurm_runs_dir.exists():
        print(f"[red]Error: SLURM run directory not found at {slurm_runs_dir}[/red]")
        print("Please run 'generate-slurm' first.")
        raise typer.Exit(code=1)

    scripts_to_submit = list(slurm_runs_dir.glob("*.slurm"))
    if not scripts_to_submit:
        print(f"[yellow]No .slurm files found in {slurm_runs_dir}.[/yellow]")
        raise typer.Exit()

    print(f"Found {len(scripts_to_submit)} scripts to submit from {slurm_runs_dir}.")

    if remote:
        # Remote submission
        config = load_project_config(project_name)
        if "remotes" not in config or remote not in config["remotes"]:
            print(f"Error: Remote '{remote}' not configured for project '{project_name}'.")
            raise typer.Exit(code=1)
        remote_config = config["remotes"][remote]
        
        remote_base_path = remote_config.get("remote_base_path", "~/remote-job-manager-workspace")
        remote_project_dir = f"{remote_base_path}/{project_name}"
        remote_scripts_dir = f"{remote_project_dir}/output/{project_name}/slurm_runs/{experiment_name}"
        
        print(f"Syncing project to remote '{remote}' before submission...")
        remote_manager.sync_project_to_remote(remote_config, project_name)

        for script_path in scripts_to_submit:
            remote_script_path = f"{remote_scripts_dir}/{script_path.name}"
            submit_cmd = f"sbatch {remote_script_path}"
            print(f"Submitting on remote: {submit_cmd}")
            remote_manager.run_remote_command(remote_config, submit_cmd)
    else:
        # Local submission
        for script_path in scripts_to_submit:
            submit_cmd = ["sbatch", str(script_path.resolve())]
            print(f"Submitting locally: {' '.join(submit_cmd)}")
            try:
                result = subprocess.run(submit_cmd, check=True, capture_output=True, text=True)
                print(result.stdout.strip())
            except FileNotFoundError:
                print("[red]Error: 'sbatch' command not found. Are you on a SLURM login node?[/red]")
                raise typer.Exit(code=1)
            except subprocess.CalledProcessError as e:
                print(f"[red]Error submitting job {script_path.name}:[/red]")
                print(e.stderr)


@app.command(name="generate-and-submit", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def generate_and_submit_command(
    ctx: typer.Context,
    project_name: str = typer.Option(..., "--project-name", "-n", help="The name of the project."),
    remote: str = typer.Option(None, "--remote", "-r", help="The name of the remote server to use."),
):
    """
    Generate and launch SLURM jobs using Hydra in a single step.
    
    Pass any additional arguments for Hydra after the command, e.g.:
    `... generate-and-submit --project-name my-proj cluster=my-cluster experiment=my-exp grid=my-grid --multirun`
    """
    #dispatch_to_remote_if_needed(ctx, remote, project_name)

    ensure_project_initialized(project_name)
    
    project_output_dir = Path("output") / project_name
    job_launcher_script = Path(__file__).parent / "job_launcher.py"

    if not (project_output_dir / "conf").exists():
        print(f"Error: Configuration directory not found in {project_output_dir}")
        print("Please ensure the project has been initialized correctly.")
        raise typer.Exit(code=1)

    command = [
        "python",
        str(job_launcher_script.resolve()),
    ] + ctx.args

    print("Invoking Hydra to generate and submit jobs...")
    command_str = " ".join(command)
    print(f"Command: {command_str}")
    subprocess.run(command_str, shell=True, cwd=project_output_dir)

if __name__ == "__main__":
    app()
