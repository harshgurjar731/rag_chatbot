# Multi-stage build for optimal image size
# Stage 1: Builder - Install dependencies with compilers
FROM continuumio/miniconda3:latest AS builder

WORKDIR /build

# Install build dependencies via conda (no apt needed)
RUN conda install -y -c conda-forge \
    gcc_linux-64 \
    gxx_linux-64 \
    && conda clean -a -y

# Set compiler environment variables
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++ \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Copy requirements first (better caching)
COPY requirements.txt .

# Install uv and dependencies
RUN pip install --no-cache-dir --upgrade pip uv && \
    uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system --no-cache -r requirements.txt

# Stage 2: Runtime - Minimal image with only runtime dependencies
FROM continuumio/miniconda3:latest

WORKDIR /app

# Install only runtime system dependencies via conda
RUN conda install -y -c conda-forge \
    tesseract \
    poppler \
    ghostscript \
    && conda clean -a -y

# Copy installed packages from builder
COPY --from=builder /opt/conda/lib/python3.13/site-packages /opt/conda/lib/python3.13/site-packages
COPY --from=builder /opt/conda/bin /opt/conda/bin

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)" || exit 1

# Command to run the application (remove --reload for production)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
