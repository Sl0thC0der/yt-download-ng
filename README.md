# yt-download-container-ng

A modern, containerized YouTube Music downloader with a beautiful web interface. Built with Rust (Axum), Python (gytmdl), and Node.js (PO Token server).

## ✨ Features

- 🎨 **Beautiful Web UI** - Purple gradient design with real-time updates
- 🔒 **Containerized** - Runs in Docker for easy deployment
- 🚀 **Fast Rust Backend** - Built with Axum for high performance
- 🎵 **Multiple Quality Profiles** - 11 pre-configured profiles
- 📊 **Job Management** - Track download progress and history
- 🔄 **WebSocket Updates** - Real-time job status updates
- 🛡️ **PO Token Support** - Automatic bot protection bypass

## 🚀 Quick Start

```bash
docker compose up -d
```

Access the web UI at **http://localhost:8080**

## 📁 Downloads

Downloaded files appear in `./downloads/` directory.

## 🎯 API Endpoints

- `GET /health` - Health check
- `GET /api/profiles` - List quality profiles
- `POST /api/download` - Submit download
- `GET /api/jobs` - List all jobs
- `GET /api/jobs/:id` - Get job status

## 🎨 Quality Profiles

- **gytmdl** - Standard (140 kbps AAC)
- **audiophile-max** - Maximum quality
- **music-hq** - High quality
- **archive-lossless** - Lossless
- **vinyl-collection** - Vinyl-optimized
- And 6 more specialized profiles

## 🔧 Technical Details

**The Key Fix**: Modified gytmdl files with PO token server detection (in `gytmdl-patches/`)

**Architecture**:
1. Rust Backend (Axum) - HTTP/WebSocket/Job management
2. Python (gytmdl) - Download orchestration
3. Node.js (bgutil) - PO token generation
4. Embedded Frontend - Purple gradient UI

## ✅ Status

**ALL ISSUES FIXED!** ✓

- ✓ Virtual environment detection
- ✓ Config paths for Linux
- ✓ PO token server integration
- ✓ Downloads working perfectly
- ✓ Files saved to mounted volume
- ✓ Web UI fully functional

**Tested**: 33-track album downloaded successfully!

## 🙏 Credits

- [gytmdl](https://github.com/glomatico/gytmdl)
- [yt-dlp](https://github.com/yt-dlp/yt-dlp)
- [bgutil-ytdlp-pot-provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider)
- [Axum](https://github.com/tokio-rs/axum)
