# Revisão e limpeza — 09/10/2026

Base: pacote local Urna_Escolar_2.3.0. A revisão foi feita numa cópia; a pasta original permanece preservada. A numeração foi mantida porque esta é uma correção de empacotamento e organização da mesma versão.

## Rodada de segurança e entrega

- O instalador deixou de empacotar `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/data`; o primeiro uso cria o banco, certificados e chaves no computador instalado.
- O backup de atualização preserva bancos SQLite auxiliares e arquivados, inclusive dados ainda confirmados no WAL, e recusa links/junções para impedir cópia fora da pasta eleitoral.
- Depois da cópia SQLite, o backup é normalizado para journal `DELETE`; os dados confirmados do WAL permanecem, sem deixar arquivos `-wal`/`-shm` no pacote de recuperação.
- Os BATs de reset confirmam o papel instalado, exigem a mesma conta Windows, recusam processos abertos e recusam árvores com links/junções antes de apagar qualquer destino.
- Uploads de chapa agora validam formato, tamanho, dimensões e normalizam a imagem para PNG; planilhas têm limites de expansão, linhas e colunas; entradas de chapa, urna, usuário e eleição são limitadas no servidor.
- A instalação inicial fica restrita ao próprio computador da Central. A origem `null` e origens com esquema ou host diferente são recusadas nas operações de alteração.
- No primeiro cadastro, `localhost` e `127.0.0.1` são tratados como aliases do mesmo loopback; origens da rede continuam bloqueadas.
- O agente HTTP legado de impressão, mantido para compatibilidade de operação sem impressão nativa, aceita apenas clientes de loopback. O aplicativo empacotado continua usando o módulo nativo.
- O raster ESC/POS é enviado em tiras de no máximo 512 linhas, e layouts longos reservam altura conforme a quantidade de chapas e recusam corte silencioso.
- As dependências de servidor foram atualizadas para `cryptography 50.0.2`, `python-multipart 0.0.32`, `starlette 1.7.0` e `fastapi 0.143.0`, cobrindo os avisos oficiais consultados. O cliente de testes passou a usar `httpx2`.
- O gerador `installer/package_source.py` cria o ZIP de fonte por allowlist, exclui dados e confirma o conteúdo pelo manifesto SHA-256.

## Correções

- PrintJournal agora confirma ou desfaz a transação e fecha a conexão SQLite em todos os caminhos. Isso corrige o arquivo test.db preso no Windows durante o self-test do aplicativo.
- A proteção de atualização fecha as conexões de leitura e de backup do banco.
- Um teste de regressão verifica commit, rollback, conexões encerradas e remoção do arquivo do diário.
- O teste do servidor usa um diretório de dados separado em test-results/runtime. A compilação não testa usando o banco real da escola.
- A compilação recusa a porta 8443 ocupada, limita o tempo do curl e verifica que seu processo ainda está ativo.
- A instalação silenciosa dos dois papéis é executada apenas no Windows descartável do GitHub com -TestarInstalacao. A compilação local não altera uma instalação existente.
- A limpeza no PowerShell valida que cada destino está dentro da raiz do projeto antes de removê-lo.
- Removida a função Wait-Agent sem chamadas. Os processos auxiliares da compilação são iniciados com janela oculta.
- Dependências de compilação foram fixadas nas versões encontradas no ambiente da versão original. O servidor interrompe a compilação se a coleta de uma dependência obrigatória falhar.
- As instruções e o manifesto de integridade deixaram de mencionar os lançadores removidos. A documentação de segurança foi atualizada para a aplicação unificada.

## Arquivos retirados da entrega

- .build-venv, build, dist, .pytest_cache, __pycache__, arquivos .pyc, test-results e logs antigos.
- GERAR_INSTALADOR_WINDOWS.bat, GERAR_INSTALADOR_LOCAL_CORRIGIDO.bat e DIAGNOSTICO_BUILD.bat. O único ponto de compilação é installer/BUILD_WINDOWS.ps1.
- installer/setup_assistant.py e assistant.spec: assistente antigo que não é utilizado pela aplicação unificada.
- installer/print_agent_launcher.py e print_agent.spec: executável separado antigo; a impressão atual é carregada pela Central/Urna.
- Lançadores HTA da Central, Mesa, Urna e Central de Impressão; scripts BAT de tools/windows.
- Cópia antiga do print_agent dentro de 01_SERVIDOR_ADMIN. A biblioteca utilizada continua em 03_URNA/print_agent.
- A segunda cópia idêntica do instalador de fonte. A única cópia mantida fica em 01_SERVIDOR_ADMIN/scripts/install_atkinson_windows.ps1.
- Checklists, notas de versão, instruções de atualização e guias de instalação antigos da 2.2.1; documentos LEIA-ME de operação antiga.
- SHA256SUMS.txt e MANIFEST_SHA256_GERADO.txt antigos, que não correspondem ao código revisado. O ZIP entregue recebe um novo SHA-256 externo.
- Relatórios de testes da entrega anterior e SECURITY.md duplicado. O resultado desta revisão está registrado aqui; a segurança está em SEGURANCA.md.

