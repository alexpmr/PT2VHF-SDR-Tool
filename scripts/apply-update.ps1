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
    [string]$Version = '',
    [string]$ReadyFile = ''
)
$ErrorActionPreference = 'Stop'
$resultFile = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-result.txt'
$setupLog = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-setup.log'
$status = 'erro'
$detail = ''
$traceFile = Join-Path $env:TEMP 'PT2VHF-SDR-Tool-ota-helper.log'
function Write-Phase([string]$phase, [string]$detail = '') {
    try {
        Add-Content -LiteralPath $traceFile -Value ((Get-Date -Format o) + ' | PID=' + $PID + ' | ' + $phase + ' | ' + $detail) -Encoding UTF8
    } catch { }
}
Write-Phase 'LAUNCHED' ('mode=' + $Mode + ' wait_pid=' + $WaitPid + ' version=' + $Version)

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
    if ($WaitPid -lt 1 -or -not $Package -or -not $Executable) { throw 'Parâmetros OTA incompletos.' }
    if ($ReadyFile) { Set-Content -LiteralPath $ReadyFile -Value 'READY' -Encoding UTF8 }
    Write-Phase 'READY' 'Auxiliar ativo; aguardando encerramento do SDR.'
    $children = @(Get-Descendants $WaitPid | Where-Object { $_ -ne $PID })
    Write-Phase 'WAIT_PARENT' ('PID principal: ' + $WaitPid + '; filhos: ' + $children.Count)
    $left = Wait-Exit @($WaitPid) 25
    if ($left.Count -gt 0) {
        # Only the original, exact executable may be force-closed after
        # a graceful 25s shutdown timeout. Never terminate unrelated PIDs.
        $owner = Get-Process -Id $WaitPid -ErrorAction SilentlyContinue
        if (-not $owner -or -not $owner.Path -or
            -not [string]::Equals($owner.Path, $Executable,
                [System.StringComparison]::OrdinalIgnoreCase)) {
            throw 'Processo em execução não corresponde ao aplicativo SDR esperado.'
        }
        Write-Phase 'FORCE_CLOSE_OWN_APP' ('PID ' + $WaitPid)
        Stop-Process -Id $WaitPid -Force -ErrorAction Stop
        $left = Wait-Exit @($WaitPid) 8
        if ($left.Count -gt 0) { throw 'O PT2VHF SDR Tool não fechou para atualização.' }
    }
    # Do not wait for every subprocess: long-lived SDR/decoder children caused
    # the former 90-second silent hang before installing. Restart Manager in
    # Inno Setup handles file locks without killing unrelated programs.
    Write-Phase 'PARENT_EXITED' 'Aplicativo encerrado; iniciando atualização.'
    if ($Mode -eq 'Setup') {
        if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) { throw 'Instalador ausente.' }
        Write-Phase 'SETUP_START' ('Executando instalador com progresso visível: ' + $Package)
        $setupArgs = @('/SILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/SP-', '/CLOSEAPPLICATIONS', "/LOG=`"$setupLog`"")
        if ($Destination) { $setupArgs += "/DIR=`"$Destination`"" }
        $p = Start-Process -FilePath $Package -ArgumentList $setupArgs -Wait -PassThru
        Write-Phase 'SETUP_EXIT' ('ExitCode=' + $p.ExitCode)
        if ($p.ExitCode -ne 0) { throw "Instalador terminou com codigo $($p.ExitCode) (log: $setupLog)" }
    } else {
        Write-Phase 'PORTABLE_START' 'Substituindo executável portátil verificado.'
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
    Write-Phase 'PACKAGE_DONE' ('Mode=' + $Mode)
    $status = 'ok'
    $detail = "Atualizado para a versao $Version."
} catch {
    $detail = $_.Exception.Message
    Write-Phase 'ERROR' $detail
    "Falha ao instalar atualizacao PT2VHF SDR Tool: $detail" | Out-File -FilePath (Join-Path $env:TEMP 'PT2VHF-SDR-Tool-update-error.txt') -Encoding UTF8
} finally {
    Write-Phase 'RESULT' ($status + ' ' + $Version + ' ' + $detail)
    "$status`n$Version`n$detail" | Out-File -FilePath $resultFile -Encoding UTF8
    if ($Executable -and (Test-Path -LiteralPath $Executable)) {
        Write-Phase 'RELAUNCH' ('Executável: ' + $Executable)
        try { Start-Process -FilePath $Executable }
        catch { Write-Phase 'RELAUNCH_ERROR' $_.Exception.Message }
    }
}
