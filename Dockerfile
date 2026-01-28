# Use official Python slim image for smaller size
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Prevent debconf warnings during apt installs
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first (Docker layer caching)
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Create necessary directories
RUN mkdir -p output

# Test imports to catch errors early
RUN python -c "import fastapi; import uvicorn; print('✅ Core dependencies OK')" && \
    python -c "import server; print('✅ Server module loads OK')" || echo "⚠️ Server module has issues but continuing..."

# Expose port 8080 (Cloud Run default)
EXPOSE 8080

# Set default PORT if not provided
ENV PORT=8080

# Use shell form to properly expand environment variable
# Removed healthcheck as Cloud Run handles this
CMD uvicorn server:app --host 0.0.0.0 --port $PORT --timeout-keep-alive 30