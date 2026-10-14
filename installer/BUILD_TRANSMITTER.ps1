$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot '.build-venv\Scripts\python.exe'
if (!(Test-Path -LiteralPath $PythonExe)) { throw 'Execute BUILD_WINDOWS.ps1 primeiro para preparar o ambiente de compilacao.' }
$env:URNA_BUILD_ROOT = $ProjectRoot
Set-Location -LiteralPath $ProjectRoot
& $PythonExe -m PyInstaller --clean --noconfirm (Join-Path $PSScriptRoot 'transmitter.spec')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o Transmissor Eleitoral.' }
$TransmitterExe = Join-Path $ProjectRoot 'dist\TransmissorEleitoral.exe'
$Check = Start-Process -FilePath $TransmitterExe -ArgumentList '--self-test' -PassThru -WindowStyle Hidden
if (!$Check.WaitForExit(60000)) { Stop-Process -Id $Check.Id -Force; throw 'O teste do transmissor excedeu o tempo limite.' }
if ($Check.ExitCode -ne 0) { throw 'Falha no teste do executavel do transmissor.' }
Get-FileHash -LiteralPath $TransmitterExe -Algorithm SHA256
Write-Host 'TransmissorEleitoral.exe pronto. Nao precisa de Python no computador de destino.'
