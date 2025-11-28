import os
import yaml
from pathlib import Path
from rich import print
from itertools import product

def ensure_slurm_runs_dirs(project_name: str):
    """
    Ensures the slurm_runs directory structure exists for a given project.
    """
    base_path = Path("output") / project_name / "slurm_runs"
    (base_path / "clusters").mkdir(parents=True, exist_ok=True)
    (base_path / "experiments").mkdir(parents=True, exist_ok=True)
    (base_path / "runs").mkdir(parents=True, exist_ok=True)
    print(f"Ensured SLURM runs directory structure for project '{project_name}'.")

def load_cluster_config(project_name: str, cluster_name: str) -> dict:
    """
    Loads cluster-specific configurations from a .conf file.
    """
    config_path = Path("output") / project_name / "slurm_runs" / "clusters" / f"{cluster_name}.conf"
    if not config_path.exists():
        print(f"Error: Cluster configuration file not found at {config_path}")
        raise FileNotFoundError
    
    config = {}
    with open(config_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                config[key.strip()] = value.strip()
    return config

def load_experiment_config(project_name: str, experiment_name: str) -> tuple[dict, dict]:
    """
    Loads experiment-specific configurations (config.yaml and grid.yaml).
    """
    experiment_base_path = Path("output") / project_name / "slurm_runs" / "experiments" / experiment_name
    
    config_path = experiment_base_path / "config.yaml"
    if not config_path.exists():
        print(f"Error: Experiment config.yaml not found at {config_path}")
        raise FileNotFoundError
    
    grid_path = experiment_base_path / "grid.yaml"
    if not grid_path.exists():
        print(f"Error: Experiment grid.yaml not found at {grid_path}")
        raise FileNotFoundError

    with open(config_path, 'r') as f:
        experiment_config = yaml.safe_load(f)
    
    with open(grid_path, 'r') as f:
        grid_config = yaml.safe_load(f)
        
    return experiment_config, grid_config

def generate_grid_combinations(grid_config: dict) -> list[dict]:
    """
    Generates all combinations of parameters from the grid configuration.
    """
    keys = grid_config.keys()
    values = grid_config.values()
    
    combinations = []
    for combo in product(*values):
        combinations.append(dict(zip(keys, combo)))
    return combinations

def build_command(base_command: str, params: dict) -> str:
    """
    Constructs the shell command from the base command and a set of parameters.
    """
    cmd_parts = [base_command]
    for key, value in params.items():
        # Handle boolean flags
        if isinstance(value, bool):
            if value:
                cmd_parts.append(f"--{key}")
        else:
            cmd_parts.append(f"--{key} {value}")
    return " ".join(cmd_parts)

def render_slurm_template(template_content: str, slurm_params: dict) -> str:
    """
    Renders the SLURM template with the provided parameters.
    """
    rendered_script = template_content
    for key, value in slurm_params.items():
        rendered_script = rendered_script.replace(f"{{{{{key}}}}}", str(value))
    return rendered_script

def generate_jobs(project_name: str, cluster_name: str, experiment_name: str):
    """
    Generates SLURM job scripts for a given project, cluster, and experiment.
    """
    ensure_slurm_runs_dirs(project_name)

    # Load configurations
    cluster_config = load_cluster_config(project_name, cluster_name)
    experiment_config, grid_config = load_experiment_config(project_name, experiment_name)

    # Load SLURM template
    slurm_template_path = Path(__file__).parent / "templates" / "slurm.template"
    with open(slurm_template_path, 'r') as f:
        slurm_template_content = f.read()

    # Generate parameter combinations
    param_combinations = generate_grid_combinations(grid_config)

    # Output directory for generated runs
    runs_output_dir = Path("output") / project_name / "slurm_runs" / "runs" / cluster_name / experiment_name
    runs_output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {len(param_combinations)} SLURM jobs for experiment '{experiment_name}' on cluster '{cluster_name}'...")

    for i, params in enumerate(param_combinations):
        # Build the experiment command
        base_cmd = experiment_config.get("script", "python main.py") # Default script
        full_cmd = build_command(base_cmd, params)

        # Prepare SLURM parameters
        slurm_params = {
            "JOB_NAME": f"{experiment_name}-{i}",
            "ACCOUNT": cluster_config.get("ACCOUNT", "default_account"),
            "PARTITION": cluster_config.get("PARTITION", "debug"),
            "TIME": cluster_config.get("TIME", "00:10:00"),
            "GPU_TYPE": cluster_config.get("GPU_TYPE", ""),
            "NUM_GPUS": cluster_config.get("NUM_GPUS", 0),
            "CPUS": cluster_config.get("CPUS", 1),
            "MEMORY": cluster_config.get("MEMORY", "4G"),
            "MODULES": cluster_config.get("MODULES", ""),
            "CMD": full_cmd,
        }

        # Render SLURM script
        rendered_slurm_script = render_slurm_template(slurm_template_content, slurm_params)

        # Save SLURM script
        run_id = f"{i:04d}" # Pad with zeros for consistent naming
        output_script_path = runs_output_dir / f"run_{run_id}.slurm"
        with open(output_script_path, 'w') as f:
            f.write(rendered_slurm_script)
        print(f"Generated: {output_script_path}")

    print(f"Successfully generated SLURM jobs in {runs_output_dir}")
