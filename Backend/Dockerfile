FROM python:3.12-alpine

WORKDIR /app

# Install system dependencies required for building Python packages
RUN apk add --no-cache \
    gcc \
    g++ \
    musl-dev \
    linux-headers \
    cmake \
    make \
    libffi-dev \
    openssl-dev \
    postgresql-dev \
    gfortran \
    openblas-dev \
    lapack-dev \
    tesseract-ocr \
    ghostscript \
    poppler-utils \
    jpeg-dev \
    zlib-dev \
    freetype-dev \
    lcms2-dev \
    openjpeg-dev \
    tiff-dev \
    tk-dev \
    tcl-dev

# Copy requirements
COPY requirements.txt .

# Install PyTorch CPU-only version first
RUN pip install --upgrade pip setuptools wheel && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu

# Install remaining packages via pip
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
