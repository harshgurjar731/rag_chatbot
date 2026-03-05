# Single-stage build to ensure consistent Python environment
FROM continuumio/miniconda3:latest

WORKDIR /app

# Configure conda for slow networks
RUN conda config --set remote_read_timeout_secs 600 && \
    conda config --set remote_max_retries 5

# Install system dependencies & Python 3.11 via conda
RUN conda install -y -c conda-forge \
    python=3.11 \
    gcc_linux-64 \
    gxx_linux-64 \
    && conda clean -a -y

# Set paths and envs
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++ \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Install uv and pip
RUN pip install --no-cache-dir --upgrade pip uv

# Copy requirements first (better caching)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install synthetic-data-kit
RUN pip install --no-cache-dir synthetic-data-kit

# Install missing dependency for local version (optimized cache)
RUN pip install --no-cache-dir pylance pymupdf python-docx python-pptx youtube-transcript-api

# Copy application code
COPY . .

# Command
CMD ["python", "evaluation_worker.py"]
