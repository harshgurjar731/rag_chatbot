# Multi-stage build for optimal image size
# Stage 1: Builder - Install dependencies with compilers
FROM continuumio/miniconda3:latest AS builder

WORKDIR /build

# Install build dependencies via conda (no apt needed)
RUN conda install -y -c conda-forge \
    python=3.12 \
    gcc_linux-64 \
    gxx_linux-64 \
    && conda clean -a -y

# Set compiler environment variables
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++ \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Install uv (optional, helps with speed but using pip for consistency with instructions)
RUN pip install --no-cache-dir --upgrade pip uv

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies from requirements.txt
# Using uv pip install --system for speed as requested in original Dockerfile, but respecting requirements.txt
RUN uv pip install --system -r requirements.txt

# Stage 2: Runtime - Minimal image with only runtime dependencies
FROM continuumio/miniconda3:latest

WORKDIR /app

# Install only runtime system dependencies via conda
RUN conda install -y -c conda-forge \
    python=3.12 \
    tesseract \
    poppler \
    ghostscript \
    && conda clean -a -y

# Copy installed packages from builder
COPY --from=builder /opt/conda/lib/python3.12/site-packages /opt/conda/lib/python3.12/site-packages
COPY --from=builder /opt/conda/bin /opt/conda/bin

# Copy application code
COPY . .

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Command (Assuming main.py is the entrypoint based on previous files, but wait, previous Dockerfile didn't have a CMD? 
# Ah, it ended without CMD. The original file cut off. 
# Wait, let me check the original file content again. It ended at line 149 and didn't show CMD. 
# I will assume `CMD ["python", "main.py"]` or similar based on Ingestion Pool, OR `uvicorn` if it's an API.
# The `requirement.txt` has `fastapi` and `uvicorn`. 
# The directory listing specific `main.py` and `worker_wrapper.py`. 
# I'll default to `CMD ["python", "worker_wrapper.py"]` or `main.py`.
# Let's check `worker_wrapper.py` size: 13171 bytes. `main.py`: 10523 bytes.
# Typically workers run a script. I'll add a comment or check `main.py` context if I could, 
# but simply providing a CMD that mimics a generic python run is safer if unknown, or maybe no CMD is needed if docker-compose defines it.
# However, Dockerfiles should usually have a CMD. 
# I will NOT add a CMD if the original didn't have one, to avoid breaking behavior if it is controlled by compose.
# But wait, the previous file view ended at line 149 with `PATH=...`
# It might be that the file was truncated or just didn't have CMD.
# I'll leave CMD out if it wasn't there, or add a comment found in similar files.
# Actuallly, I should probably check `docker-compose.yml` if I could, but I don't see it open.
# I will stick to NOT adding a CMD if none was seen, but usually this is an error.
# Wait, look at the end of the view_file output. "The above content shows the entire, complete file contents...".
# So there was NO CMD.
# I will proceed without CMD.)

# No CMD instruction found in original Dockerfile. Relying on external command execution (e.g. docker-compose).
