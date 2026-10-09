# Como limpar uma votação de teste ou resetar todo o sistema

Há dois tipos de limpeza. Escolha de acordo com o que deseja preservar.

## Opção 1 — criar outra eleição e manter acessos

Use esta opção quando o teste terminou corretamente e você quer preparar a eleição real sem configurar novamente os computadores.

Ela remove da eleição ativa:

- votos e autorizações;
- eleitores;
- chapas e integrantes;
- ocorrências e comandos de impressão da eleição;
- apuração e configuração eleitoral.

Ela preserva:

- usuários ADMIN e MESÁRIO;
- senhas desses usuários;
- computadores vinculados;
- cadastro das estações de votação;
- escolha da impressora e margem antes do corte;
- uma cópia arquivada da eleição encerrada.

Procedimento:

1. Encerre a eleição pela Mesa Eleitoral e confirme a impressão do boletim.
2. Entre no **Administrador**.
3. Abra **Histórico**.
4. Na área **Iniciar nova eleição**, digite `NOVA ELEICAO`.
5. Clique **Arquivar e criar nova eleição**.

O botão só aparece depois que a eleição foi encerrada. A eleição anterior continua guardada em um arquivo de histórico.

## Opção 2 — reset completo, incluindo senhas

Use esta opção para voltar ao estado de primeira instalação. Ela apaga:

- eleição ativa e eleições arquivadas;
- votos, eleitores, chapas e relatórios internos;
- usuários e senhas ADMIN/MESÁRIO;
- chaves de criptografia e certificados da Central;
- vínculo entre Central e Urna;
- seleção e confirmação da impressora;
- margem de corte, sessões do navegador e diário local de impressão;
- logs antigos.

O papel escolhido na instalação — Central ou Urna — é preservado. Não é necessário reinstalar o programa.

### Arquivos prontos para executar

Na raiz do projeto existem dois arquivos que fazem a limpeza completa automaticamente:

- `RESETAR_PC_CENTRAL_MESA.bat`: execute somente no computador Central + Mesa;
- `RESETAR_PC_URNA.bat`: execute somente no computador da Urna.

Copie o arquivo correto para cada computador, feche a Central, a Urna e todas as janelas do Microsoft Edge e clique no arquivo com o botão direito, escolhendo **Executar como administrador**. O arquivo confere o papel instalado no computador e pede que você digite uma frase de confirmação antes de apagar qualquer dado.

Os comandos PowerShell das seções seguintes são uma alternativa manual aos arquivos BAT. Não é necessário usar os dois métodos.

> [!CAUTION]
> O reset completo é irreversível. Se houver qualquer informação que deva ser guardada, copie antes a pasta `C:\ProgramData\UrnaEscolar\Servidor` para um local protegido. Essa cópia contém dados sensíveis, chaves e hashes de senha e não deve ser enviada ao GitHub ou compartilhada.

### 1. Feche os programas

Nos dois computadores:

1. Feche as janelas do Microsoft Edge abertas pela eleição.
2. Feche **Central da Eleição** e **Urna de Votação**.
3. Abra o Gerenciador de Tarefas e confirme que `UrnaEscolar.exe` e `UrnaEscolarServidor.exe` não estão em execução.

### 2. Limpe a Central

No computador **Central + Mesa**, abra o PowerShell **como administrador** e execute todo o bloco:

