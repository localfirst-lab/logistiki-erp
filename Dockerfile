# =====================================================================
#   LogistiKI ERP — Production Dockerfile
#   AI-first WMS & Paperless Logistics Platform
#   Author: Davide Carrieri (Simbio Ecosystem)
# =====================================================================

FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5055 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies (OCR, PDF rendering, graphics libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-deu \
    tesseract-ocr-ita \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Expose ERP service port
EXPOSE 5055

# Healthcheck to verify the server is answering
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5055/ || exit 1

# Start LogistiKI ERP
CMD ["python", "app.py"]
