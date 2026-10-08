param([switch]$TestarInstalacao)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$Root = (Split-Path -Parent $PSScriptRoot)
Set-Location $Root
$Log = Join-Path $PSScriptRoot 'build-log.txt'

try { Stop-Transcript | Out-Null } catch {}
Start-Transcript -Path $Log -Force | Out-Null

function Fail([string]$Message) {
    Write-Host ''
    Write-Host ('[ERRO] ' + $Message) -ForegroundColor Red
    throw $Message
}

function Run-Native([string]$Exe, [string[]]$CommandArgs) {
    Write-Host ('> ' + $Exe + ' ' + ($CommandArgs -join ' ')) -ForegroundColor DarkGray
    & $Exe @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        Fail ("Comando falhou com codigo ${LASTEXITCODE}: $Exe")
    }
}

function Remove-BuildDirectory([string]$RelativePath) {
    $ResolvedRoot = [IO.Path]::GetFullPath($Root).TrimEnd('\') + '\'
    $Target = [IO.Path]::GetFullPath((Join-Path $Root $RelativePath))
    if (-not $Target.StartsWith($ResolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
        Fail ('Pasta fora do projeto: ' + $Target)
    }
    if (Test-Path -LiteralPath $Target) { Remove-Item -LiteralPath $Target -Recurse -Force }
}

function Wait-Server([string]$Exe) {
    # Never accept the health response of a different, already running server.
    if (Get-NetTCPConnection -LocalPort 8443 -State Listen -ErrorAction SilentlyContinue) {
        Fail 'A porta 8443 esta ocupada. Feche a Central antes de compilar.'
    }
    $proc = Start-Process -FilePath $Exe -PassThru -WindowStyle Hidden
    try {
        for ($i=0; $i -lt 40; $i++) {
            Start-Sleep -Milliseconds 500
            try {
                $json = & curl.exe --max-time 2 -k -f -s 'https://127.0.0.1:8443/health'
                if ($LASTEXITCODE -eq 0 -and $json) {
                    $h = $json | ConvertFrom-Json
                    if ($h.ok -and -not $proc.HasExited) { return $true }
                }
            } catch {}
            if ($proc.HasExited) { break }
        }
        return $false
    }
    finally {
        if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue }
    }
}

try {
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host ' URNA ESCOLAR 2.3.0 - BUILD WINDOWS + SMOKE TESTS' -ForegroundColor Cyan
    Write-Host '============================================================' -ForegroundColor Cyan
    Write-Host ('Raiz: ' + $Root)

    $BootstrapExe = $null
    $BootstrapArgs = @()

    if ($env:GITHUB_ACTIONS -eq 'true') {
        $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($PythonCmd) {
            $VersionText = & $PythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
            if ($LASTEXITCODE -eq 0 -and $VersionText.Trim() -eq '3.13') {
                $BootstrapExe = $PythonCmd.Source
                $BootstrapArgs = @()
            }
        }
    } else {
        $PyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($PyLauncher) {
            & $PyLauncher.Source -3.13 --version *> $null
            if ($LASTEXITCODE -eq 0) {
                $BootstrapExe = $PyLauncher.Source
                $BootstrapArgs = @('-3.13')
            }
        }
        if (-not $BootstrapExe) {
            $PythonCmd = Get-Command python.exe -ErrorAction SilentlyContinue
            if ($PythonCmd) {
                $VersionText = & $PythonCmd.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
                if ($LASTEXITCODE -eq 0 -and $VersionText.Trim() -eq '3.13') {
                    $BootstrapExe = $PythonCmd.Source
                    $BootstrapArgs = @()
                }
            }
        }
    }

    if (-not $BootstrapExe) { Fail 'Python 3.13 nao foi encontrado para compilacao.' }
    Write-Host ('Python de compilacao: ' + $BootstrapExe + ' ' + ($BootstrapArgs -join ' ')) -ForegroundColor Green

    $Venv = Join-Path $Root '.build-venv'
    $Py = Join-Path $Venv 'Scripts\python.exe'

    if (-not (Test-Path $Py)) {
        Write-Host '[1/9] Criando ambiente de compilacao...' -ForegroundColor Yellow
        $VenvArgs = @() + $BootstrapArgs + @('-m','venv',$Venv)
        Run-Native -Exe $BootstrapExe -CommandArgs $VenvArgs
    } else {
        Write-Host '[1/9] Ambiente de compilacao ja existe.' -ForegroundColor Green
    }
    if (-not (Test-Path $Py)) { Fail ('Ambiente virtual nao foi criado: ' + $Py) }

    Write-Host '[2/9] Instalando dependencias e validando sintaxe...' -ForegroundColor Yellow
    Run-Native -Exe $Py -CommandArgs @('-m','pip','install','--upgrade','pip','setuptools','wheel')
    Run-Native -Exe $Py -CommandArgs @('-m','pip','install','-r',(Join-Path $Root 'URNA_ESCOLAR_SOURCE\01_SERVIDOR_ADMIN\requirements.txt'))
    Run-Native -Exe $Py -CommandArgs @('-m','pip','install','-r',(Join-Path $Root 'URNA_ESCOLAR_SOURCE\03_URNA\print_agent\requirements.txt'))
    Run-Native -Exe $Py -CommandArgs @('-m','pip','install','-r',(Join-Path $PSScriptRoot 'requirements-build.txt'))
    Run-Native -Exe $Py -CommandArgs @('-m','compileall','-q',(Join-Path $Root 'URNA_ESCOLAR_SOURCE'),(Join-Path $Root 'installer'))

    Run-Native -Exe $Py -CommandArgs @('-m','pytest','-q',(Join-Path $Root 'tests'),'--junitxml=test-results/windows-tests.xml')

    Write-Host '[3/9] Limpando builds anteriores...' -ForegroundColor Yellow
    Remove-BuildDirectory 'build'
    Remove-BuildDirectory 'dist'
    Remove-BuildDirectory 'installer\output'
    $env:URNA_BUILD_ROOT = $Root
    # Smoke tests use disposable data, never the school's actual database.
    $env:URNA_BUILD_DATA_DIR = Join-Path $Root 'test-results\runtime\UrnaEscolar'

    Write-Host '[4/9] Gerando e testando UrnaEscolarServidor.exe...' -ForegroundColor Yellow
    Run-Native -Exe $Py -CommandArgs @('-m','PyInstaller','--clean','--noconfirm',(Join-Path $PSScriptRoot 'server.spec'))
    $ServerExe = Join-Path $Root 'dist\UrnaEscolarServidor\UrnaEscolarServidor.exe'
    if (-not (Test-Path $ServerExe)) { Fail ('PyInstaller nao criou: ' + $ServerExe) }
    if (-not (Wait-Server $ServerExe)) {
        $ServerLog = Join-Path $env:URNA_BUILD_DATA_DIR 'logs\server.log'
        if (Test-Path $ServerLog) { Get-Content $ServerLog -Tail 80 | Write-Host }
        Fail 'Smoke test do servidor falhou: /health nao respondeu em HTTPS.'
    }
    Write-Host '[OK] Servidor iniciou e respondeu /health.' -ForegroundColor Green

    Write-Host '[5/9] Gerando aplicativo Central / Urna...' -ForegroundColor Yellow
    Run-Native -Exe $Py -CommandArgs @('-m','PyInstaller','--clean','--noconfirm',(Join-Path $PSScriptRoot 'desktop.spec'))
    $DesktopExe = Join-Path $Root 'dist\UrnaEscolar\UrnaEscolar.exe'
    if (-not (Test-Path $DesktopExe)) { Fail 'Aplicativo não foi criado.' }
    Write-Host '[6/9] Testando aplicativo sem invocar Python externo...' -ForegroundColor Yellow
    $SelfTest = Start-Process -FilePath $DesktopExe -ArgumentList '--self-test' -PassThru -Wait -WindowStyle Hidden
    if ($SelfTest.ExitCode -ne 0) {
        $SelfTestLog = Join-Path $env:LOCALAPPDATA 'UrnaEscolar\self-test-error.txt'
        if (Test-Path $SelfTestLog) {
            Write-Host '--- erro detalhado do self-test ---' -ForegroundColor Yellow
            Get-Content $SelfTestLog -Tail 120 | Write-Host
            Write-Host '--- fim do erro detalhado ---' -ForegroundColor Yellow
        } else {
            Write-Host ('Arquivo de erro não encontrado: ' + $SelfTestLog) -ForegroundColor Yellow
        }
        Fail ('Self-test do aplicativo falhou (codigo ' + $SelfTest.ExitCode + ').')
    }
    Write-Host '[7/9] Preparando proteção de atualização...' -ForegroundColor Yellow
    Run-Native -Exe $Py -CommandArgs @('-m','PyInstaller','--clean','--noconfirm',(Join-Path $PSScriptRoot 'upgrade_guard.spec'))
    Write-Host '[8/9] Executáveis prontos.' -ForegroundColor Green

    Write-Host '[9/9] Gerando instalador com Inno Setup...' -ForegroundColor Yellow
    $Candidates = @('C:\Program Files (x86)\Inno Setup 6\ISCC.exe','C:\Program Files\Inno Setup 6\ISCC.exe')
    $Iscc = $null
    $Cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($Cmd) { $Iscc = $Cmd.Source }
    if (-not $Iscc) {
        foreach ($candidate in $Candidates) { if (Test-Path $candidate) { $Iscc = $candidate; break } }
    }
    if (-not $Iscc) { Fail 'Inno Setup 6 / ISCC.exe nao foi encontrado.' }
    Run-Native -Exe $Iscc -CommandArgs @((Join-Path $PSScriptRoot 'UrnaEscolar.iss'))

    $InstallerExe = Join-Path $PSScriptRoot 'output\Instalar_Urna_Escolar_2.3.0.exe'
    if (-not (Test-Path $InstallerExe)) { Fail ('Inno Setup nao criou: ' + $InstallerExe) }

    # The runtime check cannot resolve python.exe, py.exe or a build venv.
    # This does not substitute for validation on the school's clean PCs.
    if ($TestarInstalacao) {
    if ($env:GITHUB_ACTIONS -ne 'true') { Fail 'O teste de instalacao automatica e permitido apenas no runner descartavel do GitHub Actions.' }
    $SavedPath = $env:PATH
    $SavedPythonHome = $env:PYTHONHOME
    $SavedPythonPath = $env:PYTHONPATH
    try {
        $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
        Remove-Item Env:PYTHONHOME -ErrorAction SilentlyContinue
        Remove-Item Env:PYTHONPATH -ErrorAction SilentlyContinue
        if (Get-Command python.exe -ErrorAction SilentlyContinue) { Fail 'Python externo continua no PATH do teste.' }
        $Installed = Join-Path $env:ProgramFiles 'Urna Escolar Teste 230'
        foreach ($Role in @('central','urna')) {
            $InstallArgs = @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART',"/ROLE=$Role",('/DIR="' + $Installed + '"'),('/LOG="' + (Join-Path $Root "test-results\install-$Role.log") + '"'))
            $Install = Start-Process -FilePath $InstallerExe -ArgumentList $InstallArgs -PassThru -Wait -WindowStyle Hidden
            if ($Install.ExitCode -ne 0) { Fail "Instalacao do papel $Role falhou: $($Install.ExitCode)" }
            $ActualRole = Get-Content (Join-Path $env:ProgramData 'UrnaEscolar\role.json') -Raw | ConvertFrom-Json
            if ($ActualRole.role -ne $Role) { Fail 'Papel instalado incorreto.' }
            $Check = Start-Process -FilePath (Join-Path $Installed 'Aplicativo\UrnaEscolar.exe') -ArgumentList '--self-test' -PassThru -Wait -WindowStyle Hidden
            if ($Check.ExitCode -ne 0) { Fail 'Aplicativo instalado nao passou no self-test.' }
            if ($Role -eq 'central' -and -not (Wait-Server (Join-Path $Installed 'Servidor\UrnaEscolarServidor.exe'))) { Fail 'Servidor instalado nao iniciou.' }
        }
        'Instalador executado nos dois papeis. Runtime testado sem Python externo no PATH. Impressora fisica e dois PCs: pendentes.' | Set-Content (Join-Path $Root 'test-results\windows-smoke.txt') -Encoding UTF8
    } finally {
        $env:PATH = $SavedPath
        $env:PYTHONHOME = $SavedPythonHome
        $env:PYTHONPATH = $SavedPythonPath
    }
    }
    Get-FileHash -LiteralPath $InstallerExe -Algorithm SHA256 | Format-List

    Write-Host ''
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ' BUILD 2.3.0 CONCLUIDO - CONFIRA OS TESTES NO LOG' -ForegroundColor Green
    Write-Host '============================================================' -ForegroundColor Green
    Write-Host ('Instalador: ' + $InstallerExe) -ForegroundColor Green
    Write-Host ('Log: ' + $Log)
    Stop-Transcript | Out-Null
    exit 0
}
catch {
    Write-Host ''
    Write-Host ('FALHA: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Veja o log: ' + $Log) -ForegroundColor Yellow
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
