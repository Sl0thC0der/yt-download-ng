$files = Get-ChildItem -Path "C:\Users\TiHa\.git\ytdl-web\config" -Filter "*.json" -Recurse

foreach ($file in $files) {
    $content = Get-Content $file.FullName -Raw
    $newContent = $content -replace 'config\\\\cookies\.txt', 'config/cookies.txt'
    Set-Content -Path $file.FullName -Value $newContent -NoNewline
    Write-Host "Fixed: $($file.FullName)"
}

Write-Host "Done!"
