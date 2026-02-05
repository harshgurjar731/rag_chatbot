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

# Install uv
RUN pip install --no-cache-dir --upgrade pip uv

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies from requirements.txt
RUN uv pip install --system -r requirements.txt

# Stage 2: Runtime - Minimal image with only runtime dependencies
FROM continuumio/miniconda3:latest

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /opt/conda/lib/python3.13/site-packages /opt/conda/lib/python3.13/site-packages
COPY --from=builder /opt/conda/bin /opt/conda/bin

# Copy application code (this changes most frequently, so keep it late)
COPY . .

# Install runtime binary dependencies (ffmpeg)
# We install here to ensure shared libraries are properly linked in the runtime environment
RUN conda install -y -c conda-forge ffmpeg && conda clean -a -y

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Expose port
EXPOSE 8000

# Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
