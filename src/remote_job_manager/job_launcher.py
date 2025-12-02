import hydra
from hydra.core.hydra_config import HydraConfig
from omegaconf import DictConfig, OmegaConf
from jinja2 import Environment, FileSystemLoader
from pathlib import Path
import os


# ------------------------------
#  Helpers
# ------------------------------

HYDRA_INTERNAL_KEYS = {
    "hydra",
    "_hydra_enable_legacy_struct_",
    "no_submit",
    "slurm_output_dir",
    "project",
    "cluster",
    "experiment",
    "job_index",
    "grid",
}

def load_template():
    """Load the Jinja2 SLURM template from the project directory."""
    original_cwd = Path(hydra.utils.get_original_cwd())
    template_dir = original_cwd / "src" / "remote_job_manager" / "templates"
    env = Environment(loader=FileSystemLoader(template_dir))
    return env.get_template("slurm.template.jinja2")


def extract_params(cfg: DictConfig) -> dict:
    """Extract experiment parameters + grid parameters, excluding Hydra internals."""
    params = {}

    # experiment defaults
    params.update(OmegaConf.to_container(cfg.experiment, resolve=True))

    # everything else inside cfg (grid params)
    for key, value in cfg.items():
        if key not in HYDRA_INTERNAL_KEYS:
            params[key] = value

    params.pop("script", None)
    return params


def build_command(base_cmd: str, params: dict) -> str:
    """Convert parameters into CLI flags."""
    flags = [f"--{k}={v}" for k, v in params.items()]
    return base_cmd + " " + " ".join(flags)


# ------------------------------
#  Main Hydra Entry Point
# ------------------------------
@hydra.main(version_base=None, config_path=None)
def main(cfg: DictConfig) -> None:

    OmegaConf.set_struct(cfg, False)

    # Job index (supplied manually)
    job_index = int(cfg.get("job_index", 0))

    # Load template
    template = load_template()

    # Extract CLI parameters
    params = extract_params(cfg)

    # Build command
    cmd = build_command(cfg.experiment.script, params)

    # Render SLURM
    slurm_text = template.render(
        job_name=f"{cfg.project.general.project_name}-{job_index}",
        cmd=cmd,
        **cfg.cluster.slurm
    )

    # Output
    outdir = Path(cfg.slurm_output_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    script_path = outdir / f"job_{job_index}.slurm"

    script_path.write_text(slurm_text)
    print(f"Generated SLURM file: {script_path}")


if __name__ == "__main__":
    main()
