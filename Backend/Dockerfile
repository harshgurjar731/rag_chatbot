FROM continuumio/miniconda3:latest

WORKDIR /app

# Install system dependencies via conda (no apt needed)
RUN conda install -y -c conda-forge \
    gcc_linux-64 \
    gxx_linux-64 \
    tesseract \
    poppler \
    ghostscript && \
    conda clean -a -y

# Set compiler environment variables to use conda compilers
ENV CC=/opt/conda/bin/x86_64-conda-linux-gnu-gcc \
    CXX=/opt/conda/bin/x86_64-conda-linux-gnu-g++

# Copy requirements
COPY requirements.txt .

# Install uv and use it for package installation
RUN pip install --upgrade pip uv && \
    uv pip install --system torch --index-url https://download.pytorch.org/whl/cpu && \
    uv pip install --system -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
