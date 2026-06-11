FROM python:3.11-slim

# Security: run as non-root user
RUN useradd -m -s /bin/bash agentos

WORKDIR /app

# Install deps first (cache layer)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt cryptography psutil

# Copy source
COPY . .

# Create data dir with correct permissions
RUN mkdir -p /app/data && chown -R agentos:agentos /app

USER agentos
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s \
    CMD python3 -c "import httpx; r=httpx.get('http://localhost:8000/'); exit(0 if r.status_code in (200,401) else 1)"

CMD ["python3", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
