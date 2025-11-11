
# NVIDIA base image
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Set working directory
WORKDIR /nano

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Command to run the application
CMD ["python", "app.py"]
