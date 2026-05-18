# Use an official lightweight Python runtime
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8443

# Set the working directory
WORKDIR /app

# Install system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY src/ ./src/

# Create a data directory for the SQLite database
RUN mkdir -p /app/data

# Expose the server port
EXPOSE 8443

# Start uvicorn server
CMD ["sh", "-c", "uvicorn src.webhook:app --host 0.0.0.0 --port ${PORT}"]
