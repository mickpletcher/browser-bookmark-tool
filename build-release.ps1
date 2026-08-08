[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory)]
    [string]$OutputDirectory,

    [ValidateSet('Unsigned', 'Prepare', 'Finalize')]
    [string]$Mode = 'Unsigned',

    [string]$PythonCommand
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($PythonCommand)) {
    $PythonCommand = if ($env:GITHUB_ACTIONS -eq 'true') {
        'python'
    }
    elseif (Get-Command py -ErrorAction SilentlyContinue) {
        'py'
    }
    else {
        'python'
    }
}

$projectFile = Join-Path $PSScriptRoot 'pyproject.toml'
$projectVersion = & $PythonCommand -c "import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['version'])" $projectFile
if ($LASTEXITCODE -ne 0) {
    throw 'Unable to read the project version.'
}
if ($projectVersion.Trim() -ne $Version) {
    throw "Requested version $Version does not match pyproject.toml version $($projectVersion.Trim())."
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
$outputExists = Test-Path -LiteralPath $resolvedOutput
if ($Mode -eq 'Finalize' -and -not $outputExists) {
    throw "Prepared release directory does not exist: $resolvedOutput"
}
if ($Mode -ne 'Finalize' -and $outputExists) {
    throw "Output directory already exists: $resolvedOutput"
}

$nameSuffix = if ($Mode -eq 'Unsigned') { '-unsigned' } else { '' }
$executableName = "BrowserBookmarkTool-$Version$nameSuffix.exe"
$sbomName = "browser-bookmark-tool-$Version.cdx.json"
$executablePath = Join-Path $resolvedOutput $executableName
$sbomPath = Join-Path $resolvedOutput $sbomName
$buildRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("browser-bookmark-tool-release-" + [guid]::NewGuid())
$workPath = Join-Path $buildRoot 'work'
$specPath = Join-Path $buildRoot 'spec'
$distPath = Join-Path $buildRoot 'dist'
$packageRoot = Join-Path $buildRoot 'package'
$versionFilePath = Join-Path $buildRoot 'version-info.txt'
$virtualEnvironment = Join-Path $buildRoot 'venv'
$releasePython = Join-Path $virtualEnvironment 'Scripts\python.exe'
$createdOutput = $Mode -ne 'Finalize'
$completed = $false

try {
    New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null

    if ($Mode -ne 'Finalize') {
        New-Item -ItemType Directory -Path $workPath, $specPath, $distPath, $resolvedOutput -Force | Out-Null

        & $PythonCommand -m venv $virtualEnvironment
        if ($LASTEXITCODE -ne 0) {
            throw "Release environment creation failed with exit code $LASTEXITCODE."
        }
        $releaseDependenciesJson = & $PythonCommand -c "import json, pathlib, sys, tomllib; print(json.dumps(tomllib.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))['project']['optional-dependencies']['release']))" $projectFile
        if ($LASTEXITCODE -ne 0) {
            throw 'Unable to read release dependencies.'
        }
        $releaseDependencies = @($releaseDependenciesJson | ConvertFrom-Json)
        & $releasePython -m pip install --disable-pip-version-check @releaseDependencies
        if ($LASTEXITCODE -ne 0) {
            throw "Release dependency installation failed with exit code $LASTEXITCODE."
        }

        $versionParts = @($Version.Split('.') | ForEach-Object { [int]$_ }) + 0
        $versionTuple = "($($versionParts[0]), $($versionParts[1]), $($versionParts[2]), $($versionParts[3]))"
        $versionInfo = @"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$versionTuple,
    prodvers=$versionTuple,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'Mick Pletcher'),
          StringStruct('FileDescription', 'Browser Bookmark Tool'),
          StringStruct('FileVersion', '$Version'),
          StringStruct('InternalName', 'BrowserBookmarkTool'),
          StringStruct('LegalCopyright', 'Copyright (c) 2026 Mick Pletcher'),
          StringStruct('OriginalFilename', 'BrowserBookmarkTool.exe'),
          StringStruct('ProductName', 'Browser Bookmark Tool'),
          StringStruct('ProductVersion', '$Version')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@
        Set-Content -LiteralPath $versionFilePath -Value $versionInfo -Encoding utf8NoBOM

        & $releasePython -m PyInstaller `
            --noconfirm `
            --clean `
            --onefile `
            --name BrowserBookmarkTool `
            --version-file $versionFilePath `
            --workpath $workPath `
            --specpath $specPath `
            --distpath $distPath `
            (Join-Path $PSScriptRoot 'browser_bookmark_sync.py')
        if ($LASTEXITCODE -ne 0) {
            throw "Standalone build failed with exit code $LASTEXITCODE."
        }
        Copy-Item -LiteralPath (Join-Path $distPath 'BrowserBookmarkTool.exe') -Destination $executablePath

        $unsignedStatus = (Get-AuthenticodeSignature -LiteralPath $executablePath).Status
        if ($unsignedStatus -ne 'NotSigned') {
            throw "Prepared executable had unexpected Authenticode status: $unsignedStatus"
        }

        $versionMetadata = (Get-Item -LiteralPath $executablePath).VersionInfo
        $expectedMetadata = [ordered]@{
            FileDescription = 'Browser Bookmark Tool'
            OriginalFilename = 'BrowserBookmarkTool.exe'
            ProductName = 'Browser Bookmark Tool'
            ProductVersion = $Version
        }
        foreach ($entry in $expectedMetadata.GetEnumerator()) {
            if ($versionMetadata.($entry.Key) -ne $entry.Value) {
                throw "Prepared executable metadata $($entry.Key) was '$($versionMetadata.($entry.Key))'; expected '$($entry.Value)'."
            }
        }

        & $releasePython -m cyclonedx_py environment `
            --pyproject $projectFile `
            --mc-type application `
            --sv 1.6 `
            --output-reproducible `
            --of JSON `
            -o $sbomPath `
            --validate
        if ($LASTEXITCODE -ne 0) {
            throw "CycloneDX SBOM generation failed with exit code $LASTEXITCODE."
        }
        $sbomText = Get-Content -LiteralPath $sbomPath -Raw
        $privateMarkers = @('file://', $PSScriptRoot, $env:USERPROFILE) | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
        foreach ($marker in $privateMarkers) {
            if ($sbomText.Contains($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
                throw "The generated SBOM contains a prohibited local path marker: $marker"
            }
        }

        if ($Mode -eq 'Prepare') {
            $completed = $true
            [ordered]@{
                executable = $executablePath
                prepared = $true
                sbom = $sbomPath
                version = $Version
            } | ConvertTo-Json -Compress
            return
        }
    }
    else {
        if (-not (Test-Path -LiteralPath $executablePath) -or -not (Test-Path -LiteralPath $sbomPath)) {
            throw 'Prepared executable or SBOM is missing.'
        }
        $expectedSubject = $env:WINDOWS_SIGNING_SUBJECT
        if ([string]::IsNullOrWhiteSpace($expectedSubject)) {
            throw 'Signature verification requires WINDOWS_SIGNING_SUBJECT.'
        }
        $verifiedSignature = Get-AuthenticodeSignature -LiteralPath $executablePath
        $hasCodeSigningUsage = $verifiedSignature.SignerCertificate -and
            $verifiedSignature.SignerCertificate.EnhancedKeyUsageList.ObjectId.Value -contains '1.3.6.1.5.5.7.3.3'
        $subjectMatches = $verifiedSignature.SignerCertificate -and
            $verifiedSignature.SignerCertificate.Subject.Equals($expectedSubject, [System.StringComparison]::OrdinalIgnoreCase)
        if ($verifiedSignature.Status -ne 'Valid' -or
            -not $hasCodeSigningUsage -or
            -not $subjectMatches -or
            -not $verifiedSignature.TimeStamperCertificate) {
            throw "The signed executable failed Authenticode verification. Status: $($verifiedSignature.Status)"
        }
    }

    Copy-Item -LiteralPath $executablePath -Destination $packageRoot
    Copy-Item -LiteralPath $sbomPath -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'LICENSE') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'SECURITY.md') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'PRIVACY.md') -Destination $packageRoot
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'CODE_SIGNING_POLICY.md') -Destination $packageRoot

    $archiveName = "browser-bookmark-tool-$Version-windows-x64$nameSuffix.zip"
    $archivePath = Join-Path $resolvedOutput $archiveName
    Compress-Archive -Path (Join-Path $packageRoot '*') -DestinationPath $archivePath -CompressionLevel Optimal

    $checksumPath = Join-Path $resolvedOutput 'SHA256SUMS'
    $checksumTargets = @($executablePath, $archivePath, $sbomPath)
    $checksumLines = foreach ($target in $checksumTargets) {
        $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
        "$hash  $([System.IO.Path]::GetFileName($target))"
    }
    Set-Content -LiteralPath $checksumPath -Value $checksumLines -Encoding utf8NoBOM

    foreach ($line in Get-Content -LiteralPath $checksumPath) {
        if ($line -notmatch '^([a-f0-9]{64})  (.+)$') {
            throw "Invalid checksum line: $line"
        }
        $targetPath = Join-Path $resolvedOutput $Matches[2]
        $actualHash = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $Matches[1]) {
            throw "Checksum verification failed for $($Matches[2])."
        }
    }

    $completed = $true
    [ordered]@{
        archive = $archivePath
        checksum = $checksumPath
        executable = $executablePath
        sbom = $sbomPath
        signed = $Mode -eq 'Finalize'
        version = $Version
    } | ConvertTo-Json -Compress
}
finally {
    if (Test-Path -LiteralPath $buildRoot) {
        Remove-Item -LiteralPath $buildRoot -Recurse -Force
    }
    if (-not $completed -and $createdOutput -and (Test-Path -LiteralPath $resolvedOutput)) {
        Remove-Item -LiteralPath $resolvedOutput -Recurse -Force
    }
}
