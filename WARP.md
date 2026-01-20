# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

YT-Download-NG is a containerized YouTube Music downloader with a modern web interface. It's a hybrid application using:
- **Rust (Axum)** - Web backend and API server (~30KB main.rs)
- **Python (gytmdl)** - Download orchestration (ytdl.py + patched gytmdl library)
- **Node.js (bgutil)** - PO token server for YouTube bot protection bypass
- **Vanilla HTML/CSS/JS** - Enhanced web UI with 5 views (Dashboard, Downloads, Files, Logs, Settings)

Key architectural note: This is a containerized web wrapper around Python CLI tools. The Rust backend spawns Python/Node.js processes and manages jobs.

## Development Commands

### Docker (Primary Development Method)
```powershell
# Build and start container
docker compose up -d

# Rebuild after code changes
docker compose down
docker compose build --no-cache
docker compose up -d

# View logs
docker logs -f ytdl-web

# Execute commands in container
docker exec ytdl-web python ytdl.py download "URL" -p profiles/audiophile-max

# Shell access
docker exec -it ytdl-web bash
```

### Rust Backend (Local Development)
```powershell
# From web-backend/ directory
cd web-backend
cargo build --release
cargo run

# Run tests (if available)
cargo test
```

### Python Tools (Host Machine)
```powershell
# Install dependencies
pip install -r requirements.txt

# Download directly (bypassing web UI)
python ytdl.py download "URL" -p profiles/audiophile-max

# List available profiles
python ytdl.py profiles

# Check dependencies
python ytdl.py check

# Start PO token server manually
python ytdl.py server
```

### Testing Downloads
```powershell
# Test API endpoint
.\test-api-final.ps1

# Test single download
.\test-download.ps1

# Test batch downloads
.\test-download2.ps1
.\test-download3.ps1
```

## Architecture & Critical Components

### Multi-Stage Build Process
The Dockerfile uses 3 stages:
1. **node-builder** - Compiles TypeScript PO token server
2. **rust-builder** - Compiles Rust web backend
3. **Final image** - Python runtime with all components

### Critical Patch System
**Location**: `gytmdl-patches/`
- `cli.py` - Modified gytmdl CLI with PO server detection (lines 264-273)
- `downloader.py` - Modified downloader with PO token integration

These patches are applied during Docker build (Dockerfile lines 62-65). **Never modify gytmdl directly via pip** - changes must be made to patches and container rebuilt.

### Configuration Management
- **Main config**: `config/gytmdl.json` (default profile)
- **Quality profiles**: `config/profiles/*.json` (10 specialized profiles)
- **Cookies**: `config/cookies.txt` (required for downloads, expires periodically)
- **Path handling**: All config paths use forward slashes for Linux container compatibility

### State Management
- **Jobs**: In-memory HashMap in Rust (Arc<RwLock<HashMap<Uuid, DownloadJob>>>)
- **Downloads**: Mounted volume at `./downloads/`
- **Logs**: Captured from Python stdout/stderr, stored per-job
- **PO Server**: Singleton process managed by Rust backend

### API Endpoints
```
GET  /                     - Serve web UI
GET  /health              - Health check
GET  /api/profiles        - List quality profiles
POST /api/download        - Submit download job
GET  /api/jobs            - List all jobs
GET  /api/jobs/:id        - Get job details
POST /api/jobs/:id/cancel - Cancel job
POST /api/jobs/:id/retry  - Retry job
GET  /api/files           - List downloaded files
GET  /api/logs            - Get system logs
GET  /api/settings        - Get settings
PUT  /api/settings        - Update settings
GET  /api/system/status   - System info (disk, memory, CPU)
GET  /api/server/status   - PO token server status
POST /api/server/start    - Start PO token server
WS   /ws                  - WebSocket for real-time updates
```

## Common Development Patterns

### Adding a New Quality Profile
1. Create `config/profiles/new-profile.json` with gytmdl config
2. Profile auto-detected by `ytdl.py profiles` command
3. Rebuild container to include new profile
4. Access via API or UI dropdown

### Modifying gytmdl Behavior
1. Edit files in `gytmdl-patches/` (NOT site-packages)
2. Rebuild container (patches applied at build time)
3. Test in container: `docker exec ytdl-web python ytdl.py download "URL"`

### Extending Rust Backend
1. Edit `web-backend/src/main.rs`
2. Add route to Router in `main()` function (around line 134)
3. Implement async handler function
4. Rebuild: `cargo build --release` or `docker compose build`

### Adding UI Features
1. Edit `ui-enhanced.html` (single-file UI)
2. UI is served from file or embedded fallback
3. Rebuild container to update embedded version
4. Test at http://localhost:8080

