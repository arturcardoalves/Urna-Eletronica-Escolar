@echo off
setlocal EnableExtensions
chcp 65001 >nul
title Urna Escolar - Reset do PC da Urna

net session >nul 2>&1
if not "%errorlevel%"=="0" (
    echo Solicitando permissao de administrador...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo ============================================================
echo   RESET COMPLETO - PC DA URNA
echo ============================================================
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { $role=(Get-Content -LiteralPath (Join-Path $env:ProgramData 'UrnaEscolar\role.json') -Raw | ConvertFrom-Json).role; if ($role -ne 'urna') { exit 3 } } catch { exit 4 }"
if "%errorlevel%"=="3" (
    echo ERRO: Este computador esta instalado como CENTRAL.
    echo Use o arquivo RESETAR_PC_CENTRAL_MESA.bat neste computador.
    echo.
    pause
    exit /b 1
)
if not "%errorlevel%"=="0" (
    echo ERRO: Nao foi possivel confirmar que este e o PC da Urna.
    echo Reinstale o sistema escolhendo URNA e tente novamente.
    echo.
    pause
    exit /b 1
)

for %%P in (UrnaEscolar.exe UrnaEscolarServidor.exe msedge.exe) do (
    tasklist /FI "IMAGENAME eq %%P" 2>nul | find /I "%%P" >nul
    if not errorlevel 1 (
        echo ERRO: O programa %%P ainda esta aberto.
        echo Feche a Urna e todas as janelas do Microsoft Edge.
        echo Depois execute este arquivo novamente.
        echo.
        pause
        exit /b 1
    )
)

echo ATENCAO: esta operacao e irreversivel.
echo.
echo Serao apagados deste computador:
echo   - vinculo e credencial de acesso a Central;
echo   - certificado instalado pela Central;
echo   - configuracao da impressora e margem antes do corte;
echo   - sessoes locais, navegador da urna e diario de impressao;
echo   - logs antigos.
echo.
echo O programa instalado e o papel URNA serao preservados.
echo Os votos e usuarios armazenados na Central nao sao apagados por este arquivo.
echo.
set "CONFIRMACAO="
set /p "CONFIRMACAO=Para limpar esta Urna, digite exatamente RESETAR URNA: "
if /I not "%CONFIRMACAO%"=="RESETAR URNA" (
    echo.
    echo Operacao cancelada. Nenhum dado foi apagado.
    pause
    exit /b 0
)

echo.
echo Limpando os dados locais da Urna...

powershell.exe -NoProfile -ExecutionPolicy Bypass -Command ^
 "$ErrorActionPreference='Stop';" ^
 "$localBase=[IO.Path]::GetFullPath($env:LOCALAPPDATA);" ^
 "$local=[IO.Path]::GetFullPath((Join-Path $localBase 'UrnaEscolar'));" ^
 "$programBase=[IO.Path]::GetFullPath($env:ProgramData);" ^
 "$machine=[IO.Path]::GetFullPath((Join-Path $programBase 'UrnaEscolar'));" ^
 "$logs=[IO.Path]::GetFullPath((Join-Path $machine 'logs'));" ^
 "$legacy=[IO.Path]::GetFullPath((Join-Path $machine 'device_setup.json'));" ^
 "if ((Split-Path -Parent $local) -ne $localBase) { throw 'Caminho local invalido.' };" ^
 "if ((Split-Path -Parent $machine) -ne $programBase) { throw 'Caminho principal invalido.' };" ^
 "$roleFile=Join-Path $machine 'role.json';" ^
 "if (-not (Test-Path -LiteralPath $roleFile)) { throw 'role.json nao encontrado.' };" ^
 "$role=(Get-Content -LiteralPath $roleFile -Raw | ConvertFrom-Json).role;" ^
 "if ($role -ne 'urna') { throw 'Este computador nao esta configurado como Urna.' };" ^
 "$certPath=Join-Path $local 'central.crt';" ^
 "if (Test-Path -LiteralPath $certPath) {" ^
 "  $cert=[Security.Cryptography.X509Certificates.X509Certificate2]::new($certPath);" ^
 "  $store=[Security.Cryptography.X509Certificates.X509Store]::new('Root','CurrentUser');" ^
 "  $store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite);" ^
 "  try {" ^
 "    $matches=$store.Certificates.Find([Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint,$cert.Thumbprint,$false);" ^
 "    foreach ($item in $matches) { $store.Remove($item) }" ^
 "  } finally { $store.Close() }" ^
 "};" ^
 "if (Test-Path -LiteralPath $logs) { Remove-Item -LiteralPath $logs -Recurse -Force };" ^
 "if (Test-Path -LiteralPath $legacy) { Remove-Item -LiteralPath $legacy -Force };" ^
 "if (Test-Path -LiteralPath $local) { Remove-Item -LiteralPath $local -Recurse -Force };"

if errorlevel 1 (
    echo.
    echo FALHA: o reset nao foi concluido.
    echo Confira a mensagem acima, feche os programas e tente novamente.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   RESET CONCLUIDO COM SUCESSO
echo ============================================================
echo Abra a Urna e faca o vinculo com a Central novamente.
echo Depois selecione a impressora e execute as impressoes de teste.
echo.
pause
exit /b 0
