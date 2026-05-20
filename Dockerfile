FROM python:3.11-slim

# Set environment variables to prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install system dependencies needed for Curl and package updates
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and download Chromium with its required system dependencies
RUN playwright install chromium --with-deps

# Copy application directories into the container workspace
COPY scripts/ /app/scripts/
COPY reports/ /app/reports/
COPY docs/ /app/docs/

# Expose PYTHONPATH to support absolute imports under the scripts folder
ENV PYTHONPATH=/app/scripts

# Execute the pipeline orchestrator by default
CMD ["python", "scripts/src/main.py"]
