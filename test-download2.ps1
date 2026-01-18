$body = @{
    url = "https://music.youtube.com/watch?v=kJQP7kiw5Fk"
    profile = "gytmdl"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/download" -Body $body -ContentType "application/json"
    Write-Host "Job ID: $($response.data)"
    Start-Sleep -Seconds 30
    
    $job = (Invoke-RestMethod -Uri "http://localhost:8080/api/jobs/$($response.data)").data
    Write-Host "`nStatus: $($job.status)"
    Write-Host "Progress: $($job.progress)%"
    Write-Host "`n--- Last 5 Logs ---"
    $job.logs | Select-Object -Last 5 | ForEach-Object { Write-Host $_ }
} catch {
    Write-Host "Error: $_"
}
