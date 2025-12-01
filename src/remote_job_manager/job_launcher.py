import hydra
from omegaconf import DictConfig, OmegaConf
import submitit
from jinja2 import Environment, FileSystemLoader
from pathlib import Path

@hydra.main(config_path="conf", config_name="project")
def main(cfg: DictConfig) -> None:
    """
    Main entry point for the job launcher.
    Parses configurations, generates SLURM scripts, and submits them.
    """
    print("Hydra Configuration:\n", OmegaConf.to_yaml(cfg))

    # 1. Set up Jinja2 environment
    template_dir = Path(hydra.utils.get_original_cwd()) / "src" / "remote_job_manager" / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template("slurm.template.jinja2")

    # 2. Set up Submitit executor
    log_folder = Path(cfg.hydra.sweep.dir) / "submitit_logs"
    log_folder.mkdir(parents=True, exist_ok=True)
    
    executor = submitit.AutoExecutor(folder=log_folder)
    executor.update_parameters(
        slurm_partition=cfg.cluster.partition,
        slurm_account=cfg.cluster.account,
        timeout_min=int(cfg.cluster.time.split(':')[0]) * 60, # Simple time parsing
        nodes=1,
        gpus_per_node=cfg.cluster.num_gpus,
        tasks_per_node=1,
        cpus_per_task=cfg.cluster.cpus,
        mem_gb=int(cfg.cluster.memory.replace('G', '')),
    )

    # 3. Build the command
    # This part will be more complex, building the command from experiment config
    base_cmd = "python my_script.py"
    params = {k: v for k, v in cfg.items() if k not in ['cluster', 'project', 'hydra']}
    
    cmd_parts = [base_cmd]
    for key, value in params.items():
        cmd_parts.append(f"--{key}={value}")
    
    full_cmd = " ".join(cmd_parts)

    # 4. Render the SLURM script (optional, as Submitit can also run functions)
    slurm_script_content = template.render(
        JOB_NAME=f"{cfg.project.name}-{cfg.hydra.job.num}",
        CMD=full_cmd,
        **cfg.cluster
    )
    
    print("\n--- Generated SLURM Script ---")
    print(slurm_script_content)
    print("----------------------------\n")

    # 5. Submit the job
    # For now, we just print the script. The actual submission would be:
    # job = executor.submit(my_python_function, **params)
    # print(f"Submitted job {job.job_id}")
    
    print("Job generation complete. (Submission is currently disabled).")


if __name__ == "__main__":
    main()
