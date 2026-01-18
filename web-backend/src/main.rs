use axum::{
    extract::{Path, State, WebSocketUpgrade, ws::{WebSocket, Message}},
    response::{Html, IntoResponse, Json},
    routing::{get, post},
    Router,
};
use futures::{StreamExt, SinkExt};
use serde::{Deserialize, Serialize};
use std::{
    collections::HashMap,
    process::Stdio,
    sync::Arc,
};
use tokio::{
    process::Command,
    sync::{Mutex, RwLock},
};
use tower_http::{
    cors::{Any, CorsLayer},
    services::ServeDir,
    trace::TraceLayer,
};
use tracing::{info, warn};
use uuid::Uuid;

// State and types
#[derive(Clone)]
struct AppState {
    jobs: Arc<RwLock<HashMap<Uuid, DownloadJob>>>,
    po_server_pid: Arc<Mutex<Option<u32>>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct DownloadJob {
    id: Uuid,
    url: String,
    profile: String,
    status: JobStatus,
    progress: f32,
    created_at: chrono::DateTime<chrono::Utc>,
    logs: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
enum JobStatus {
    Pending,
    Running,
    Completed,
    Failed,
}

#[derive(Debug, Deserialize)]
struct DownloadRequest {
    url: String,
    profile: Option<String>,
}

#[derive(Debug, Serialize)]
struct ApiResponse<T> {
    success: bool,
    data: Option<T>,
    error: Option<String>,
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "info".into()),
        )
        .init();

    info!("Starting YT-Download-NG Web Backend");

    let state = AppState {
        jobs: Arc::new(RwLock::new(HashMap::new())),
        po_server_pid: Arc::new(Mutex::new(None)),
    };

    if let Err(e) = start_po_server(&state).await {
        warn!("Failed to start PO token server: {}", e);
    }

    let app = Router::new()
        .route("/", get(serve_ui))
        .route("/health", get(health_check))
        .route("/api/profiles", get(list_profiles))
        .route("/api/download", post(start_download))
        .route("/api/jobs", get(list_jobs))
        .route("/api/jobs/:id", get(get_job))
        .route("/api/server/status", get(server_status))
        .route("/api/server/start", post(start_server))
        .route("/ws", get(websocket_handler))
        .nest_service("/static", ServeDir::new("static"))
        .layer(CorsLayer::new().allow_origin(Any).allow_methods(Any).allow_headers(Any))
        .layer(TraceLayer::new_for_http())
        .with_state(state);

    let port = std::env::var("YTDL_PORT")
        .unwrap_or_else(|_| "8080".to_string())
        .parse()
        .unwrap_or(8080);

    let addr = format!("0.0.0.0:{}", port);
    info!("Server listening on {}", addr);

    let listener = tokio::net::TcpListener::bind(&addr).await.unwrap();
    axum::serve(listener, app).await.unwrap();
}

async fn serve_ui() -> impl IntoResponse {
    match tokio::fs::read_to_string("ui-enhanced.html").await {
        Ok(content) => Html(content).into_response(),
        Err(_) => Html(UI_HTML).into_response(), // Fallback to embedded UI
    }
}

async fn health_check() -> Json<ApiResponse<String>> {
    Json(ApiResponse {
        success: true,
        data: Some("OK".to_string()),
        error: None,
    })
}

async fn list_profiles() -> Json<ApiResponse<Vec<String>>> {
    let output = Command::new("python")
        .args(&["ytdl.py", "profiles"])
        .output()
        .await;

    match output {
        Ok(output) if output.status.success() => {
            let profiles = String::from_utf8_lossy(&output.stdout)
                .lines()
                .filter(|line| line.contains("✓"))
                .map(|line| {
                    // Remove ANSI color codes and clean up
                    let cleaned = line
                        .replace("\x1b[32m", "")  // Remove green color
                        .replace("\x1b[0m", "")   // Remove reset
                        .replace("✓", "")
                        .trim()
                        .to_string();
                    cleaned
                })
                .collect();

            Json(ApiResponse {
                success: true,
                data: Some(profiles),
                error: None,
            })
        }
        _ => Json(ApiResponse {
            success: false,
            data: None,
            error: Some("Failed to list profiles".to_string()),
        }),
    }
}

async fn start_download(
    State(state): State<AppState>,
    Json(req): Json<DownloadRequest>,
) -> Json<ApiResponse<Uuid>> {
    let job_id = Uuid::new_v4();
    let profile = req.profile.unwrap_or_else(|| "gytmdl".to_string());

    let job = DownloadJob {
        id: job_id,
        url: req.url.clone(),
        profile: profile.clone(),
        status: JobStatus::Pending,
        progress: 0.0,
        created_at: chrono::Utc::now(),
        logs: vec![],
    };

    {
        let mut jobs = state.jobs.write().await;
        jobs.insert(job_id, job);
    }

    let state_clone = state.clone();
    let url = req.url;
    tokio::spawn(async move {
        run_download(state_clone, job_id, url, profile).await;
    });

    Json(ApiResponse {
        success: true,
        data: Some(job_id),
        error: None,
    })
}

