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
│       ├── config.yaml
│       ├── Dockerfile
│       └── requirements.txt
└── src/
    └── remote_job_manager/
        ├── __init__.py
        ├── cli.py          # Main CLI application (Typer/Click)
        ├── config.py       # Configuration loading and validation
        ├── docker_builder.py # Logic for building Docker images
        ├── docker_utils.py # Docker-related utility functions
        ├── singularity_converter.py # Logic for Docker-to-Singularity conversion
        ├── slurm_submitter.py # Logic for generating and submitting SLURM scripts
        ├── templates/
        │   └── Dockerfile.template
        ├── utils.py        # General helper functions
        └── web_utils.py    # Web-related utility functions
```
**Example `config.yaml` structure:**
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

1.  [x] **Implement Project Initialization:** Flesh out the `init` command to interactively create a structured `config.yaml` file for each project, with a conditional prompt for test and GPU information.
2.  [x] **Implement Project Configuration:** Implement the `configure` command to allow users to update the project configuration, including GPU support.
3.  [ ] **Implement Dockerfile Template Command:** Flesh out the `template` command in `cli.py` to generate a customizable Dockerfile and an empty `requirements.txt` file from a template.
4.  [x] **Implement Docker Builder:** Flesh out `docker_builder.py` to execute `docker build` commands using the system's Docker daemon.
5.  [x] **Implement Docker Tester:** Implement the `test` command, which uses utility functions to clone a repo, download a dataset, and run a test command with GPU support (using the NVIDIA Container Runtime), placeholder replacement, and correct file permissions.
6.  [x] **Implement Image Lister:** Implement the `list-images` command to list all Docker images created by the tool.
7.  [x] **Implement Interactive Fix and Rerun:** Implement the `fix-and-rerun` command to provide a robust, interactive session for debugging dependencies that does not exit on errors.
8.  [ ] **Implement Singularity Converter:** Implement the logic in `singularity_converter.py` to pull a Docker image and build a Singularity image from it.
9.  [ ] **Implement SLURM Submitter:** Develop the `slurm_submitter.py` module to generate `sbatch` scripts from a template and submit them using `sbatch`.
10. [ ] **Add Testing Framework:** Set up `pytest` and write initial unit tests for the configuration loader and CLI stubs.
11. [ ] **Implement Logging:** Integrate structured logging throughout the application to provide clear feedback to the user.
12. [ ] **Add Validation:** Implement robust validation for the configuration files to catch errors early.
13. [ ] **Develop Documentation:** Create comprehensive documentation in the `docs/` folder explaining advanced usage, configuration options, and architecture.
14. [ ] **Package for Distribution:** Ensure the project can be built and published to PyPI.

## 5. How to Run CLI Commands

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
*   **List container images created by this tool:**
    ```bash
    job-manager list-images
    ```
*   **Interactively fix and rerun a test:**
    ```bash
    job-manager fix-and-rerun --project-name my-new-project
    ```
*   **Get help for a command:**
    ```bash
    job-manager --help
    job-manager template --help
    ```
