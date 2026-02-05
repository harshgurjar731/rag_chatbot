FROM python:3.10-slim

WORKDIR /app

# Install system dependencies - SKIPPED to avoid network issues, relying on wheels
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     libpq-dev \
#     git \
#     && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY synthetic_data_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy synthetic-data-kit from parent context
# Expecting docker build context to be the root 'rag_chatbot' directory
COPY synthetic-data-kit /app/synthetic-data-kit

# Install synthetic-data-kit
RUN pip install --no-cache-dir -e /app/synthetic-data-kit

# Copy service code
COPY synthetic_data_service /app/service

# Set python path to include compiled kit
ENV PYTHONPATH="${PYTHONPATH}:/app/synthetic-data-kit"

# Run the worker
CMD ["python", "/app/service/synthetic_worker.py"]
