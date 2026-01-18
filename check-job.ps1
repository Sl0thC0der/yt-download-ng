param([string]$jobId)

$response = Invoke-RestMethod -Uri "http://localhost:8080/api/jobs/$jobId"
$job = $response.data

Write-Host "Status: $($job.status)"
Write-Host "Progress: $($job.progress)%"
Write-Host "`n--- LOGS ---"
foreach ($log in $job.logs) {
    Write-Host $log
}
