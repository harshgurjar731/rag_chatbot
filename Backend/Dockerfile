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

# Install Core & Light Frameworks (FastAPI, SQLModel, Redis)
RUN uv pip install --system fastapi
RUN uv pip install --system uvicorn
RUN uv pip install --system python-multipart
RUN uv pip install --system pydantic
RUN uv pip install --system pydantic-settings
RUN uv pip install --system sqlmodel
RUN uv pip install --system python-dotenv
RUN uv pip install --system aiofiles
RUN uv pip install --system requests
RUN uv pip install --system deep-translator
RUN uv pip install --system redis
RUN uv pip install --system psycopg2-binary

# Light LangChain (Core only)
RUN uv pip install --system langchain-core
RUN uv pip install --system langchain-text-splitters
RUN uv pip install --system pypdf
RUN uv pip install --system openai
RUN uv pip install --system langchain-openai

# Observability
RUN uv pip install --system opentelemetry-api
RUN uv pip install --system opentelemetry-sdk
RUN uv pip install --system opentelemetry-exporter-otlp
RUN uv pip install --system arize-phoenix-otel
RUN uv pip install --system arize-phoenix
RUN uv pip install --system openinference-instrumentation-langchain
RUN uv pip install --system openinference-instrumentation-openai

# Stage 2: Runtime - Minimal image with only runtime dependencies
FROM continuumio/miniconda3:latest

WORKDIR /app

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

# Command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
