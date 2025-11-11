import yaml
from pathlib import Path

def get_project_config_path(project_name: str) -> Path:
    """
    Returns the path to the config.yaml file for a given project.
    """
    return Path("output") / project_name / "config.yaml"

def load_project_config(project_name: str) -> dict:
    """
    Loads the config.yaml file for a given project.
    """
    config_path = get_project_config_path(project_name)
    if not config_path.exists():
        return None
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config

def save_project_config(project_name: str, config: dict):
    """
    Saves a configuration dictionary to the config.yaml file for a project.
    """
    config_path = get_project_config_path(project_name)
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
