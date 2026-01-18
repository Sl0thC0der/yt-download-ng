$body = @{
    url = "https://music.youtube.com/watch?v=jNQXAC9IVRw"
    profile = "gytmdl"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Method Post -Uri "http://localhost:8080/api/download" -Body $body -ContentType "application/json"
    Write-Host "Response: $($response | ConvertTo-Json)"
} catch {
    Write-Host "Error: $_"
    Write-Host "Response: $($_.ErrorDetails.Message)"
}
