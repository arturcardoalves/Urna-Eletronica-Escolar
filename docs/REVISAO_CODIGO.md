# Revisão e limpeza — 08/10/2026

Base: pacote local Urna_Escolar_2.3.0. A revisão foi feita numa cópia; a pasta original permanece preservada. A numeração foi mantida porque esta é uma correção de empacotamento e organização da mesma versão.

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

Executada a suíte nesta cópia com Python 3.13 e as dependências existentes da versão original: **20 testes aprovados**, em 15,19 segundos. Inclui eleição com 20 votos, apuração, PDF, voto repetido/concorrrente sem duplicação, impressão com falha, reimpressão autorizada, desconexão, vinculação e proteção de atualização. Também inclui a nova regressão do SQLite.

O parser do PowerShell não encontrou erros de sintaxe no script de compilação. Os testes produziram 537 avisos de depreciação de bibliotecas/APIs existentes; não foram falhas. Esta revisão não migrou toda a aplicação para novos padrões de datas e lifecycle.

Não foi gerado nem instalado um novo EXE nesta revisão. A compilação e os testes do executável empacotado serão executados pelo workflow ao enviar o código ao GitHub. Testes reais nos dois PCs e na impressora ainda são necessários.
