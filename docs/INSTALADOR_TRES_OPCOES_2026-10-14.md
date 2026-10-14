# Instalador com três funções — 14/10/2026

O mesmo `Instalar_Urna_Escolar_2.3.0.exe` oferece:

1. **Central da Eleição + Mesa Eleitoral:** servidor, administrador e mesa, no computador da rede offline.
2. **Urna de votação + impressora USB:** votação e agente de impressão.
3. **Publicação de resultados — Transmissor Eleitoral:** envio dos pacotes do pendrive ao portal pelo computador com internet.

A terceira opção instala o EXE em `Publicacao/TransmissorEleitoral.exe`, cria o atalho **Publicação de Resultados** e oferece abrir o transmissor ao finalizar. Uma instalação nova dessa opção não copia os runtimes da votação, não inicia a Central automaticamente e não cria regras de entrada para o servidor. A escolha fica registrada como `publicacao` para ser preservada em uma atualização. Dados da Central e configurações de transmissão não são apagados ao atualizar. Ao trocar a função de uma instalação antiga, arquivos instalados anteriormente podem permanecer; os atalhos e a inicialização passam a corresponder à função escolhida.

O transmissor continua independente da votação, exige confirmação do operador e não executa arquivos do pendrive. A opção não hospeda o site neste computador: envia os documentos ao portal Cloudflare já publicado. Cada eleição ainda exige seu cadastro de chave confiável e credencial no portal.

## Alterações

- `installer/UrnaEscolar.iss`: terceira opção, filtros de arquivos por função, ícones/atalhos, inicialização correta e comportamento de rede.
- `installer/BUILD_WINDOWS.ps1`: compila e testa o transmissor antes de montar o instalador. O ensaio de instalação no runner descartável agora cobre `publicacao`, `central` e `urna`, incluindo destino do atalho e ausência de inicialização da votação no papel de publicação.
- `.github/workflows/build-windows-installer.yml`: usa o build integrado, sem recompilar o transmissor duas vezes.
- `installer/upgrade_guard.py`: recusa atualização enquanto o Transmissor estiver aberto.
- `tests/test_windows_delivery.py`: proteção de atualização durante transmissão, com processo simulado.
- README e guias: uso do mesmo instalador nas três funções.

## Validação

- Inno Setup compila os seletores e o pacote com os três aplicativos.
- Testes de entrega Windows: **10 passaram**, incluindo a nova proteção de atualização (processo simulado; nenhum aplicativo real foi fechado).
- Scripts PowerShell foram analisados pelo parser, sem erros de sintaxe.
- O guardião de atualização foi recompilado. Central, Urna e Transmissor usam os runtimes aprovados no ensaio da revisão anterior, sem alterações no código de votação/transmissão.
- Pacote de fonte limpo relido e conferido por SHA-256, sem dados eleitorais ou credenciais.

Não executei o assistente de instalação sobre este computador: ele alteraria o perfil de função, registro e firewall do sistema existente. Os testes de instalação das três funções foram configurados para o runner descartável do GitHub; ainda precisam ser executados nessa cópia pelo Actions, ou em Windows limpo. A compilação local não equivale à instalação presencial. Confira o relatório anterior para os 99 testes de lógica e os ensaios dos EXEs já executados.

## Gerar novamente

Na raiz do projeto, execute `installer/BUILD_WINDOWS.ps1`. Esse comando agora gera os três aplicativos e o instalador unificado. No GitHub, envie os arquivos atualizados e use **Actions → Build Windows Installer**. O artefato principal continua **Instalador-Urna-Escolar-2.3.0**. O Transmissor independente continua disponível como alternativa opcional.
