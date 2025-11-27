#!/bin/bash
set -e
echo "Creating test directory..."
mkdir -p {{remote_test_dir}}
cd {{remote_test_dir}}

repo_name=$(basename {{repo_url}} .git)
if [ ! -d "$repo_name" ]; then
    echo "Cloning repository..."
    git clone {{repo_url}} .
else
    echo "Repository '$repo_name' already exists, skipping clone."
fi

if [ ! -f ".dataset_downloaded" ]; then
    echo "Downloading dataset..."
    {{dataset_command}}
    touch .dataset_downloaded
else
    echo "Dataset already downloaded, skipping."
fi

echo "---- Remote test environment setup complete ----"