async fn list_jobs(State(state): State<AppState>) -> Json<ApiResponse<Vec<DownloadJob>>> {
    let jobs = state.jobs.read().await;
    let job_list: Vec<DownloadJob> = jobs.values().cloned().collect();

    Json(ApiResponse {
        success: true,
        data: Some(job_list),
        error: None,
    })
}

async fn get_job(
    State(state): State<AppState>,
    Path(id): Path<Uuid>,
) -> Json<ApiResponse<DownloadJob>> {
    let jobs = state.jobs.read().await;

    match jobs.get(&id) {
        Some(job) => Json(ApiResponse {
            success: true,
            data: Some(job.clone()),
            error: None,
        }),
        None => Json(ApiResponse {
            success: false,
            data: None,
            error: Some("Job not found".to_string()),
        }),
    }
}

async fn server_status(State(state): State<AppState>) -> Json<ApiResponse<bool>> {
    let pid = state.po_server_pid.lock().await;
    let running = pid.is_some();

    Json(ApiResponse {
        success: true,
        data: Some(running),
        error: None,
    })
}

async fn start_server(State(state): State<AppState>) -> Json<ApiResponse<String>> {
    match start_po_server(&state).await {
        Ok(_) => Json(ApiResponse {
            success: true,
            data: Some("Server started".to_string()),
            error: None,
        }),
        Err(e) => Json(ApiResponse {
            success: false,
            data: None,
            error: Some(e.to_string()),
        }),
    }
}

async fn websocket_handler(
    ws: WebSocketUpgrade,
    State(state): State<AppState>,
) -> impl IntoResponse {
    ws.on_upgrade(|socket| websocket(socket, state))
}

async fn websocket(stream: WebSocket, state: AppState) {
    let (mut sender, mut receiver) = stream.split();

    let state_clone = state.clone();
    tokio::spawn(async move {
        loop {
            tokio::time::sleep(tokio::time::Duration::from_secs(1)).await;

            let jobs = state_clone.jobs.read().await;
            let job_list: Vec<DownloadJob> = jobs.values().cloned().collect();

            if let Ok(msg) = serde_json::to_string(&job_list) {
                if sender.send(Message::Text(msg)).await.is_err() {
                    break;
                }
            }
        }
    });

    while let Some(Ok(msg)) = receiver.next().await {
        if matches!(msg, Message::Close(_)) {
            break;
        }
    }
}

async fn start_po_server(state: &AppState) -> Result<(), Box<dyn std::error::Error>> {
    let mut child = Command::new("node")
        .arg("bgutil-pot-provider/server/build/main.js")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()?;

    let pid = child.id().ok_or("Failed to get process ID")?;
    *state.po_server_pid.lock().await = Some(pid);

    info!("Started PO token server with PID {}", pid);
    Ok(())
}

async fn run_download(state: AppState, job_id: Uuid, url: String, profile: String) {
    {
        let mut jobs = state.jobs.write().await;
        if let Some(job) = jobs.get_mut(&job_id) {
            job.status = JobStatus::Running;
            job.logs.push(format!("Starting download: {}", url));
        }
    }

    let output = Command::new("python")
        .args(&["ytdl.py", "download", &url, "-p", &profile])
        .current_dir("/app")
        .output()
        .await;

    {
        let mut jobs = state.jobs.write().await;
        if let Some(job) = jobs.get_mut(&job_id) {
            match output {
                Ok(output) if output.status.success() => {
                    job.status = JobStatus::Completed;
                    job.progress = 100.0;
                    job.logs.push("Download completed successfully".to_string());
                    
                    // Add all stdout for debugging
                    if !output.stdout.is_empty() {
                        let stdout = String::from_utf8_lossy(&output.stdout);
                        for line in stdout.lines() {
                            job.logs.push(format!("[stdout] {}", line));
                        }
                    }
                    
                    // Add stderr too in case there are warnings
                    if !output.stderr.is_empty() {
                        let stderr = String::from_utf8_lossy(&output.stderr);
                        for line in stderr.lines() {
                            job.logs.push(format!("[stderr] {}", line));
                        }
                    }
                }
                Ok(output) => {
                    job.status = JobStatus::Failed;
                    job.logs.push(format!("Download failed with exit code: {}", output.status.code().unwrap_or(-1)));
                    
                    // Capture stderr for debugging
                    if !output.stderr.is_empty() {
                        let stderr = String::from_utf8_lossy(&output.stderr);
                        for line in stderr.lines().take(10) {
                            job.logs.push(format!("Error: {}", line));
                        }
                    }
                    
                    // Also capture stdout in case of error
                    if !output.stdout.is_empty() {
                        let stdout = String::from_utf8_lossy(&output.stdout);
                        for line in stdout.lines().take(5) {
                            job.logs.push(format!("Output: {}", line));
                        }
                    }
                }
                Err(e) => {
                    job.status = JobStatus::Failed;
                    job.logs.push(format!("Failed to execute command: {}", e));
                }
            }
        }
    }
}

