[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$ConfigPath,

    [ValidateSet('Check', 'Run')]
    [string]$Mode = 'Run',

    [string]$ExecutablePath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$resolvedConfig = (Resolve-Path -LiteralPath $ConfigPath).Path
$operation = if ($Mode -eq 'Check') { '--check-automation' } else { '--run-automation' }

if ($ExecutablePath) {
    $program = (Resolve-Path -LiteralPath $ExecutablePath).Path
    $arguments = @($operation, $resolvedConfig)
}
else {
    $standalone = Join-Path $PSScriptRoot 'dist\BrowserBookmarkTool.exe'
    $sourceModule = Join-Path $PSScriptRoot 'browser_bookmark_sync.py'
    $standaloneIsCurrent =
        (Test-Path -LiteralPath $standalone -PathType Leaf) -and
        ((Get-Item -LiteralPath $standalone).LastWriteTimeUtc -ge (Get-Item -LiteralPath $sourceModule).LastWriteTimeUtc)
    if ($standaloneIsCurrent) {
        $program = $standalone
        $arguments = @($operation, $resolvedConfig)
    }
    else {
        $pythonLauncher = Get-Command py, python3, python -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($null -eq $pythonLauncher) {
            throw 'Python 3.10 or newer is required when a current standalone executable is unavailable.'
        }
        $program = $pythonLauncher.Source
        $arguments = @($sourceModule, $operation, $resolvedConfig)
    }
}

& $program @arguments
$automationExitCode = $LASTEXITCODE
if ($null -eq $automationExitCode) {
    throw 'The browser bookmark automation process did not return an exit code.'
}
exit $automationExitCode
