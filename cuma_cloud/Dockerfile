# Cuma Cloud Control Plane - Production image
# Lightweight, secure, Harness Engineering philosophy

FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code, preserving cuma_cloud package structure
COPY . /app/cuma_cloud

# Ensure Python can resolve cuma_cloud module
ENV PYTHONPATH=/app

# Expose CLOUD_PORT (default 8080)
EXPOSE 8080

# Run uvicorn directly (no reload in production)
CMD ["uvicorn", "cuma_cloud.main:app", "--host", "0.0.0.0", "--port", "8080"]
