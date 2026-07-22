### ── Stage 1: Build dependencies ─────────────────────────────────────────────
FROM python:3.11-slim AS builder
WORKDIR /build

# System deps needed to compile some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# --index-url pytorch/cpu takes priority for every package (torch resolves to the
# CPU-only build there); --extra-index-url falls back to PyPI for the rest. Without
# this, the default PyPI `torch` wheel on Linux pulls ~3GB of nvidia-* CUDA packages
# even though this image has no GPU passthrough configured.
RUN pip install --no-cache-dir --prefix=/install \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.org/simple \
    -r requirements.txt

### ── Stage 2: Runtime image ──────────────────────────────────────────────────
FROM python:3.11-slim AS runtime
WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Runtime system libs (libgomp for sentence-transformers ONNX backend)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Copy application source
COPY . .

# Create data directories
RUN mkdir -p /app/data/uploads /app/data/demo

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

CMD ["python", "run.py"]
