# Use Python slim image
FROM python:3.11-slim

# Avoid timezone prompt during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    poppler-utils \
    poppler-data \
    tesseract-ocr \
    ghostscript \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements-dev.txt .

# Install Python packages
RUN pip3 install --no-cache-dir -r requirements-dev.txt \
    && pip3 install --no-cache-dir unstructured_pytesseract pytesseract nltk

# Create directory for NLTK data and download required packages
RUN mkdir -p /usr/local/share/nltk_data && \
    python3 -m nltk.downloader -d /usr/local/share/nltk_data all

# Set environment variables
ENV NLTK_DATA=/usr/local/share/nltk_data
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Copy application code
COPY . .

# Verify NLTK data is properly installed
RUN python3 -c 'import nltk; nltk.data.path.append("/usr/local/share/nltk_data"); from nltk.tokenize import sent_tokenize; print(sent_tokenize("This is a test."))'

# Expose the port
EXPOSE 8000

# Command to run the application
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
