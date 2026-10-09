@echo off
setlocal EnableExtensions DisableDelayedExpansion
title Urna Escolar - Reset
set "URNA_RESET_SCRIPT=%~f0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "$raw=Get-Content -LiteralPath $env:URNA_RESET_SCRIPT -Raw; & ([scriptblock]::Create(($raw -split '(?m)^# POWERSHELL_RESET\r?$',2)[1]))"
set "RESET_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %RESET_RESULT%
# POWERSHELL_RESET
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Assert-PlainTree([string]$Path) {
    $current = [IO.Path]::GetFullPath($Path)
    while ($current) {
        if (Test-Path -LiteralPath $current) {
            if ((Get-Item -LiteralPath $current -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
                throw 'A pasta contem link/juncao. Revise o caminho antes de limpar.'
            }
        }
        $current = Split-Path -Parent $current
    }
    if (Test-Path -LiteralPath $Path -PathType Container) {
        $pending = New-Object 'System.Collections.Generic.Stack[string]'
        $pending.Push($Path)
        while ($pending.Count -gt 0) {
            foreach ($item in Get-ChildItem -LiteralPath $pending.Pop() -Force) {
                if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                    throw 'A pasta contem link/juncao. Revise o caminho antes de limpar.'
                }
                if ($item.PSIsContainer) { $pending.Push($item.FullName) }
            }
        }
    }
}

function Reset-UrnaData([string]$LocalBase, [string]$ProgramBase, [string]$Role) {
    if ($Role -notin @('central','urna')) { throw 'Papel invalido.' }
    if (-not [IO.Path]::IsPathRooted($LocalBase) -or -not [IO.Path]::IsPathRooted($ProgramBase)) {
        throw 'As pastas de dados devem ter caminhos absolutos.'
    }
    $localBasePath = [IO.Path]::GetFullPath($LocalBase).TrimEnd('\')
    $programBasePath = [IO.Path]::GetFullPath($ProgramBase).TrimEnd('\')
    $local = [IO.Path]::GetFullPath((Join-Path $localBasePath 'UrnaEscolar'))
    $machine = [IO.Path]::GetFullPath((Join-Path $programBasePath 'UrnaEscolar'))
    if ((Split-Path -Parent $local) -ne $localBasePath -or (Split-Path -Parent $machine) -ne $programBasePath) {
        throw 'Destino fora da pasta autorizada.'
    }
    $targets = @($local, (Join-Path $machine 'logs'), (Join-Path $machine 'device_setup.json'))
    if ($Role -eq 'central') {
        $targets += (Join-Path $machine 'Servidor')
        $targets += (Join-Path $machine 'Backups')
    }
    # Validate everything before touching certificates or deleting any item.
    Assert-PlainTree $machine
    foreach ($path in $targets) { Assert-PlainTree $path }
    $roleFile = Join-Path $machine 'role.json'
    $installedRole = (Get-Content -LiteralPath $roleFile -Raw | ConvertFrom-Json).role
    if ($installedRole -ne $Role) {
        throw 'Este BAT nao corresponde ao papel instalado. Use o BAT do outro computador.'
    }
    $certPath = Join-Path $local 'central.crt'
    if (Test-Path -LiteralPath $certPath) {
        $cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2($certPath)
        $store = New-Object Security.Cryptography.X509Certificates.X509Store('Root','CurrentUser')
        $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        try {
            $matches = $store.Certificates.Find([Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,$cert.Thumbprint,$false)
            foreach ($item in $matches) { $store.Remove($item) }
        } finally { $store.Close(); $cert.Dispose() }
    }
    foreach ($path in $targets) {
        if (Test-Path -LiteralPath $path) {
            Assert-PlainTree $path
            Remove-Item -LiteralPath $path -Recurse -Force
            Write-Host ('Removido: ' + $path)
        }
    }
}

# INTERACTIVE_RESET
try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Clique com o botao direito no BAT > Executar como administrador, usando a mesma conta Windows da Urna.'
    }
    # Elevation using another account would select the wrong profile/cert store.
    $sessionId = (Get-Process -Id $PID).SessionId
    $explorers = @(Get-CimInstance Win32_Process -Filter "Name='explorer.exe'" | Where-Object { $_.SessionId -eq $sessionId })
    if (-not $explorers.Count) { throw 'Abra este BAT na sessao Windows usada para executar a Urna.' }
    foreach ($explorer in $explorers) {
        $owner = Invoke-CimMethod -InputObject $explorer -MethodName GetOwnerSid
        if ($owner.ReturnValue -ne 0 -or $owner.Sid -ne $identity.User.Value) {
            throw 'A conta elevada e diferente da conta Windows em uso. Cancelado para preservar o perfil correto.'
        }
    }
    $running = @(Get-Process -Name UrnaEscolar,UrnaEscolarServidor,msedge -ErrorAction SilentlyContinue)
    if ($running.Count) { throw 'Feche a Central, a Urna e todas as janelas/processos do Microsoft Edge e tente novamente.' }
    $role = 'urna'
    Write-Host ''
    Write-Host 'RESET COMPLETO - PC DA URNA' -ForegroundColor Yellow
    Write-Host 'Esta operacao apaga dados permanentemente. Copie qualquer backup que deseja guardar para outra pasta.'
    Write-Host 'Os votos e usuarios guardados na Central serao preservados.'
    Write-Host 'Serao apagados: vinculos, certificado desta Central no usuario atual, impressora, margem, sessoes, diario de impressao e logs.'
    Write-Host 'O programa instalado e o papel do computador serao preservados.'
    Write-Host ('Conta Windows: ' + $identity.Name)
    $answer = Read-Host 'Para continuar, digite RESETAR URNA'
    if ($answer -cne 'RESETAR URNA') { Write-Host 'Cancelado. Nenhum dado foi apagado.'; exit 0 }
    Reset-UrnaData ([Environment]::GetFolderPath('LocalApplicationData')) ([Environment]::GetFolderPath('CommonApplicationData')) $role
    Write-Host 'RESET CONCLUIDO. Abra a Urna, vincule a Central e configure/teste novamente a impressora.' -ForegroundColor Green
    exit 0
} catch {
    Write-Host ('FALHA: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Se a remocao ja havia comecado, ela pode estar parcial. Corrija a causa e execute novamente.'
    exit 1
}
