from pathlib import Path

def add_wandb_volumes(docker_run_cmd: list, wandb_mode: str) -> list:
    if wandb_mode:
        docker_run_cmd.extend(["-e", f"WANDB_MODE={wandb_mode}"])
        if wandb_mode == "online":
            home_dir = Path.home()
            wandb_config = home_dir / ".config" / "wandb"
            netrc = home_dir / ".netrc"
            if wandb_config.exists():
                docker_run_cmd.extend(["-v", f"{wandb_config}:/root/.config/wandb"])
            if netrc.exists():
                docker_run_cmd.extend(["-v", f"{netrc}:/root/.netrc"])
    
    return docker_run_cmd