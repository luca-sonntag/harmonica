# =============================================================================
# Stage 1: Build Mobile-First Anti-AI-Slop React Frontend (Vite + TypeScript)
# =============================================================================
FROM node:22-slim AS web-builder

WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci

COPY web/ ./
RUN npm run build

# =============================================================================
# Stage 2: Lightweight Cloud-CPU Runtime (FFmpeg + FastAPI + ONNX + Verovio)
# Uses CPU-only PyTorch (~180 MB) + ONNX Basic Pitch (17 MB) + JKU Beat-This
# instead of 4 GB CUDA/TensorFlow bloat.
# =============================================================================
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Install CPU-only PyTorch & Torchaudio (avoids 2.8 GB NVIDIA CUDA wheels on Railway CPU)
RUN pip install --index-url https://download.pytorch.org/whl/cpu \
    torch==2.6.0+cpu torchaudio==2.6.0+cpu

# 2. Install core pipeline dependencies + Beat-This + Basic Pitch (ONNX Runtime without TensorFlow)
COPY requirements-railway.txt ./
RUN pip install -r requirements-railway.txt && \
    pip install --no-deps basic-pitch==0.4.0 && \
    pip install --no-deps git+https://github.com/CPJKU/beat_this.git

# 3. Pre-warm JKU Beat-This checkpoint during build so Railway cold starts are instant
RUN python -c "from beat_this.inference import File2Beats; File2Beats(checkpoint_path='final0', device='cpu', dbn=False)"

# 4. Copy backend package (including compact demo_assets/) and built React frontend
COPY harmonica_pipeline/ ./harmonica_pipeline/
COPY --from=web-builder /app/web/dist ./web/dist

RUN mkdir -p /app/outputs/jobs /app/samples

EXPOSE 8000

CMD ["sh", "-c", "uvicorn harmonica_pipeline.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
