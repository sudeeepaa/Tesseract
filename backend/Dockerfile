# Use Python 3.9 slim as the base image for runtime consistency
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY pyproject.toml /app/
# We copy pyproject.toml and do a pip install
# Since we are installing threadline as a package, we need to copy threadline source files first,
# OR we can install requirements. Let's install the dependencies from pyproject.toml directly.
# To do that, we can install the package in editable or non-editable mode.
# Let's copy the code package as well.
COPY threadline/ /app/threadline/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir .

# Pre-download the sentence-transformers fallback model to avoid download latency during live demo
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the backend code
COPY backend/ /app/backend/

# Expose the API port
EXPOSE 8000

# Run FastAPI backend
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
