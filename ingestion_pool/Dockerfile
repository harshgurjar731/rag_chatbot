# Single-stage build to ensure consistent Python environment
FROM continuumio/miniconda3:latest

WORKDIR /app

# Configure conda for slow networks
RUN conda config --set remote_read_timeout_secs 600 && \
    conda config --set remote_max_retries 5

# Install system dependencies & Python 3.11 via conda
# Python 3.11 is required for numpy<2 wheels and legacy ML lib compatibility
RUN conda install -y -c conda-forge \
    python=3.11 \
    gcc_linux-64 \
    gxx_linux-64 \
    poppler \
    ghostscript \
    && conda clean -a -y

# Set paths and envs
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++ \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Install uv (optional, keeping it if we want to use it, but mainly using pip for safety per previous comments)
RUN pip install --no-cache-dir --upgrade pip uv

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies from requirements.txt
# Using pip directly to avoid potential registry issues with uv for some ML packages
RUN pip install --no-cache-dir -r requirements.txt

# Install Azure Document Intelligence separately to leverage cache for requirements.txt
RUN pip install --no-cache-dir azure-ai-documentintelligence

# Copy application code
COPY . .

# Command
CMD ["python", "main.py"]
