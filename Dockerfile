# Production Dockerfile for GutBut Health Ingestion & RAG System
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency specifications
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Download required NLTK tokenizers
RUN python -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

# Copy project code
COPY . .

# Expose Web UI port
EXPOSE 8000

# Default entry point: Launch the Web UI
CMD ["python", "web_ui.py", "8000"]

