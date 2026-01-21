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
# COPY requirements.txt .

# Install uv and dependencies
RUN pip install --no-cache-dir --upgrade pip uv && \
    uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu

RUN uv pip install --system beautifulsoup4
RUN uv pip install --system camelot_py
RUN uv pip install --system chromadb
RUN uv pip install --system deep_translator
RUN uv pip install --system Evaluation
RUN uv pip install --system faiss_cpu
RUN uv pip install --system fastapi
RUN uv pip install --system fitz
RUN uv pip install --system groq
RUN uv pip install --system langchain_chroma
RUN uv pip install --system langchain_classic
RUN uv pip install --system langchain_community
RUN uv pip install --system langchain_core
RUN uv pip install --system langchain_experimental
RUN uv pip install --system langchain_huggingface
RUN uv pip install --system langchain_openai
RUN uv pip install --system langchain_qdrant
RUN uv pip install --system langchain_text_splitters
RUN uv pip install --system mistralai
RUN uv pip install --system nemoguardrails
RUN uv pip install --system numpy
RUN uv pip install --system openai
RUN uv pip install --system phoenix
RUN uv pip install --system Pillow
RUN uv pip install --system pydantic
RUN uv pip install --system pymupdf
RUN uv pip install --system pytesseract
RUN uv pip install --system python-dotenv
RUN uv pip install --system qdrant_client
RUN uv pip install --system Requests
RUN uv pip install --system sentence_transformers
RUN uv pip install --system sqlmodel
RUN uv pip install --system tqdm
RUN uv pip install --system transformers
# RUN uv pip install --system openinference
RUN uv pip install --system openinference.instrumentation.langchain
RUN uv pip install --system openinference.instrumentation.openai
RUN uv pip install --system python-multipart
RUN uv pip install --system guardrails-ai
RUN uv pip install --system arize-phoenix
RUN uv pip install --system arize-phoenix-evals
RUN uv pip install --system langchain-nvidia-ai-endpoints
RUN uv pip install --system numpy
RUN uv pip install --system pandas 
RUN uv pip install --system dotenv
RUN uv pip install --system python-multipart
RUN uv pip install --system camelot-py
RUN uv pip install --system huggingface-hub
RUN uv pip install --system nvidia-riva-client
RUN uv pip install --system opencv-python-headless
RUN uv pip install --system pdf2image
RUN uv pip install --system pillow
RUN uv pip install --system pydantic
RUN uv pip install --system sentence_transformers
RUN uv pip install --system scikit-learn
RUN uv pip install --system ragas
COPY Evaluation/synthetic_data_kit /build/synthetic_data_kit
RUN uv pip install --system /build/synthetic_data_kit




RUN uv pip install --system uvicorn
RUN uv pip install --system python-multipart
RUN uv pip install --system pydantic
RUN uv pip install --system pydantic-settings
RUN uv pip install --system sqlmodel
RUN uv pip install --system python-dotenv
RUN uv pip install --system aiofiles
RUN uv pip install --system requests
RUN uv pip install --system langchain
RUN uv pip install --system langchain-core
RUN uv pip install --system langchain-community
RUN uv pip install --system langchain-text-splitters
RUN uv pip install --system langchain-chroma
RUN uv pip install --system langchain-openai
RUN uv pip install --system langchain-experimental
RUN uv pip install --system langchain-nvidia-ai-endpoints
RUN uv pip install --system chromadb
RUN uv pip install --system sentence-transformers
RUN uv pip install --system PyMuPDF
RUN uv pip install --system camelot-py
RUN uv pip install --system pytesseract
RUN uv pip install --system Pillow
RUN uv pip install --system opencv-python-headless
RUN uv pip install --system transformers
RUN uv pip install --system torch
RUN uv pip install --system redis
# RUN uv pip install --system psycopg2
RUN uv pip install --system psycopg2-binary


# # --- RAG Pipeline & Safety ---
# RUN uv pip install --system nemoguardrails
# RUN uv pip install --system langchain-classic
# RUN uv pip install --system langchain-qdrant

# # --- Observability & Tracing (Phoenix) ---
# RUN uv pip install --system opentelemetry-api
# RUN uv pip install --system opentelemetry-sdk
# RUN uv pip install --system opentelemetry-exporter-otlp
# RUN uv pip install --system arize-phoenix-otel
# RUN uv pip install --system arize-phoenix

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
