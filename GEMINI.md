# Project Guide: Remote Job & Container Manager

## 1. Goal

The primary goal of this project is to create a Python command-line tool that automates and simplifies the management of remote jobs and containerized experiments. This tool will streamline the process of building Docker images, converting them to the Singularity format, and submitting them as jobs to SLURM-managed high-performance computing (HPC) clusters.

## 2. Core Principles & Patterns

1.  **Modularity and Separation of Concerns:** The tool will be divided into distinct modules for each core function: Docker building, Singularity conversion, and SLURM submission. This makes the codebase easier to maintain, test, and extend.
2.  **Configuration as Code:** Job specifications, build parameters, and cluster details will be defined in declarative YAML configuration files. This allows users to version control their experimental setups and ensures reproducibility.
3.  **Command-Line First Interface:** The primary user interaction will be through a clean and intuitive CLI, built using a modern Python library like `Typer` or `Click` for self-documenting commands and options.
4.  **Extensibility:** The architecture will be designed to allow future expansion, such as adding support for other container runtimes (e.g., Podman) or different job schedulers (e.g., LSF, PBS).
5.  **Best Practices in Packaging:** The project will follow modern Python packaging standards using `pyproject.toml` and a `src` layout to ensure it can be reliably packaged and distributed.

## 3. Proposed Folder Structure

```
remote-job-manager/
├── .gitignore
├── GEMINI.md           # This project guide
├── LICENSE
├── README.md           # User-facing documentation
├── pyproject.toml      # Project metadata and dependencies (PEP 621)
├── docs/               # Detailed documentation (e.g., Sphinx)
│   └── ...
├── examples/           # Example configuration files and use cases
│   └── simple_job.yaml
├── output/             # Default directory for project outputs
│   └── <project_name>/
│       ├── Dockerfile
│       ├── requirements.txt
│       ├── slurm_runs/
│       │   └── <experiment_name>/
│       │       ├── job_0.slurm
│       │       └── ...
│       └── conf/
│           ├── project.yaml      # Project-level defaults
│           ├── cluster/          # Cluster configurations for this project
│           │   └── my-cluster.yaml
│           ├── experiment/       # Experiment configurations
│           │   └── my-experiment.yaml
│           └── grid/             # Grid search configurations
│               └── my-grid.yaml
└── src/
    └── remote_job_manager/
        ├── __init__.py
        ├── cli.py          # Main CLI application (Typer/Click)
        ├── config.py       # Configuration loading and validation
        ├── docker_utils.py # Docker-related utility functions
        ├── job_launcher.py # Hydra-based job launcher
        ├── remote.py       # Logic for remote execution via SSH/rsync
        ├── singularity_utils.py # Singularity-related utility functions
        ├── slurm_submitter.py # Logic for generating and submitting SLURM scripts
        ├── templates/
        │   ├── Dockerfile.template
        |   ├── prepare_remote_test_env.sh
        │   └── slurm.template.jinja2
        ├── utils.py        # General helper functions
        └── web_utils.py    # Web-related utility functions

Global cluster configurations are stored in `~/.config/remote-job-manager/clusters/`.
```
**Example `project.yaml` structure:**
```yaml
general:
  project_name: my-project
test:
  repo_url: "https://github.com/user/repo.git"
  dataset_command: |
    wget -O dataset.zip https://example.com/dataset.zip
    unzip dataset.zip
  run_command: |
    python main.py --data_dir=<YOUR_DATA_DIRECTORY>/unzipped_dataset
  gpus: true
  wandb_mode: "offline"

```
**Example `my-cluster.yaml` structure:**
```yaml
slurm:
  account: default_account
  partition: debug
  time: 00:10:00
  gpu_type: a1000l
  num_gpus: 1
  cpus: 1
  memory: 32G
  modules: []
remote:
  host: login.server.mila.quebec
  user: mayorw
  port: 2222
  remote_base_path: ~/remote-job-manager-workspace

```
**Example `Dockerfile.template` with LABEL:**
```Dockerfile
# Python base image
FROM python:3.9-slim
LABEL created_by="remote_job_manager"

# Set working directory
WORKDIR /{{ project_name }}

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Command to run the application
CMD ["python", "app.py"]
```

