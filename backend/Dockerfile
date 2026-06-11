# ==============================================================================
# KisanMitra AI Backend — Multi-stage Dockerfile
# ==============================================================================
# Stage 1: Builder — install dependencies in isolation
# Stage 2: Runtime — slim image with only what's needed
# ==============================================================================
# Compatible with: Render, Hugging Face Spaces, Google Cloud Run
# HF Spaces requires port 7860. Others use PORT env var or default 7860.
# ==============================================================================

# ---- Stage 1: Builder ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install system dependencies for building native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: Runtime ----
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install minimal runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY . .

# Copy the startup script and make it executable
COPY start.sh /app/start.sh
RUN chmod +x /app/start.sh

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser \
    && chown -R appuser:appuser /app
USER appuser

# Default port (HF Spaces uses 7860)
ENV PORT=7860
EXPOSE 7860

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${PORT:-7860}/').raise_for_status()" || exit 1

# Run the startup script (handles Firebase SA decoding + uvicorn)
CMD ["/app/start.sh"]