## Troubleshooting

### Downloads Failing
1. Check cookies.txt is present and not expired
2. Verify PO token server is running: `GET /api/server/status`
3. Check logs: `docker logs ytdl-web` or UI Logs view
4. Look for "Using automatic PO token provider" in logs

### Container Build Issues
- Node.js stage: Ensure bgutil-pot-provider submodule is initialized
- Rust stage: Check pkg-config and libssl-dev are installed
- Python stage: Patches must apply to correct site-packages path

### Path Problems
- Container runs Linux - all config paths must use `/` not `\`
- Volume mounts: Host paths can use Windows style, container paths use Linux
- Use `Path(__file__).parent.absolute()` in Python for cross-platform paths

### Port Conflicts
- Web UI: Default 8080, change in docker-compose.yml or YTDL_PORT env var
- PO Server: Hardcoded 4416, change requires code modifications

## Quality Profiles

Pre-configured profiles optimized for different use cases:
- **gytmdl** - Standard quality (140 kbps AAC)
- **audiophile-max** - Maximum quality (Opus 135kbps, 1400px covers)
- **music-hq** - High quality balanced
- **archive-lossless** - Lossless archival
- **vinyl-collection** - Vinyl-optimized settings
- **classical** - Optimized for classical music
- **audiobook** - Speech-optimized
- **live-recordings** - Live performance settings
- **mobile-optimized** - Smaller files for mobile
- **critical-listening** - Studio reference quality
- **reference-testing** - Maximum quality for testing

## Dependencies

### Container Runtime
- Docker and Docker Compose required
- Multi-arch support (builds on x86_64, arm64)

### Build Dependencies
- Node.js 20+ (for building PO server)
- Rust 1.83+ (for web backend)
- Python 3.12+ (for gytmdl)

### Runtime Dependencies (in container)
- ffmpeg (audio processing)
- aria2 (parallel downloads - currently disabled in favor of native)
- curl (health checks)

### Python Packages (requirements.txt)
- gytmdl>=2.1.6 (YouTube Music downloader)
- yt-dlp>=2025.12.08 (YouTube extractor)
- ytmusicapi>=1.11.4 (YouTube Music API)
- bgutil-ytdlp-pot-provider>=1.2.2 (PO token integration)
- psutil>=7.2.1 (process management)
- requests>=2.32.5 (HTTP client)

### Rust Crates (Cargo.toml)
- axum 0.7 (web framework)
- tokio 1.0 (async runtime)
- serde/serde_json (JSON serialization)
- tower-http (CORS, static files, tracing)
- rusqlite 0.31 (SQLite database)
- uuid 1.0 (job IDs)
- chrono 0.4 (timestamps)
- sysinfo 0.30 (system metrics)

## Project Status

**Production Ready** - All core features tested and working:
- ✅ Downloads working end-to-end (verified with 33-track album)
- ✅ PO token server integration functional
- ✅ Web UI with 5 views and real-time WebSocket updates
- ✅ Container health checks and automatic restart
- ✅ All 10 quality profiles detected and functional

Known limitations:
- Job history not persisted (in-memory only)
- No authentication/multi-user support
- File browser API placeholder (UI present, backend incomplete)
- Log streaming is per-job capture, not real-time tailing

## File Structure

```
.
├── Dockerfile                    # Multi-stage build
├── docker-compose.yml            # Deployment config
├── ytdl.py                       # Python orchestration script
├── requirements.txt              # Python dependencies
├── ui-enhanced.html              # Single-file web UI
├── web-backend/
│   ├── Cargo.toml               # Rust dependencies
│   └── src/main.rs              # Axum web server (~30KB)
├── config/
│   ├── gytmdl.json              # Default profile
│   ├── cookies.txt              # YouTube cookies (required)
│   └── profiles/*.json          # Quality profiles (10 files)
├── gytmdl-patches/
│   ├── cli.py                   # Modified gytmdl CLI
│   └── downloader.py            # Modified gytmdl downloader
├── bgutil-pot-provider/         # Git submodule (Node.js PO server)
├── downloads/                   # Downloaded files (volume mount)
├── cache/                       # gytmdl cache (volume mount)
└── logs/                        # System logs (volume mount)
```

## Windows-Specific Notes

This repository is developed on Windows but runs Linux containers:
- PowerShell scripts (*.ps1) for testing on host
- Use `docker exec` to run commands inside Linux container
- Path separators: `\` on host, `/` in container
- Line endings: CRLF on host, LF in container (Git handles conversion)
