FROM python:3.12-alpine

WORKDIR /app

# Install system dependencies
# build-base, openblas-dev, gfortran, etc. are for numpy/scipy/pandas compilation
# libffi-dev, openssl-dev for general python libs
# jpeg-dev, zlib-dev for Pillow
# linux-headers for some compilations
RUN apk add --no-cache \
    build-base \
    libffi-dev \
    openssl-dev \
    openblas-dev \
    gfortran \
    python3-dev \
    linux-headers \
    jpeg-dev \
    zlib-dev \
    cargo \
    pkgconfig \
    freetype-dev \
    libpng-dev \
    g++ \
    gcc \
    make

# Copy requirements
COPY requirements.txt .

# Install python dependencies
# Note: This might take a while due to compilation
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
