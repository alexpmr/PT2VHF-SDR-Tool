# End-to-end Windows smoke for OTA Setup helper after the real Inno Setup build.
param([string]$Version = '0.13.1')
$ErrorActionPreference = 'Stop'
$setup = Join-Path $PSScriptRoot "..\dist\PT2VHF-SDR-Tool-v$Version-Win11-x64-Setup.exe"
$installed = Join-Path $env:LOCALAPPDATA 'Programs\PT2VHF SDR Tool\PT2VHF-SDR-Tool.exe'
$destination = Split-Path -Parent $installed
$helper = Join-Path $PSScriptRoot 'apply-update.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$resultFile = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-result.txt'
$root = Join-Path $env:TEMP ("pt2vhf-ota-setup-smoke-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $root | Out-Null
$launcher = Join-Path $root 'launch-setup-helper.ps1'
if (-not (Test-Path $setup) -or -not (Test-Path $installed)) {
    throw 'Instalador compilado ou instalação inicial não encontrados.'
}
$originalHash = (Get-FileHash $installed -Algorithm SHA256).Hash
$env:PT2VHF_TEST_HELPER = $helper
$env:PT2VHF_TEST_DIR = $destination
$env:PT2VHF_TEST_EXE = $installed
$env:PT2VHF_TEST_VERSION = $Version

@'
$ErrorActionPreference = 'Stop'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$argsForHelper = @(
  '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
  ('"' + $env:PT2VHF_TEST_HELPER + '"'),
  '-WaitPid', [string]$PID,
  '-Package', ('"' + $env:PT2VHF_TEST_PACKAGE + '"'),
  '-Destination', ('"' + $env:PT2VHF_TEST_DIR + '"'),
  '-Executable', ('"' + $env:PT2VHF_TEST_EXE + '"'),
  '-Mode', 'Setup', '-Version', $env:PT2VHF_TEST_VERSION
)
Start-Process -FilePath $powershell -ArgumentList $argsForHelper -WindowStyle Hidden
Start-Sleep -Seconds 3
'@ | Set-Content -Path $launcher -Encoding UTF8

function Stop-InstalledGui {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    foreach ($p in $all) {
        if ($p.ExecutablePath -and $p.ExecutablePath -ieq $installed) {
            Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-SetupSmoke([string]$source) {
    $env:PT2VHF_TEST_PACKAGE = $source
    Remove-Item -LiteralPath $resultFile -Force -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $powershell -ArgumentList @(
        '-NoProfile', '-NonInteractive', '-File', ('"' + $launcher + '"')
    ) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Launcher Setup falhou: $($p.ExitCode)" }
    for ($i = 0; $i -lt 100; $i++) {
        if (Test-Path -LiteralPath $resultFile) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $resultFile)) {
        throw 'Helper Setup não concluiu em 100 segundos.'
    }
    return @(Get-Content -LiteralPath $resultFile -Encoding UTF8)
}

try {
    $result = Invoke-SetupSmoke $setup
    if ($result[0].Trim() -ne 'ok') {
        throw "OTA Setup real falhou: $($result -join ' | ')"
    }
    Start-Sleep -Seconds 3
    $reopened = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ExecutablePath -and $_.ExecutablePath -ieq $installed })
    if ($reopened.Count -eq 0) {
        throw 'Instalador OTA terminou, mas o aplicativo não foi reaberto.'
    }
    Stop-InstalledGui
    if ((Get-FileHash $installed -Algorithm SHA256).Hash -ne $originalHash) {
        throw 'Reinstalação da mesma versão alterou o executável inesperadamente.'
    }
    $p = Start-Process -FilePath $installed -ArgumentList '--selftest' -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Autoteste pós-OTA Setup falhou: $($p.ExitCode)" }
    Write-Host 'OTA_SETUP_SMOKE=PASS (Inno, helper, restart e selftest)'

    $result = Invoke-SetupSmoke (Join-Path $root 'missing-setup.exe')
    if ($result[0].Trim() -ne 'erro') {
        throw "Pacote Setup ausente deveria falhar: $($result -join ' | ')"
    }
    if ((Get-FileHash $installed -Algorithm SHA256).Hash -ne $originalHash) {
        throw 'Falha OTA Setup alterou executável instalado.'
    }
    Stop-InstalledGui
    Write-Host 'OTA_SETUP_FAILURE_SMOKE=PASS (pacote ausente preserva instalação)'
} finally {
    Stop-InstalledGui
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
