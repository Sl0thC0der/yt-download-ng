# YouTube Music Downloader NG - Containerized Version
# Multi-stage build for optimized image size

# Stage 1: Build PO Token Provider
FROM node:20-slim AS node-builder
WORKDIR /app
COPY bgutil-pot-provider/server ./server
WORKDIR /app/server
RUN npm install && npx tsc

# Stage 2: Build Rust Web Backend
FROM rust:1.83-slim AS rust-builder
WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y \
    pkg-config \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Rust project files
COPY web-backend ./web-backend
WORKDIR /app/web-backend

# Build release binary
RUN cargo build --release

# Stage 3: Final runtime image
FROM python:3.12-slim

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    aria2 \
    nodejs \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create app user
RUN useradd -m -u 1000 ytdl && \
    mkdir -p /app /data/downloads /data/config /data/cache /data/logs /data/temp && \
    chown -R ytdl:ytdl /app /data

USER ytdl
WORKDIR /app

# Add user bin to PATH
ENV PATH="/home/ytdl/.local/bin:${PATH}"

# Copy Python requirements and install
COPY --chown=ytdl:ytdl requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Copy application files
COPY --chown=ytdl:ytdl ytdl.py .
COPY --chown=ytdl:ytdl config ./config
COPY --chown=ytdl:ytdl --from=node-builder /app/server ./bgutil-pot-provider/server
COPY --chown=ytdl:ytdl --from=rust-builder /app/web-backend/target/release/ytdl-web /usr/local/bin/

# Apply gytmdl patches for PO token provider support
COPY --chown=ytdl:ytdl gytmdl-patches/* /tmp/gytmdl-patches/
RUN cp /tmp/gytmdl-patches/cli.py /home/ytdl/.local/lib/python3.12/site-packages/gytmdl/cli.py && \
    cp /tmp/gytmdl-patches/downloader.py /home/ytdl/.local/lib/python3.12/site-packages/gytmdl/downloader.py && \
    rm -rf /tmp/gytmdl-patches

# Fix all configs on startup
RUN python ytdl.py fix-all || true

# Expose ports
# 8080: Web UI
# 4416: PO Token Server
EXPOSE 8080 4416

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Start web backend (which manages Python and Node processes)
CMD ["/usr/local/bin/ytdl-web"]
