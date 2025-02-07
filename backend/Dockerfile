# Base Python image
FROM python:3.11-slim AS base
WORKDIR /app

# Development stage
FROM base AS development
# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
# Copy requirements first to leverage Docker cache
COPY requirements.txt .
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Copy rest of the application
COPY . .
# Expose port
EXPOSE 8000
# Start development server with hot reload
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Production stage
FROM development AS production
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"] 