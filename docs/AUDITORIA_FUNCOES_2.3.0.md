# Auditoria de funções da versão 2.3.0

Data da conferência: 08/10/2026.

## Base da comparação

Foi comparada a pasta original `Urna_Escolar_2.3.0`, anterior à limpeza e ao novo fluxo de EXE, com o repositório atual `Repositorio_HTTPS_Atualizado`.

Nos arquivos Python, JavaScript, HTML e CSS da aplicação eleitoral, 25 arquivos-fonte eram idênticos. Nenhum arquivo-fonte da aplicação estava ausente. As diferenças intencionais estavam em `integrity.py`, para retirar referências a executáveis antigos, e em `admin.html`, para ajustar instruções. Os demais itens diferentes encontrados eram caches `__pycache__`, que não são código-fonte.

Os arquivos antigos `setup_assistant.py` e `print_agent_launcher.py` não eram chamados pelo `BUILD_WINDOWS.ps1` nem incluídos por `UrnaEscolar.iss` na versão unificada. Suas funções úteis foram absorvidas pelo aplicativo atual: escolha do papel no instalador, descoberta e vínculo automáticos, certificado automático, seleção/teste de impressora, diagnóstico, inicialização do servidor e impressão nativa. O servidor HTTP separado de impressão deixou de ser necessário porque a biblioteca de impressão é carregada diretamente no aplicativo da urna.

## Funções confirmadas no código atual

| Área | Funções presentes |
|---|---|
| Instalação | Um instalador para Central + Mesa ou Urna + impressora; backup e bloqueio de atualização durante eleição lacrada/aberta |
| Central e rede | Servidor HTTPS, descoberta na LAN, vínculo aprovado por código, certificado fixado, reconexão e diagnóstico |
| Administração | Primeiro acesso, usuários ADMIN/MESÁRIO, configuração da eleição, chapas, integrantes, fotos, eleitores manuais e importação |
| Urnas | Cadastro/vínculo, estado online, modo individual teclado ou mouse/toque e padrão herdado da eleição |
| Mesa | Login próprio, pesquisa/lista por turma, liberação e cancelamento, operação sem identificação nominal, acompanhamento das urnas |
| Abertura | Lacração, verificação de integridade, geração e impressão da zerésima nas urnas e confirmação antes de abrir |
| Votação | Teclado numérico, seleção visual, branco, corrige, confirma, proteção contra repetição e registro sem identidade junto ao voto |
| Impressão | Teste físico, voto em 80 mm, zerésima, boletim, corte, diário contra duplicação, falha e reimpressão autorizada pelo mesário |
| Encerramento | Bloqueio de novos votos, apuração, boletim final nas urnas e PDF do resultado |
| Auditoria | Log append-only, PDF de logs, ocorrências automáticas, hashes, lacração, verificação de integridade e comprovante de segurança |
| RDV | Conteúdo criptografado, posições aleatórias, exportação JSON e verificação da cadeia dos votos |
| Relatórios | Zerésima, listas de eleitores, comparecimento, ausentes, ocorrências, logs, resultado e RDV |
| Interface | Fonte legível, foto 3:4, modo teclado/mouse por urna e abertura Normal/Tela cheia/Quiosque para Mesa e Urna |

Também foi corrigida uma instrução antiga no Administrador que ainda citava impressão na Mesa. O comportamento e o texto agora refletem a decisão vigente: a impressora fica somente no computador da urna.

## Itens discutidos, mas ausentes nos dois pacotes comparados

Estes itens não foram perdidos na limpeza: eles não existiam no código original 2.3.0 usado na comparação.

- **Módulo isolado “Teste da Eleição”** usando a mesma votação com dados marcados como teste.
- **QR Code verificável no boletim final.** O boletim contém hashes, mas não gera QR.
- **Impressão térmica do log operacional.** O PDF e o texto do log existem, porém não há comando de interface que envie esse documento às impressoras das urnas.

Esses pontos devem ser tratados como funcionalidades pendentes, caso ainda façam parte do escopo desejado. Acrescentá-los exige implementação e testes próprios; não são uma simples restauração de arquivos removidos.

## Validação desta alteração

A Mesa e a Urna agora possuem três botões: **Normal**, **Tela cheia** e **Modo quiosque**. Cada área e modo usa um perfil separado do Edge para garantir que o navegador respeite a opção mesmo quando outra janela já foi aberta. Administração e Mesa continuam com sessões separadas.

A suíte completa passou com **27 testes**. Foram verificados os argumentos dos três modos, perfis separados, rejeição de modos inválidos, votação completa, impressão/reimpressão, apuração, integridade, HTTPS e recuperação. Permanecem avisos de depreciação já existentes nas bibliotecas, sem falhas de teste.
