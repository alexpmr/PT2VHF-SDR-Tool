# Deterministic Windows collector tests with synthetic Application Error/WER events.
# Never reads real user logs or uploads any data.
$ErrorActionPreference = 'Stop'
$collector = Join-Path $PSScriptRoot 'collect_windows_crash_evidence.ps1'
$folder = Join-Path $env:TEMP ('pt2vhf-wer-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $folder -Force | Out-Null
$global:PT2VHFWEREvents = @()
$global:PT2VHFWERThrow = $false

function New-MockEvent {
    param([int]$Id, [string]$Provider, [object[]]$Values, [string]$Message = '')
    $properties = @($Values | ForEach-Object { [pscustomobject]@{ Value = $_ } })
    return [pscustomobject]@{
        Id = $Id
        ProviderName = $Provider
        Properties = $properties
        Message = $Message
        TimeCreated = [datetime]::UtcNow
    }
}

# This function shadows the cmdlet only inside this PowerShell test process.
function global:Get-WinEvent {
    [CmdletBinding()]
    param([hashtable]$FilterHashtable, [int]$MaxEvents)
    if ($global:PT2VHFWERThrow) { throw 'C:\Users\private-user\sensitive-query-failure' }
    if ($FilterHashtable.LogName -ne 'Application' -or $MaxEvents -ne 500) {
        throw 'Unexpected event query contract'
    }
    return $global:PT2VHFWEREvents
}

function Assert-Contains {
    param([string]$Text, [string]$Expected)
    if (-not $Text.Contains($Expected)) { throw "Missing expected summary marker: $Expected" }
}
function Assert-NotContains {
    param([string]$Text, [string]$Forbidden)
    if ($Text.Contains($Forbidden)) { throw "Unexpected summary marker: $Forbidden" }
}
function Run-Collector {
    param([string]$Name)
    $file = Join-Path $folder ($Name + '.txt')
    & $collector -Days 7 -OutputFile $file | Out-Null
    if (-not (Test-Path -LiteralPath $file)) { throw "Missing summary for $Name" }
    return (Get-Content -LiteralPath $file -Raw)
}

try {
    $global:PT2VHFWEREvents = @(
        (New-MockEvent 1000 'Application Error' @('PT2VHF-SDR-Tool.exe', '0.13.3', 'x', 'C:\Users\private-user\KERNELBASE.dll', 'x', 'x', '0xc0000005')),
        (New-MockEvent 1000 'Application Error' @('PT2VHF-SDR-Tool-Portable.exe', '0.13.3', 'x', 'C:\Users\private-user\Qt6Core.dll', 'x', 'x', 'c0000374')),
        (New-MockEvent 1001 'Windows Error Reporting' @() 'Fault: C:\Users\private-user\PT2VHF-SDR-Tool-Portable.exe'),
        (New-MockEvent 1000 'Application Error' @('Other-App.exe', 'x', 'x', 'Other.dll', 'x', 'x', 'c0000005')),
        (New-MockEvent 1001 'Windows Error Reporting' @() 'PT2VHF-SDR-Tool-helper.exe'),
        (New-MockEvent 1000 'Application Error' @('PT2VHF-SDR-Tool.exe', 'x', 'x', 'C:\Users\private-user\Audio.dll', 'x', 'x', 'invalid-code'))
    )
    $data = Run-Collector 'mixed'
    Assert-Contains $data 'Application=PT2VHF-SDR-Tool.exe Module=KERNELBASE.dll Exception=0xc0000005'
    Assert-Contains $data 'Application=PT2VHF-SDR-Tool-Portable.exe Module=Qt6Core.dll Exception=c0000374'
    Assert-Contains $data 'Module=Audio.dll Exception=unknown'
    Assert-Contains $data 'Event=1001 WindowsErrorReporting=present'
    Assert-NotContains $data 'Other-App.exe'
    Assert-NotContains $data 'PT2VHF-SDR-Tool-helper.exe'
    Assert-NotContains $data 'private-user'
    if ((@($data -split "`n" | Where-Object { $_ -match 'Event=1000 ' })).Count -ne 3) {
        throw 'Expected exactly three matching Application Error records'
    }
    if ((@($data -split "`n" | Where-Object { $_ -match 'Event=1001 ' })).Count -ne 1) {
        throw 'Expected exactly one matching WER record'
    }

    $global:PT2VHFWEREvents = @()
    $empty = Run-Collector 'empty'
    Assert-Contains $empty 'No PT2VHF SDR Tool crash events found among the retrieved events.'

    $global:PT2VHFWERThrow = $true
    $failed = Run-Collector 'query-failure'
    Assert-Contains $failed 'Crash event status unknown because the event query failed.'
    Assert-NotContains $failed 'No PT2VHF SDR Tool crash events found'
    Assert-NotContains $failed 'private-user'
    $global:PT2VHFWERThrow = $false

    $global:PT2VHFWEREvents = @(1..500 | ForEach-Object {
        New-MockEvent 1000 'Application Error' @('Unrelated.exe', 'x', 'x', 'Other.dll', 'x', 'x', 'c0000005')
    })
    $limited = Run-Collector 'limit'
    Assert-Contains $limited 'WARNING: reached the 500-event query limit; older crashes may be omitted.'
} finally {
    Remove-Item -LiteralPath $folder -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item Function:\Get-WinEvent -ErrorAction SilentlyContinue
    Remove-Variable PT2VHFWEREvents -Scope Global -ErrorAction SilentlyContinue
    Remove-Variable PT2VHFWERThrow -Scope Global -ErrorAction SilentlyContinue
}
Write-Output 'P0-WER-COLLECTOR-TEST=PASS'
