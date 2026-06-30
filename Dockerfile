# Use official Python 3.11 slim image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# Install system dependencies (ffmpeg is required for audio processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    unzip \
    wget \
    build-essential \
    cmake \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download Vosk Model automatically during build (Small Hindi model recommended for general purpose)
RUN mkdir -p /app/model && \
    wget -qO model.zip https://alphacephei.com/vosk/models/vosk-model-small-hi-0.22.zip && \
    unzip -q model.zip && \
    mv vosk-model-small-hi-0.22/* /app/model/ && \
    rm -rf model.zip vosk-model-small-hi-0.22

# Copy the rest of the application
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Start the application
CMD ["python", "main.py"]