```powershell
$processos = Get-Process -Name 'UrnaEscolar','UrnaEscolarServidor' -ErrorAction SilentlyContinue
if ($processos) {
    throw 'Feche a Central e o Servidor antes de continuar.'
}

$pastaLocal = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'UrnaEscolar'))
$pastaRaiz = [IO.Path]::GetFullPath((Join-Path $env:ProgramData 'UrnaEscolar'))
$pastaServidor = [IO.Path]::GetFullPath((Join-Path $pastaRaiz 'Servidor'))
$pastaLogs = [IO.Path]::GetFullPath((Join-Path $pastaRaiz 'logs'))
$configuracaoAntiga = [IO.Path]::GetFullPath((Join-Path $pastaRaiz 'device_setup.json'))

if ((Split-Path -Parent $pastaServidor) -ne $pastaRaiz) {
    throw 'Caminho de dados da Central inválido.'
}

$certificado = Join-Path $pastaLocal 'central.crt'
if (Test-Path -LiteralPath $certificado) {
    $cert = [Security.Cryptography.X509Certificates.X509Certificate2]::new($certificado)
    $store = [Security.Cryptography.X509Certificates.X509Store]::new('Root','CurrentUser')
    $store.Open('ReadWrite')
    try {
        @($store.Certificates | Where-Object Thumbprint -eq $cert.Thumbprint) |
            ForEach-Object { $store.Remove($_) }
    } finally {
        $store.Close()
    }
}

if (Test-Path -LiteralPath $pastaServidor) {
    Remove-Item -LiteralPath $pastaServidor -Recurse -Force
}
if (Test-Path -LiteralPath $pastaLogs) {
    Remove-Item -LiteralPath $pastaLogs -Recurse -Force
}
if (Test-Path -LiteralPath $configuracaoAntiga) {
    Remove-Item -LiteralPath $configuracaoAntiga -Force
}
if (Test-Path -LiteralPath $pastaLocal) {
    Remove-Item -LiteralPath $pastaLocal -Recurse -Force
}

Write-Host 'Central resetada. O papel Central foi preservado.' -ForegroundColor Green
```

O comando não apaga `C:\ProgramData\UrnaEscolar\role.json`, pois esse arquivo informa que o computador continua sendo a Central.

### 3. Limpe a Urna

No computador **Urna + impressora USB**, entre na mesma conta do Windows usada durante a eleição, abra o PowerShell **como administrador** e execute:

```powershell
$processos = Get-Process -Name 'UrnaEscolar','UrnaEscolarServidor' -ErrorAction SilentlyContinue
if ($processos) {
    throw 'Feche a Urna antes de continuar.'
}

$pastaLocal = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'UrnaEscolar'))
$pastaRaiz = [IO.Path]::GetFullPath((Join-Path $env:ProgramData 'UrnaEscolar'))
$pastaLogs = [IO.Path]::GetFullPath((Join-Path $pastaRaiz 'logs'))
$configuracaoAntiga = [IO.Path]::GetFullPath((Join-Path $pastaRaiz 'device_setup.json'))

$certificado = Join-Path $pastaLocal 'central.crt'
if (Test-Path -LiteralPath $certificado) {
    $cert = [Security.Cryptography.X509Certificates.X509Certificate2]::new($certificado)
    $store = [Security.Cryptography.X509Certificates.X509Store]::new('Root','CurrentUser')
    $store.Open('ReadWrite')
    try {
        @($store.Certificates | Where-Object Thumbprint -eq $cert.Thumbprint) |
            ForEach-Object { $store.Remove($_) }
    } finally {
        $store.Close()
    }
}

if (Test-Path -LiteralPath $pastaLogs) {
    Remove-Item -LiteralPath $pastaLogs -Recurse -Force
}
if (Test-Path -LiteralPath $configuracaoAntiga) {
    Remove-Item -LiteralPath $configuracaoAntiga -Force
}
if (Test-Path -LiteralPath $pastaLocal) {
    Remove-Item -LiteralPath $pastaLocal -Recurse -Force
}

Write-Host 'Urna resetada. O papel Urna foi preservado.' -ForegroundColor Green
```

### 4. Configure novamente

1. Abra a **Central da Eleição**. O servidor criará banco, certificados e chaves novos.
2. Clique **Abrir administração** e crie um novo usuário ADMIN e uma nova senha.
3. Cadastre um usuário MESÁRIO.
4. Na Central, permita a conexão de uma Urna por cinco minutos.
5. Abra a **Urna de Votação**, clique **Procurar Central** e compare os códigos novamente.
6. Selecione a impressora, configure a margem antes do corte e execute as duas impressões de teste.
7. Faça uma eleição curta de teste antes de preparar a eleição real.

## O que a desinstalação faz

Desinstalar o programa remove os executáveis e as regras de firewall, mas os dados eleitorais e configurações locais são preservados para evitar perda acidental. Para apagar tudo, faça o reset completo antes ou depois de desinstalar.
