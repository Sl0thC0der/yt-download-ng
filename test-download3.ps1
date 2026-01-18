$body = @{
    url = "https://music.youtube.com/playlist?list=OLAK5uy_lV2bH0OHkf8eX_J03qt_z2axGlP1INVlw"
    profile = "gytmdl"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/download" -Body $body -ContentType "application/json"
    $jobId = $response.data
    Write-Host "Job ID: $jobId"
    Write-Host "Waiting for download to complete..."
    
    Start-Sleep -Seconds 45
    
    $job = (Invoke-RestMethod -Uri "http://localhost:8080/api/jobs/$jobId").data
    Write-Host "`nStatus: $($job.status)"
    Write-Host "Progress: $($job.progress)%"
    Write-Host "`n--- Last 10 Logs ---"
    $job.logs | Select-Object -Last 10 | ForEach-Object { Write-Host $_ }
    
    # Check if files were created
    Write-Host "`n--- Checking for downloaded files ---"
    if (Test-Path "C:\Users\TiHa\.git\ytdl-web\downloads") {
        $files = Get-ChildItem -Path "C:\Users\TiHa\.git\ytdl-web\downloads" -Recurse -File
        if ($files.Count -gt 0) {
            Write-Host "Found $($files.Count) file(s):"
            $files | ForEach-Object { Write-Host "  - $($_.FullName)" }
        } else {
            Write-Host "No files found in downloads directory"
        }
    } else {
        Write-Host "Downloads directory doesn't exist"
    }
} catch {
    Write-Host "Error: $_"
}
