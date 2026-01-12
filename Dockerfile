FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_dir

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create directory for Prometheus metrics
RUN mkdir -p ${PROMETHEUS_MULTIPROC_DIR}

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ src/
COPY prompts/ prompts/
COPY scripts/ scripts/

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["gunicorn", "src.app:create_app()", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-t", "20000", "--bind", "0.0.0.0:8000"]
