$ErrorActionPreference = 'Stop'

py -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Development dependency installation failed with exit code $LASTEXITCODE."
}

$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("browser-bookmark-tool-build-" + [guid]::NewGuid())
$workPath = Join-Path $buildRoot "work"
$specPath = Join-Path $buildRoot "spec"
New-Item -ItemType Directory -Path $workPath, $specPath -Force | Out-Null

py -m PyInstaller `
    --noconfirm `
    --onefile `
    --name BrowserBookmarkTool `
    --workpath $workPath `
    --specpath $specPath `
    --distpath (Join-Path $PSScriptRoot "dist") `
    (Join-Path $PSScriptRoot "browser_bookmark_sync.py")

if ($LASTEXITCODE -ne 0) {
    throw "Standalone build failed with exit code $LASTEXITCODE. Build workspace: $buildRoot"
}

Write-Host "Built dist\BrowserBookmarkTool.exe"
