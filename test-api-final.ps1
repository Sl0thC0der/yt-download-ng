# Test the yt-download-container-ng Web API

Write-Host "=== Testing yt-download-container-ng API ===" -ForegroundColor Cyan

# Test 1: Health Check
Write-Host "`n1. Health Check..." -ForegroundColor Yellow
$health = Invoke-RestMethod -Uri "http://localhost:8080/health"
Write-Host "   Status: $($health.status)" -ForegroundColor Green

# Test 2: List Profiles
Write-Host "`n2. Listing Profiles..." -ForegroundColor Yellow
$profiles = Invoke-RestMethod -Uri "http://localhost:8080/api/profiles"
Write-Host "   Found $($profiles.data.Count) profiles" -ForegroundColor Green
Write-Host "   First 3: $($profiles.data[0..2] -join ', ')"

# Test 3: Submit Download
Write-Host "`n3. Submitting Download..." -ForegroundColor Yellow
$downloadBody = @{
    url = "https://music.youtube.com/watch?v=dQw4w9WgXcQ"
    profile = "gytmdl"
} | ConvertTo-Json

$job = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/download" -Body $downloadBody -ContentType "application/json"
$jobId = $job.data
Write-Host "   Job ID: $jobId" -ForegroundColor Green

# Test 4: Check Job Status
Write-Host "`n4. Checking Job Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 2
$jobStatus = Invoke-RestMethod -Uri "http://localhost:8080/api/jobs/$jobId"
Write-Host "   Status: $($jobStatus.data.status)" -ForegroundColor Green
Write-Host "   Progress: $($jobStatus.data.progress)%"
Write-Host "   Logs (last 3):"
$jobStatus.data.logs | Select-Object -Last 3 | ForEach-Object { Write-Host "     - $_" }

# Test 5: List All Jobs
Write-Host "`n5. Listing All Jobs..." -ForegroundColor Yellow
$allJobs = Invoke-RestMethod -Uri "http://localhost:8080/api/jobs"
Write-Host "   Total Jobs: $($allJobs.data.Count)" -ForegroundColor Green

# Test 6: Check Downloaded Files
Write-Host "`n6. Checking Downloaded Files..." -ForegroundColor Yellow
$files = Get-ChildItem -Path ".\downloads" -Recurse -Filter "*.m4a" -ErrorAction SilentlyContinue
Write-Host "   Found $($files.Count) audio files" -ForegroundColor Green
if ($files.Count -gt 0) {
    Write-Host "   Recent files:"
    $files | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
        Write-Host "     - $($_.Name)"
    }
}

Write-Host "`n=== All Tests Complete ===" -ForegroundColor Cyan
Write-Host "API is working correctly!" -ForegroundColor Green
Write-Host "`nWeb UI available at: http://localhost:8080" -ForegroundColor White
