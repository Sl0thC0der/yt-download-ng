# Host Download Wrapper for yt-download-container-ng
# This script runs on the Windows host and performs actual downloads
# Called by the container via mounted volume

param(
    [Parameter(Mandatory=$true)]
    [string]$Url,
    
    [Parameter(Mandatory=$true)]
    [string]$Profile,
    
    [Parameter(Mandatory=$true)]
    [string]$JobId
)

$hostRepoPath = "C:\Users\TiHa\.git\youtube-downloader-ng"
$containerDownloadPath = "C:\Users\TiHa\.git\ytdl-web\downloads"

# Change to host repo directory
Set-Location $hostRepoPath

# Run the download
Write-Host "[HOST] Starting download for job $JobId"
Write-Host "[HOST] URL: $Url"
Write-Host "[HOST] Profile: $Profile"

try {
    & python ytdl.py download $Url -p $Profile
    $exitCode = $LASTEXITCODE
    
    if ($exitCode -eq 0) {
        Write-Host "[HOST] Download completed successfully"
        
        # Copy downloaded files to container's download folder
        if (Test-Path "$hostRepoPath\downloads") {
            Write-Host "[HOST] Copying files to container download folder..."
            Copy-Item -Path "$hostRepoPath\downloads\*" -Destination $containerDownloadPath -Recurse -Force
            Write-Host "[HOST] Files copied successfully"
        }
    } else {
        Write-Host "[HOST] Download failed with exit code $exitCode"
    }
    
    exit $exitCode
} catch {
    Write-Host "[HOST] Error: $_"
    exit 1
}
