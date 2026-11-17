# Self-hosted Sweepr: one container, one process, no GPU needed.
#
#   docker compose -f docker-compose.prod.yml up --build
#
# The engine (deep-filter + ffmpeg) is downloaded and checksum-verified at image
# build time, so containers start offline. Set SWEEPR_TOKEN for a stable token;
# otherwise one is generated and printed in the logs.

# --- Stage 1: build the UI --------------------------------------------------
FROM node:22-slim AS ui
RUN corepack enable
WORKDIR /ui
COPY sweepr_app/ui/package.json sweepr_app/ui/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY sweepr_app/ui/ ./
RUN pnpm build

# --- Stage 2: install the package and place the engine ------------------------
# The engine comes from ./engine-local/ (deep-filter, ffmpeg, ffprobe for Linux)
# when present, otherwise from the pinned upstream deep-filter and ffmpeg
# downloads in sweepr_app/assets_manifest.json.
FROM python:3.11-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE THIRD_PARTY_NOTICES.md ./
COPY sweepr_app/ ./sweepr_app/
COPY --from=ui /ui/dist ./sweepr_app/ui/dist
COPY engine-local/ ./engine-local/
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install . \
    && mkdir -p /opt/engine \
    && if [ -f engine-local/deep-filter ]; then \
         cp -a engine-local/. /opt/engine/ ; \
       else \
         SWEEPR_CACHE_DIR=/opt/sweepr-cache /opt/venv/bin/sweepr install-assets \
         && cp "$(SWEEPR_CACHE_DIR=/opt/sweepr-cache /opt/venv/bin/python -c 'from sweepr_app import assets; print(assets.install_dir())')"/* /opt/engine/ ; \
       fi \
    && rm -f /opt/engine/README.md \
    && chmod +x /opt/engine/deep-filter /opt/engine/ffmpeg /opt/engine/ffprobe

# --- Stage 3: runtime ---------------------------------------------------------
FROM python:3.11-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    SWEEPR_DATA_DIR=/data \
    SWEEPR_BIN_DIR=/opt/engine

RUN useradd --create-home --uid 10001 sweepr \
    && mkdir /data && chown sweepr:sweepr /data

COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/engine /opt/engine

USER sweepr
WORKDIR /home/sweepr
VOLUME ["/data"]
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=4); sys.exit(0)" || exit 1

# Listens on all interfaces inside the container; publish it only on the host
# interfaces you intend (see docker-compose.prod.yml). Requests must carry
# SWEEPR_TOKEN (or the random token printed in the logs).
CMD ["sweepr", "--no-browser", "--host", "0.0.0.0", "--port", "8765"]
