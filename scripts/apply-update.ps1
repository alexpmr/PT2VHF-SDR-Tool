# PT2VHF SDR Tool: auxiliar externo de atualizacao (mesmo processo dos demais programas PT2VHF).
# Chamado somente depois do SHA-256 verificado.
# Windows 10/11. Never delete portable data/.
# Espera a arvore de processos do app, encerra somente filhos do proprio SDR Tool que nao sairem,
# instala com log, grava o resultado e sempre reabre o programa.
param(
    [int]$WaitPid,
    [string]$Package,
    [string]$Destination,
    [string]$Executable,
    [ValidateSet('Portable','Setup')][string]$Mode,
    [string]$Version = ''
)
$ErrorActionPreference = 'Stop'
$resultFile = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-result.txt'
$setupLog = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-setup.log'
$status = 'erro'
$detail = ''

function Write-TestOtaPhase([string]$phase) {
    # CI-only phase markers; no paths, PIDs, arguments or configuration values.
    if ($env:PT2VHF_TEST_OTA_TRACE -ne '1') { return }
    try {
        $trace = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-ota-helper-trace.log'
        "$(Get-Date -Format o) $phase" | Add-Content -LiteralPath $trace -Encoding UTF8
    } catch {
        # Diagnostics must never alter update behavior.
    }
}

function Get-Descendants([int]$root) {
    # Instantaneo da arvore enquanto o app ainda existe (PIDs dos filhos e netos).
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Select-Object ProcessId, ParentProcessId)
    $found = New-Object System.Collections.Generic.List[int]
    $queue = New-Object System.Collections.Generic.Queue[int]
    $queue.Enqueue($root)
    while ($queue.Count -gt 0) {
        $p = $queue.Dequeue()
        foreach ($c in $all) {
            # O auxiliar PowerShell é filho do aplicativo: nunca espere ou mate o próprio auxiliar.
            if ([int]$c.ProcessId -eq $PID) { continue }
            if ($c.ParentProcessId -eq $p -and -not $found.Contains([int]$c.ProcessId)) {
                $found.Add([int]$c.ProcessId); $queue.Enqueue([int]$c.ProcessId)
            }
        }
    }
    return $found
}

function Wait-Exit([int[]]$pids, [int]$seconds) {
    for ($i = 0; $i -lt $seconds; $i++) {
        $alive = @($pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($alive.Count -eq 0) { return @() }
        Start-Sleep -Seconds 1
    }
    return @($pids | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
}

try {
    Write-TestOtaPhase 'start'
    $children = @(Get-Descendants $WaitPid | Where-Object { $_ -ne $PID })
    Write-TestOtaPhase 'wait-parent-start'
    $left = Wait-Exit (@($WaitPid) + $children) 90
    Write-TestOtaPhase 'wait-parent-end'
    if ($left.Count -gt 0) {
        # Somente processos que eram filhos do SDR Tool; nunca de outros programas.
        foreach ($childProcessId in $left) {
            if ($childProcessId -ne $WaitPid -and $childProcessId -ne $PID) {
                Stop-Process -Id $childProcessId -Force -ErrorAction SilentlyContinue
            }
        }
        $left = Wait-Exit $left 15
        if ($left -contains $WaitPid) { throw 'O PT2VHF SDR Tool nao fechou a tempo. Feche-o e instale manualmente.' }
    }
    if ($Mode -eq 'Setup') {
        Write-TestOtaPhase 'setup-start'
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) { throw 'Instalador ausente.' }
        $setupArgs = @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CLOSEAPPLICATIONS', "/LOG=`"$setupLog`"")
        if ($Destination) { $setupArgs += "/DIR=`"$Destination`"" }
        $p = Start-Process -FilePath $Package -ArgumentList $setupArgs -Wait -PassThru
        Write-TestOtaPhase 'setup-process-exited'
        if ($p.ExitCode -ne 0) { throw "Instalador terminou com codigo $($p.ExitCode) (log: $setupLog)" }
    } else {
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf) -or
            -not $Package.EndsWith('.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Portable EXE verificado nao encontrado.'
        }
        if (-not $Executable.EndsWith('-Portable.exe', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Destino nao e a edicao portable onefile.'
        }
        $backup = $Executable + '.previous'
        if (Test-Path -LiteralPath $backup) { Remove-Item -LiteralPath $backup -Force }
        if (Test-Path -LiteralPath $Executable) {
            Copy-Item -LiteralPath $Executable -Destination $backup -Force
        }
        $copied = $false
        for ($i = 0; $i -lt 10 -and -not $copied; $i++) {
            try { Copy-Item -LiteralPath $Package -Destination $Executable -Force; $copied = $true }
            catch { Start-Sleep -Seconds 2 }
        }
        if (-not $copied) {
            if (Test-Path -LiteralPath $backup) { Copy-Item -LiteralPath $backup -Destination $Executable -Force }
            throw 'Nao foi possivel substituir o EXE portatil (arquivo em uso).'
        }
        # Configuracoes e memorias ficam em %APPDATA%\PT2VHF-SDR-Tool e nunca sao tocadas.
    }
    Write-TestOtaPhase 'apply-success'
    $status = 'ok'
    $detail = "Atualizado para a versao $Version."
} catch {
    Write-TestOtaPhase 'apply-error'
    $detail = $_.Exception.Message
    "Falha ao instalar atualizacao PT2VHF SDR Tool: $detail" | Out-File -FilePath (Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-error.txt') -Encoding UTF8
} finally {
    Write-TestOtaPhase 'result-write'
    "$status`n$Version`n$detail" | Out-File -FilePath $resultFile -Encoding UTF8
    if ($Executable -and (Test-Path -LiteralPath $Executable)) {
        Write-TestOtaPhase 'relaunch-start'
        Start-Process -FilePath $Executable
    }
}
