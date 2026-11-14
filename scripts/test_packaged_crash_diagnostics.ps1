# P0: exercise the real packaged GUI startup/shutdown path, not --selftest.
# Synthetic simulator only; this does not replace physical SDR stability testing.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string[]]$Executables
)

$ErrorActionPreference = 'Stop'
$root = Join-Path $env:RUNNER_TEMP ('pt2vhf-packaged-diagnostics-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root -Force | Out-Null
$oldAppData = $env:APPDATA
$oldDialogs = $env:PT2VHF_NO_STARTUP_DIALOGS
$oldAutoconnect = $env:PT2VHF_NO_AUTOCONNECT

try {
    $env:PT2VHF_NO_STARTUP_DIALOGS = '1'
    $env:PT2VHF_NO_AUTOCONNECT = '1'
    $index = 0
    foreach ($exe in $Executables) {
        $index++
        $resolved = (Resolve-Path -LiteralPath $exe -ErrorAction Stop).Path
        $env:APPDATA = Join-Path $root "profile-$index"
        New-Item -ItemType Directory -Path $env:APPDATA -Force | Out-Null
        $shot = Join-Path $root "gui-$index.png"
        $process = Start-Process -FilePath $resolved -ArgumentList @('--screenshot', ('"' + $shot + '"')) -PassThru
        try {
            if (-not $process.WaitForExit(60000)) {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
                throw "Packaged GUI timed out (60 s): $(Split-Path -Leaf $resolved)"
            }
            if ($process.ExitCode -ne 0) {
                throw "Packaged GUI exited with code $($process.ExitCode): $(Split-Path -Leaf $resolved)"
            }
        } finally {
            $process.Dispose()
        }
        $log = Join-Path $env:APPDATA 'PT2VHF-SDR-Tool\crash-diagnostics.log'
        if (-not (Test-Path -LiteralPath $log)) { throw 'Packaged GUI did not create crash-diagnostics.log' }
        $data = Get-Content -LiteralPath $log -Raw
        # The --screenshot smoke now closes the MainWindow explicitly.
        # Require every cleanup stage in order; a plain QApplication.quit()
        # would skip closeEvent and must not pass this diagnostic gate.
        $markers = @(
            'START pid=',
            'WINDOW-CLOSE stage=begin',
            'WINDOW-CLOSE stage=engine-stopped',
            'WINDOW-CLOSE stage=audio-stopped',
            'WINDOW-CLOSE stage=end',
            'QT-ABOUT-TO-QUIT',
            'QT-LOOP-RETURN code=0'
        )
        $cursor = -1
        foreach ($marker in $markers) {
            $position = $data.IndexOf($marker, $cursor + 1, [System.StringComparison]::Ordinal)
            if ($position -lt 0) { throw "Packaged GUI missing or out-of-order diagnostic marker: $marker" }
            $cursor = $position
        }
        if ($data -match 'UNHANDLED|THREAD-ERROR|Fatal Python error|CLEAN-EXIT') {
            throw 'Packaged GUI diagnostics contain an error or misleading clean-exit marker'
        }
        if (-not (Test-Path -LiteralPath $shot) -or (Get-Item -LiteralPath $shot).Length -eq 0) {
            throw 'Packaged GUI did not produce a screenshot'
        }
        Write-Output "P0-PACKAGED-GUI-DIAGNOSTICS=PASS exe=$(Split-Path -Leaf $resolved) (synthetic simulator, no SDR hardware)"
    }
} finally {
    $env:APPDATA = $oldAppData
    $env:PT2VHF_NO_STARTUP_DIALOGS = $oldDialogs
    $env:PT2VHF_NO_AUTOCONNECT = $oldAutoconnect
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
