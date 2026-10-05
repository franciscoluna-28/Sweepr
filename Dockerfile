# Production image: build the Svelte UI, then serve it from FastAPI.
# Result is a single container running one Python process.

# --- Stage 1: build the UI ---
FROM node:22-slim AS ui
RUN corepack enable
WORKDIR /ui
COPY app/ui/package.json app/ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY app/ui/ ./
RUN pnpm build

# --- Stage 2: runtime ---
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install torch==2.1.2 torchaudio==2.1.2 \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install -r requirements.txt

COPY app/ ./app/
COPY --from=ui /ui/dist ./app/ui/dist

EXPOSE 8765
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