const UI_HTML: &str = r#"<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YT-Download-NG</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 40px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        .card {
            background: white;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .input-group {
            margin-bottom: 20px;
        }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #333;
        }
        input, select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e1e8ed;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        input:focus, select:focus {
            outline: none;
            border-color: #667eea;
        }
        .btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 14px 30px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:active {
            transform: translateY(0);
        }
        .jobs-list {
            margin-top: 30px;
        }
        .job-item {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        .job-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .job-url {
            font-weight: 600;
            color: #333;
            flex: 1;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .status {
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
        }
        .status.pending { background: #ffd700; color: #856404; }
        .status.running { background: #17a2b8; color: white; }
        .status.completed { background: #28a745; color: white; }
        .status.failed { background: #dc3545; color: white; }
        .progress-bar {
            height: 8px;
            background: #e1e8ed;
            border-radius: 4px;
            overflow: hidden;
            margin-top: 10px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            transition: width 0.3s;
        }
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }
        .empty-state svg {
            width: 100px;
            height: 100px;
            margin-bottom: 20px;
            opacity: 0.5;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 YT-Download-NG</h1>
            <p>Fast, reliable, and beautiful music downloads</p>
        </div>

        <div class="card">
            <div class="input-group">
                <label for="url">YouTube Music URL</label>
                <input type="text" id="url" placeholder="https://music.youtube.com/playlist?list=..." />
            </div>
            <div class="input-group">
                <label for="profile">Quality Profile</label>
                <select id="profile">
                    <option value="gytmdl">Default (AAC 128kbps)</option>
                </select>
            </div>
            <button class="btn" onclick="startDownload()">Start Download</button>
        </div>

        <div class="card jobs-list">
            <h2 style="margin-bottom: 20px;">Download Jobs</h2>
            <div id="jobs"></div>
        </div>
    </div>

    <script>
        let ws;

        async function loadProfiles() {
            const res = await fetch('/api/profiles');
            const data = await res.json();
            if (data.success && data.data) {
                const select = document.getElementById('profile');
                select.innerHTML = data.data.map(p => 
                    `<option value="${p}">${p}</option>`
                ).join('');
            }
        }

        async function startDownload() {
            const url = document.getElementById('url').value;
            const profile = document.getElementById('profile').value;

            if (!url) {
                alert('Please enter a URL');
                return;
            }

            const res = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, profile })
            });

            const data = await res.json();
            if (data.success) {
                document.getElementById('url').value = '';
                loadJobs();
            } else {
                alert('Failed to start download: ' + data.error);
            }
        }

        async function loadJobs() {
            const res = await fetch('/api/jobs');
            const data = await res.json();
            const jobsDiv = document.getElementById('jobs');

            if (!data.success || !data.data || data.data.length === 0) {
                jobsDiv.innerHTML = `
                    <div class="empty-state">
                        <svg fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M9 19l3 3m0 0l3-3m-3 3V10"></path>
                        </svg>
                        <p>No downloads yet. Start your first download above!</p>
                    </div>
                `;
                return;
            }

            jobsDiv.innerHTML = data.data.map(job => `
                <div class="job-item">
                    <div class="job-header">
                        <div class="job-url">${job.url}</div>
                        <div class="status ${job.status}">${job.status}</div>
                    </div>
                    <div style="font-size: 14px; color: #6c757d;">
                        Profile: ${job.profile} | Started: ${new Date(job.created_at).toLocaleString()}
                    </div>
                    ${job.status === 'running' ? `
                        <div class="progress-bar">
                            <div class="progress-fill" style="width: ${job.progress}%"></div>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        }

        function connectWebSocket() {
            ws = new WebSocket(`ws://${window.location.host}/ws`);
            ws.onmessage = (event) => {
                const jobs = JSON.parse(event.data);
                // Update UI with real-time data
            };
            ws.onclose = () => {
                setTimeout(connectWebSocket, 3000);
            };
        }

        loadProfiles();
        loadJobs();
        setInterval(loadJobs, 2000);
        connectWebSocket();
    </script>
</body>
</html>
"#;
