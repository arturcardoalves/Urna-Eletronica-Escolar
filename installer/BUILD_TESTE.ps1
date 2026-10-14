$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot '.build-venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Execute BUILD_WINDOWS.ps1 primeiro para preparar as dependencias de compilacao.' }
Set-Location -LiteralPath $ProjectRoot
& $PythonExe -m PyInstaller --clean --noconfirm --distpath release-output/demo --workpath build/demo (Join-Path $ProjectRoot 'demo\urna_demo.spec')
if ($LASTEXITCODE -ne 0) { throw 'Falha ao compilar o teste ficticio.' }
$DemoExe = Join-Path $ProjectRoot 'release-output\demo\UrnaEscolar_Teste.exe'
$Check = Start-Process -FilePath $DemoExe -ArgumentList '--self-test' -PassThru -WindowStyle Hidden
if (-not $Check.WaitForExit(90000)) { Stop-Process -Id $Check.Id -Force; throw 'Autoteste do EXE excedeu o tempo limite.' }
if ($Check.ExitCode -ne 0) { throw 'Autoteste do EXE ficticio falhou.' }
Get-FileHash -LiteralPath $DemoExe -Algorithm SHA256
Write-Host 'Teste ficticio pronto; nao modifica a eleicao real.'
