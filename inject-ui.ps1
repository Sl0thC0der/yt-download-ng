# Script to inject the enhanced UI into main.rs

$uiFile = "web-backend\ui-enhanced.html"
$mainFile = "web-backend\src\main.rs"
$outputFile = "web-backend\src\main-new.rs"

# Read the UI content
$uiContent = Get-Content $uiFile -Raw

# Escape special characters for Rust raw string
$uiContent = $uiContent -replace '\\', '\\'
$uiContent = $uiContent -replace '"', '\"'

# Read main.rs up to line 369 (before const UI_HTML)
$mainContent = Get-Content $mainFile
$beforeUI = $mainContent[0..368]

# Create the new UI constant
$newUIConst = @"
const UI_HTML: &str = r#"$uiContent"#;
"@

# Combine everything
$finalContent = $beforeUI -join "`n"
$finalContent += "`n`n"
$finalContent += $newUIConst

# Write to new file
$finalContent | Set-Content $outputFile -NoNewline

Write-Host "Successfully created $outputFile"
Write-Host "Now run: Move-Item $outputFile $mainFile -Force"