Os testes, recursos da interface, scripts de verificação de integridade, geração TLS, biblioteca de impressão, sons e arquivos .gitkeep foram mantidos. O PowerShell, três arquivos .spec e UrnaEscolar.iss são necessários para compilar e montar o instalador.

## Validação realizada

Na rodada anterior, a suíte desta cópia teve **38 testes aprovados** com Python 3.13. Com os testes de entrega adicionados, são **50 testes coletados**. O conjunto inclui eleição com 20 votos, apuração, PDF, voto repetido/concorrente sem duplicação, impressão com falha, reimpressão autorizada, desconexão, vinculação, modos do Edge, margem antes do corte, dados arquivados, imagens longas, reset e interface.

Nesta rodada, os testes do pacote limpo passaram (**2 testes**), os testes de entrega Windows executáveis localmente passaram (**8 testes**, com o teste de TestClient legado separado), os testes de interface Node passaram (**9/9**) e o código foi compilado com `compileall`. A suíte completa precisa ser repetida no runner do GitHub depois da instalação de `httpx2`; o ambiente local atual não conseguiu baixar esse pacote e o TestClient do Starlette 1.7 fica incompatível com o `httpx` legado.

O parser do PowerShell não encontrou erros de sintaxe no script de compilação. Os testes produziram 537 avisos de depreciação de bibliotecas/APIs existentes; não foram falhas. Esta revisão não migrou toda a aplicação para novos padrões de datas e lifecycle.

Não foi gerado nem instalado um novo EXE nesta rodada local. A compilação, o teste do runtime sem Python externo e a instalação descartável dos dois papéis devem ser executados pelo workflow no GitHub. Testes reais nos dois PCs, no roteador, no driver, no papel e na impressora ainda são necessários.

Não foram encontrados padrões de chaves privadas, tokens GitHub ou chaves AWS nos 96 blobs examinados no histórico local. Isso não substitui a revogação de credenciais caso alguma tenha existido fora desses padrões.

O `pip-audit` não pôde consultar a base externa nesta sessão porque a revisão automática de rede foi bloqueada por limite de uso. As versões foram comparadas aos avisos oficiais publicados pelos projetos e fixadas nas versões corrigidas disponíveis no PyPI; a execução oficial do workflow deve repetir a auditoria antes da publicação.

## Correção posterior de HTTPS

Após reproduzir a falha da Central instalada, corrigida a geração SKI/AKI dos certificados e acrescentada compatibilidade restrita às autoridades antigas do projeto. A consulta pelo cliente corrigido ao servidor instalado passou, mantendo validação de cadeia e hostname. Suíte completa após a alteração: **23 testes aprovados em 15,94 segundos**, com os mesmos 537 avisos de depreciação. Consulte CORRECAO_HTTPS.md. A instalação atual não foi modificada.

## Modos de abertura e conferência histórica

Acrescentados os modos **Normal**, **Tela cheia** e **Modo quiosque** para a Mesa Eleitoral e a Urna. Cada combinação de área e modo recebe um perfil próprio do Edge, impedindo que uma janela já aberta faça o navegador ignorar o modo solicitado. A auditoria do pacote anterior está em AUDITORIA_FUNCOES_2.3.0.md. Suíte completa após esta alteração: **27 testes aprovados**, com os mesmos avisos de depreciação já conhecidos.

## Margem de segurança antes do corte

O painel da Urna agora permite configurar de **10 a 80 mm** de espaço em branco entre o último conteúdo e a guilhotina, com padrão de **30 mm**. O valor local é aplicado a todos os trabalhos da urna, inclusive ficha de voto, zerésima, boletim e texto operacional. O teste físico passou a imprimir duas amostras: ficha e três assinaturas. Alterar o valor invalida a confirmação anterior e exige novo teste.

Foram acrescentados 10 testes para limites, conversão milimétrica ESC/POS, corte desativado e prevalência da configuração local. Os **22 testes do módulo de execução e impressão passaram** no ambiente temporário Python 3.12. A suíte completa permanece configurada no GitHub para Python 3.13; uma execução local da parte TLS em Python 3.12 não ativa `VERIFY_X509_STRICT`, diferença já coberta pela configuração oficial do workflow.
