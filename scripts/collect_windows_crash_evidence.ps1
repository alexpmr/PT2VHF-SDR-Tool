<#
.SYNOPSIS
Collects a privacy-minimized Windows Application Error / WER summary for the
PT2VHF SDR Tool P0 crash investigation. Does not upload data or copy user logs.

.EXAMPLE
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\collect_windows_crash_evidence.ps1 -Days 7

The summary contains timestamps, event IDs, executable/module basenames and
exception codes only. It excludes file paths, usernames, event messages,
crash dumps and application configuration. Review before sharing.
#>
[CmdletBinding()]
param(
    [ValidateRange(1, 30)]
    [int]$Days = 7,
    [string]$OutputFile = (Join-Path $env:TEMP 'PT2VHF-SDR-WER-summary.txt')
)

$ErrorActionPreference = 'Stop'
$since = (Get-Date).AddDays(-$Days)
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('PT2VHF SDR Tool - Windows crash event summary')
$lines.Add('Generated UTC: ' + (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ'))
$lines.Add("Window: last $Days day(s)")
$lines.Add('No telemetry, uploads, full event messages, user paths or crash dumps.')
$lines.Add('')

$events = @()
$querySucceeded = $true
$maxEvents = 500
try {
    $events = @(Get-WinEvent -FilterHashtable @{
        LogName = 'Application'
        Id = @(1000, 1001)
        StartTime = $since
    } -MaxEvents $maxEvents -ErrorAction Stop)
} catch {
    $querySucceeded = $false
    # An empty Application log is common on clean CI machines. Never print
    # the exception text because Windows can embed local file paths in it.
    $lines.Add('Event query unavailable or no matching events. Check Event Viewer manually.')
}

$eventCount = 0
# Setup and Portable use different executable names; both must be recognized.
$appPattern = '(?i)^PT2VHF-SDR-Tool(?:-Portable)?(?:\.exe)?$'
$werPattern = '(?i)(?<![A-Za-z0-9_.-])PT2VHF-SDR-Tool(?:-Portable)?(?:\.exe)?(?![A-Za-z0-9_.-])'
if ($querySucceeded -and $events.Count -ge $maxEvents) {
    $lines.Add("WARNING: reached the $maxEvents-event query limit; older crashes may be omitted.")
}
foreach ($event in $events) {
    $provider = [string]$event.ProviderName
    if ($event.Id -eq 1000 -and $provider -eq 'Application Error') {
        $values = @($event.Properties | ForEach-Object { $_.Value })
        if ($values.Count -lt 7) { continue }
        $appName = [System.IO.Path]::GetFileName([string]$values[0])
        if ($appName -notmatch $appPattern) { continue }
        $module = [System.IO.Path]::GetFileName([string]$values[3])
        if (-not $module) { $module = 'unknown' }
        $code = [string]$values[6]
        if ($code -notmatch '^(?:0x)?[0-9a-fA-F]{8}$') { $code = 'unknown' }
        $utc = $event.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $lines.Add("UTC=$utc Event=1000 Application=$appName Module=$module Exception=$code")
        $eventCount++
    } elseif ($event.Id -eq 1001 -and $provider -eq 'Windows Error Reporting') {
        # Event 1001 has varying property layouts across Windows versions.
        # Match the application name in memory but never persist its message.
        if ([string]$event.Message -notmatch $werPattern) { continue }
        $utc = $event.TimeCreated.ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
        $lines.Add("UTC=$utc Event=1001 WindowsErrorReporting=present (details omitted)")
        $eventCount++
    }
}

if ($eventCount -eq 0) {
    if ($querySucceeded) {
        $lines.Add('No PT2VHF SDR Tool crash events found among the retrieved events.')
    } else {
        $lines.Add('Crash event status unknown because the event query failed.')
    }
}
$folder = Split-Path -Parent $OutputFile
if ($folder -and -not (Test-Path -LiteralPath $folder)) {
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
}
$lines | Set-Content -LiteralPath $OutputFile -Encoding UTF8
Write-Output "P0-WER-SUMMARY saved=$OutputFile events=$eventCount"
Write-Output 'Review the file before sharing. The existing pt2vhf-sdr.log must be reviewed separately.'