## 4. To-Do List

### Current Tasks (Initial Setup)

1.  [x] **Initialize Project Structure:** Create the complete folder and file structure as outlined above.
2.  [x] **Setup `pyproject.toml`:** Define project metadata and add initial dependencies like `typer`, `pyyaml`, and `rich`.
3.  [x] **Create `.gitignore`:** Add standard Python ignores (`__pycache__/`, `.venv/`, `dist/`, etc.) and project-specific ones.
4.  [x] **Implement Basic CLI:** In `cli.py`, set up the main command entry points (e.g., `build`, `convert`, `submit`) without full implementation.
5.  [x] **Implement Configuration Loading:** In `config.py`, create a function to load and parse the `job.yaml` files.
6.  [x] **Draft `README.md`:** Write an initial version of the `README.md` with a project description and basic usage instructions.

### Future Tasks (Feature Implementation)

1.  [x] **Implement Project Initialization:** Flesh out the `init` command to interactively create a structured `config.yaml` file for each project, with a conditional prompt for test, GPU, and W&B information.
2.  [x] **Implement Project Configuration:** Implement the `configure` command to allow users to update the project configuration, including GPU and W&B support.
3.  [x] **Implement Dockerfile Template Command:** Flesh out the `template` command in `cli.py` to generate a customizable Dockerfile and an empty `requirements.txt` file from a template.
4.  [x] **Implement Docker Builder:** Flesh out `docker_builder.py` to execute `docker build` commands using the system's Docker daemon.
5.  [x] **Implement Docker Tester:** Implement the `test` command, which uses utility functions to clone a repo, download a dataset, and run a test command with GPU support (using the NVIDIA Container Runtime).
6.  [x] **Implement Image Lister:** Implement the `list-images` command to list all Docker images created by this tool.
7.  [x] **Implement Interactive Fix and Rerun:** Implement the `fix-and-rerun` command to provide a robust, interactive session for debugging dependencies that does not exit on errors.
8.  [x] **Implement Singularity Converter:** Implement the logic in `singularity_converter.py` to pull a Docker image and build a Singularity image from it.
9.  [x] **Implement Singularity Tester:** Implement the `test-singularity` command to run the test configuration inside a converted Singularity image.
10. [x] **Implement Remote Execution:** Add the ability to execute commands on remote servers via SSH, with project-specific remote configurations managed in `config.yaml`.
11. [x] **Implement `setup-remote-test-env` command:** A command to prepare a test environment on a remote server by copying files from the local host.
12. [x] **Implement `shell` command:** A command to get an interactive shell inside a Docker container and persist changes.
13. [ ] **Implement Hydra-based Experiment System:** Overhaul the experiment generation and submission system using Hydra, Submitit, and Jinja2.
    *   [x] Add `hydra-core`, `submitit`, and `Jinja2` to dependencies.
    *   [x] Create `add-cluster` command for managing global cluster configurations.
    *   [x] Create `add-experiment-config` command for creating base experiment configurations.
    *   [x] Create `add-grid-config` command for creating grid search configurations.
    *   [ ] Implement `generate-slurm` command for script generation.
    *   [ ] Implement `submit-slurm` command for job submission.
    *   [ ] Rename `generate-jobs` to `generate-and-submit`.
    *   [ ] Modify `job_launcher.py` to support `--no-submit` flag.
    *   [x] Update `init` command to select from global cluster configs.
    *   [x] Implement Hydra-based job launcher (`job_launcher.py`).
    *   [x] Update `generate-jobs` command to invoke the Hydra launcher.
