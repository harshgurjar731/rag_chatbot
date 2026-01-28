# Single-stage build to ensure consistent Python environment
FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies & Python 3.11 via conda
# Python 3.11 is required for numpy<2 wheels and legacy ML lib compatibility
RUN conda install -y -c conda-forge \
    python=3.11 \
    gcc_linux-64 \
    gxx_linux-64 \
    tesseract \
    poppler \
    ghostscript \
    && conda clean -a -y

# Set paths and envs
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++ \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/opt/conda/bin:${PATH}"

# Install uv
RUN pip install --no-cache-dir --upgrade pip uv

# Install Dependencies with Strict Pinning
# We group these to ensure the resolver sees all constraints at once
# Install Dependencies with Strict Pinning
# Install Dependencies with Strict Pinning
# Use pip because uv cannot find the packages in the registry
# 2. Install Core ML Stack with relaxed but safe constraints
# Relaxing strict equality (==) to ranges prevents dependency hell/backtracking
RUN pip install --no-cache-dir \
    "numpy<2" \
    "huggingface-hub>=0.23.0,<1.0" \
    "transformers>=4.39.3,<5.0.0" \
    "sentence-transformers==2.7.0" \
    "langchain-huggingface" \
    "onnxruntime"

# 3. Install Vector Stores & Guardrails (Separate step to ease resolution)
RUN pip install --no-cache-dir \
    chromadb \
    qdrant_client \
    langchain-chroma \
    langchain-qdrant \
    nemoguardrails

# File Processing
RUN uv pip install --system \
    beautifulsoup4 \
    camelot_py \
    fitz \
    PyMuPDF \
    pytesseract \
    Pillow \
    opencv-python-headless \
    python-multipart \
    pdf2image \
    scikit-learn \
    ragas

# Common Utils
RUN uv pip install --system \
    fastapi \
    uvicorn \
    requests \
    redis \
    psycopg2-binary \
    sqlmodel \
    python-dotenv \
    aiofiles \
    pandas \
    pydantic-settings

# LangChain Basic
RUN uv pip install --system \
    langchain \
    langchain-core \
    langchain-community \
    langchain-text-splitters \
    langchain-openai \
    langchain-experimental \
    langchain-nvidia-ai-endpoints \
    openinference-instrumentation-langchain \
    openinference-instrumentation-openai

# Copy application code
COPY . .

# Command
CMD ["python", "main.py"]
