# Smoke test Windows do auxiliar OTA portátil, inclusive o caso em que
# o próprio auxiliar é filho do processo que deve encerrar.
$ErrorActionPreference = 'Stop'
$root = Join-Path $env:TEMP ("pt2vhf-ota-smoke-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force -Path $root | Out-Null
$resultFile = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-result.txt'
$oldExe = Join-Path $root 'PT2VHF-SDR-Tool-Portable.exe'
$package = Join-Path $root 'package.exe'
$helper = Join-Path $PSScriptRoot 'apply-update.ps1'
$powershell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
$launcher = Join-Path $root 'launch-helper.ps1'
$env:PT2VHF_TEST_HELPER = $helper
$env:PT2VHF_TEST_DIR = $root
$env:PT2VHF_TEST_EXE = $oldExe

# O helper deve substituir um executável válido por outro válido sem abrir GUI.
Copy-Item (Join-Path $env:SystemRoot 'System32\hostname.exe') $oldExe
Copy-Item (Join-Path $env:SystemRoot 'System32\whoami.exe') $package
$originalHash = (Get-FileHash $oldExe -Algorithm SHA256).Hash
$packageHash = (Get-FileHash $package -Algorithm SHA256).Hash

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
  '-Mode', 'Portable', '-Version', '0.13.1'
)
Start-Process -FilePath $powershell -ArgumentList $argsForHelper -WindowStyle Hidden
# O auxiliar precisa enxergar o processo-pai vivo no snapshot WMI.
Start-Sleep -Seconds 3
'@ | Set-Content -Path $launcher -Encoding UTF8

function Invoke-OtaSmoke([string]$source) {
    $env:PT2VHF_TEST_PACKAGE = $source
    Remove-Item -LiteralPath $resultFile -Force -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $powershell -ArgumentList @(
        '-NoProfile', '-NonInteractive', '-File', ('"' + $launcher + '"')
    ) -Wait -PassThru
    if ($p.ExitCode -ne 0) { throw "Launcher OTA falhou: $($p.ExitCode)" }
    for ($i = 0; $i -lt 40; $i++) {
        if (Test-Path -LiteralPath $resultFile) { break }
        Start-Sleep -Seconds 1
    }
    if (-not (Test-Path -LiteralPath $resultFile)) {
        throw 'Helper OTA não concluiu em 40 segundos (possível deadlock com o próprio PID).'
    }
    return @(Get-Content -LiteralPath $resultFile -Encoding UTF8)
}

try {
    $result = Invoke-OtaSmoke $package
    if ($result[0].Trim() -ne 'ok') {
        throw "OTA Portable deveria funcionar: $($result -join ' | ')"
    }
    if ((Get-FileHash $oldExe -Algorithm SHA256).Hash -ne $packageHash) {
        throw 'O EXE portátil não foi substituído corretamente.'
    }
    if ((Get-FileHash ($oldExe + '.previous') -Algorithm SHA256).Hash -ne $originalHash) {
        throw 'O backup da versão anterior está incorreto.'
    }
    Write-Host 'OTA_PORTABLE_SMOKE=PASS (helper, substituição, backup e restart)'

    # Pacote inexistente: nenhuma alteração deve ser feita no EXE instalado.
    $result = Invoke-OtaSmoke (Join-Path $root 'missing.exe')
    if ($result[0].Trim() -ne 'erro') {
        throw "Pacote ausente deveria falhar: $($result -join ' | ')"
    }
    if ((Get-FileHash $oldExe -Algorithm SHA256).Hash -ne $packageHash) {
        throw 'Falha de atualização alterou o EXE instalado.'
    }
    Write-Host 'OTA_PORTABLE_FAILURE_SMOKE=PASS (pacote ausente preserva executável)'
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