14. [ ] **Implement SLURM Submitter:** Develop the `slurm_submitter.py` module to generate `sbatch` scripts from a template and submit them using `sbatch`.
15. [ ] **Add Testing Framework:** Set up `pytest` and write initial unit tests for the configuration loader and CLI stubs.
16. [ ] **Implement Logging:** Integrate structured logging throughout the application to provide clear feedback to the user.
17. [ ] **Add Validation:** Implement robust validation for the configuration files to catch errors early.
18. [ ] **Develop Documentation:** Create comprehensive documentation in the `docs/` folder explaining advanced usage, configuration options, and architecture.
19. [ ] **Package for Distribution:** Ensure the project can be built and published to PyPI.

## 5. Remote Execution

The `job-manager` tool now supports executing commands on remote servers via SSH. This allows you to manage your containerized experiments on HPC clusters or other remote machines directly from your local workstation.

### How it Works

1.  **Configuration:** Remote server details (hostname, username, port, and `remote_base_path`) are configured within your project's `conf/cluster/my-cluster.yaml` file. This makes remote configurations project-specific and version-controllable.
2.  **File Synchronization:** When you execute a remote command, the local `output/<project_name>` directory is automatically synchronized with a corresponding directory on the remote server using `rsync`. This ensures that your remote `job-manager` instance has access to the latest project files (e.g., Dockerfiles, `config.yaml`, cloned repositories). The remote project directory will be located at `<remote_base_path>/<project_name>`.
3.  **Remote Command Dispatch:** The local `job-manager` then dispatches the requested command to the remote server via SSH. The remote server executes its own `job-manager` command, and the output is streamed back to your local terminal.

### Configuring Remotes

You can configure remotes when initializing a new project (`job-manager init`) or by using the `job-manager add-cluster` 

**Example `my-cluster.yaml` structure:**
```yaml
slurm:
  account: default_account
  partition: debug
  time: 00:10:00
  gpu_type: a1000l
  num_gpus: 1
  cpus: 1
  memory: 32G
  modules: []
remote:
  host: login.server.mila.quebec
  user: mayorw
  port: 2222
  remote_base_path: ~/remote-job-manager-workspace

```

### Using the `--remote` Flag

To execute any command on a remote server, simply add the `--remote <remote_name>` flag, where `<remote_name>` is the name you configured in your project's `my-cluster.yaml`.

## 6. How to Run CLI Commands

To simplify the command-line invocation, you can install the project in editable mode. This will create a `job-manager` script in your environment, allowing you to run the commands directly.

**1. Installation:**

Navigate to the project's root directory and run the following command:

```bash
pip install -e .
```

**2. Running Commands:**

Once the package is installed, you can use the `job-manager` command directly:

```bash
job-manager <command> [options]
```

**Examples:**

*   **Initialize a new project (interactive):**
    ```bash
    job-manager init --project-name my-new-project
    ```
*   **Configure an existing project (interactive):**
    ```bash
    job-manager configure --project-name my-new-project
    ```
*   **Generate a Dockerfile template:**
    ```bash
    job-manager template --project-name my-new-project
    ```
*   **Build a container image:**
    ```bash
    job-manager build --project-name my-new-project
    ```
*   **Test a container image:**
    ```bash
    job-manager test --project-name my-new-project
    ```
*   **Convert a Docker image to Singularity:**
    ```bash
    job-manager convert --project-name my-new-new-project
    ```
*   **Test a Singularity image:**
    ```bash
    job-manager test-singularity --project-name my-new-project
    ```
*   **List container images created by this tool:**
    ```bash
    job-manager list-images
    ```
*   **Interactively fix and rerun a test:**
    ```bash
    job-manager fix-and-rerun --project-name my-new-project
    ```
*   **Build a container image on a remote server:**
    ```bash
    job-manager build --project-name my-new-project --remote my-cluster
    ```
*   **Test a Singularity image on a remote server:**
    ```bash
    job-manager test-singularity --project-name my-new-project --remote my-cluster
    ```
*   **Prepare a remote test environment:**
    ```bash
    job-manager setup-remote-test-env --project-name my-new-project --remote my-cluster
    ```
*   **Start an interactive shell in a Docker image:**
    ```bash
    job-manager shell --project-name my-new-project
    ```
