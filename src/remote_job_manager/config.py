import yaml

def load_config(config_path: str) -> dict:
    """
    Loads a YAML configuration file.

    Args:
        config_path: The path to the YAML configuration file.

    Returns:
        A dictionary containing the configuration.
    """
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    return config
