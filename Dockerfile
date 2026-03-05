# Use official Python runtime
FROM python:3.13.2-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port (Railway will set PORT environment variable)
EXPOSE 8000

# Start the application using PORT env var (Railway sets this)
# Default to 8000 if PORT not set
CMD ["sh", "-c", "uvicorn src.server:create_app --host 0.0.0.0 --port ${PORT:-8000} --factory"]
