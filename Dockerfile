FROM python:3.12-slim

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy & install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose FastAPI port
EXPOSE 8000

# Default command (overridden in compose)
CMD ["uvicorn", "src.backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
