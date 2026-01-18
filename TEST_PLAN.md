# YT-Download-NG Test Plan

## Prerequisites
- Container running and healthy
- Port 8080 accessible

## Test Execution Order

### 1. Container Health Check
```powershell
docker compose ps
# Expected: STATUS shows "healthy"
```

### 2. Basic API Health
```powershell
curl http://localhost:8080/health
# Expected: {"success":true,"data":"OK","error":null}
```

### 3. PO Token Server Status
```powershell
curl http://localhost:8080/api/server/status
# Expected: {"success":true,"data":true,"error":null}
```

### 4. Profiles List
```powershell
curl http://localhost:8080/api/profiles
# Expected: Returns list of profiles including "gytmdl"
```

### 5. Settings API
```powershell
# Get settings
curl http://localhost:8080/api/settings
# Expected: Returns default settings

# Update settings
$settings = @{max_concurrent=5;auto_retry=$true;cleanup_days=14} | ConvertTo-Json
Invoke-WebRequest -Uri http://localhost:8080/api/download -Method PUT -Body $settings -ContentType "application/json"
# Expected: Returns updated settings
```

### 6. System Status
```powershell
curl http://localhost:8080/api/system/status
# Expected: Returns disk, memory, CPU, container status
```

### 7. File Browser (Empty State)
```powershell
curl http://localhost:8080/api/files
# Expected: {"success":true,"data":[],"error":null}
```

### 8. Download Job Submission
```powershell
$body = @{url="https://music.youtube.com/watch?v=kJQP7kiw5Fk";profile="gytmdl"} | ConvertTo-Json
$result = Invoke-WebRequest -Uri http://localhost:8080/api/download -Method POST -Body $body -ContentType "application/json" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
$jobId = $result.data
Write-Output "Job ID: $jobId"
# Expected: Returns UUID job ID
```

### 9. Job Status Check
```powershell
curl "http://localhost:8080/api/jobs/$jobId"
# Expected: Returns job with status "pending" or "running"
# After ~10 seconds: Status should be "completed"
```

### 10. Jobs List
```powershell
curl http://localhost:8080/api/jobs
# Expected: Returns array with the submitted job
```

### 11. Verify Download Executed
```powershell
docker exec ytdl-web ls -lh /app/downloads
# Expected: Shows created files or directory structure
```

### 12. File Browser (With Files)
```powershell
curl http://localhost:8080/api/files
# Expected: Returns array of downloaded files
```

### 13. Job Control - Cancel (if applicable)
```powershell
# Start a long download
$body = @{url="https://music.youtube.com/playlist?list=LONG_PLAYLIST";profile="gytmdl"} | ConvertTo-Json
$result = Invoke-WebRequest -Uri http://localhost:8080/api/download -Method POST -Body $body -ContentType "application/json" -UseBasicParsing | Select-Object -ExpandProperty Content | ConvertFrom-Json
$jobId = $result.data

# Cancel it
curl -X POST "http://localhost:8080/api/jobs/$jobId/cancel"
# Expected: Job status changes to "failed" with cancel message
```

### 14. Job Control - Retry
```powershell
# Get a failed job ID
$jobs = curl http://localhost:8080/api/jobs | ConvertFrom-Json
$failedJob = $jobs.data | Where-Object { $_.status -eq "failed" } | Select-Object -First 1

# Retry it
curl -X POST "http://localhost:8080/api/jobs/$($failedJob.id)/retry"
# Expected: Returns new job ID
```

### 15. Logs API
```powershell
curl http://localhost:8080/api/logs
# Expected: Returns array of log entries
```

### 16. WebSocket Connection
```powershell
# Manual test: Open browser to http://localhost:8080
# Open browser console and check WebSocket connection
# Expected: WebSocket connects and receives job updates
```

## Success Criteria

- [ ] All API endpoints return 200 status
- [ ] Downloads execute and create files
- [ ] Job status updates correctly
- [ ] File browser shows downloaded files
- [ ] Settings persist across requests
- [ ] System metrics display accurate data
- [ ] Job control operations work as expected

## Common Issues

### Downloads Not Starting
- Check: Is Python/gytmdl installed in container?
- Check: Are config files readable?
- Check: Is working directory correct (/app)?

### Files Not Appearing
- Check: Is downloads directory created?
- Check: Is file path correct in backend?
- Check: Are files being saved to expected location?

### Job Stuck in "Running"
- Check: Python process status in container
- Check: Container logs for errors
- Check: Job logs for failure messages