*   **Add a new global cluster configuration:**
    ```bash
    job-manager add-cluster
    ```
*   **Add a new base experiment configuration:**
    ```bash
    job-manager add-experiment-config --project-name my-new-project
    ```
*   **Add a new grid search configuration:**
    ```bash
    job-manager add-grid-config --project-name my-new-project
    ```
*   **Generate SLURM scripts for an experiment run:**
    ```bash
    job-manager generate-slurm --project-name my-new-project --experiment-config ppo --grid-config lr_up --cluster my-cluster
    ```
*   **Submit the generated SLURM scripts for an experiment run:**
    ```bash
    job-manager submit-slurm --project-name my-new-project --experiment-name ppo__lr_up --remote my-cluster
    ```
*   **Generate and launch SLURM jobs in one step:**
    ```bash
    job-manager generate-and-submit --project-name my-new-project cluster=my-cluster experiment=bert grid=lr_sweep --multirun
    ```
*   **Get help for a command:**
    ```bash
    job-manager --help
    job-manager template --help
    ```

## 7. Experiment Generation with Hydra and Submitit

The experiment generation and submission system is built on a powerful stack of open-source tools: **Hydra** for configuration management, **Jinja2** for script templating, and **Submitit** for launching jobs on SLURM clusters.

### Architecture Overview

This architecture provides a highly flexible and scalable way to define and run experiments.

1.  **Core Tools**:
    *   **Hydra**: Manages all configuration layers—cluster settings, project defaults, experiment parameters, and grid sweeps—acting as the central configuration system.
    *   **Jinja2**: Generates the SLURM scripts from a clean template (`slurm.template.jinja2`), serving as the template engine.
    *   **Submitit**: Submits the generated SLURM scripts or Python functions directly to the SLURM scheduler from within Python, acting as the job launcher.

2.  **Configuration Hierarchy**:
    Configurations are composed from multiple files, with values from later layers overriding earlier ones. The merge order is:
    `Global Cluster Config` → `Project Config` → `Experiment Config` → `Grid Overrides`

3.  **Configuration Locations**:
    *   **Global Cluster Configs**: Stored in `~/.config/remote-job-manager/clusters/`. These are YAML files defining cluster-specific parameters (e.g., account, partition, modules) and are shared across all projects. A new cluster can be added using the `add-cluster` command.
    *   **Project Configs**: Each project has a `conf/` directory within its `output/<project_name>/` folder.
        *   `conf/project.yaml`: Defines project-level defaults and settings.
        *   `conf/cluster/`: Contains project-specific cluster configurations or overrides.
        *   `conf/experiment/`: Holds reusable base experiment configurations (e.g., `bert.yaml`, `resnet.yaml`), created with the `add-experiment-config` command.
        *   `conf/grid/`: Holds reusable grid search configurations (e.g., `lr_sweep.yaml`, `full_grid.yaml`), created with the `add-grid-config` command.

4.  **Job Workflow**:
    The tool supports a two-step workflow for validating and launching jobs, providing greater control and visibility.

    *   **Step 1: Generate SLURM Scripts (`generate-slurm`)**
        *   An experiment run is defined by a unique name created from the combination of an experiment config and a grid config: `<experiment_config_name>__<grid_config_name>`.
        *   The `generate-slurm` command composes the full configuration and invokes the `job_launcher.py` script with a `--no-submit` flag.
        *   The launcher generates a SLURM script for each job in the hyperparameter sweep and saves them to `output/<project_name>/slurm_runs/<experiment_name>/`.
        *   This allows you to inspect and validate the generated scripts before submission.

    *   **Step 2: Submit SLURM Scripts (`submit-slurm`)**
        *   Once you have validated the scripts, the `submit-slurm` command is used to submit them.
        *   It takes the experiment name, finds the corresponding directory in `slurm_runs/`, and submits each `.slurm` file using `sbatch`.

    *   **Convenience Command (`generate-and-submit`)**
        *   For quick iteration, the `generate-and-submit` command combines both steps into one, launching the jobs immediately without saving the intermediate scripts for validation.
