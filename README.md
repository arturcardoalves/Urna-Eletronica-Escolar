# Urna Eletrônica Escolar 2.3.0

Código para dois computadores Windows: Central + Mesa Eleitoral e Urna + impressora USB. Esta revisão limpa corrige o bloqueio SQLite no teste do aplicativo e mantém a versão 2.3.0.

Também corrige a Central que não reconhecia o servidor ativo por incompatibilidade do certificado com Python 3.13, oferece abertura Normal, Tela cheia e Quiosque para Mesa e Urna e permite calibrar o espaço antes do corte da impressora. [Detalhes da correção HTTPS](docs/CORRECAO_HTTPS.md) · [Auditoria das funções](docs/AUDITORIA_FUNCOES_2.3.0.md). Total atual: 37 testes automatizados.

## Gerar o EXE

Envie o conteúdo desta pasta para a raiz do repositório, incluindo `.github`. Abra Actions → Build Windows Installer → Run workflow. O GitHub compila com PowerShell em um Windows temporário, roda os testes e publica o instalador como artefato da execução.

Resultado: `Instalar_Urna_Escolar_2.3.0.exe`. O mesmo instalador atende os dois computadores da eleição; eles não precisam de Python.

[Comandos e instruções](docs/GERAR_EXE_NO_GITHUB.md) · [Instalação e uso](docs/GUIA_2.3.0.md) · [Revisão e testes](docs/REVISAO_CODIGO.md)

## Compilar no seu Windows

Com Python 3.13 de 64 bits, Inno Setup 6, Edge e internet para baixar dependências, abra o PowerShell nesta pasta:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer\BUILD_WINDOWS.ps1
```

Saída: `installer/output/Instalar_Urna_Escolar_2.3.0.exe`. A compilação local não instala o programa automaticamente. Feche a Central antes de compilar: o teste usa a porta 8443 e dados isolados em `test-results/runtime`.

## Estrutura

- `URNA_ESCOLAR_SOURCE`: servidor, interface e biblioteca de impressão.
- `installer`: aplicativo Central/Urna, descoberta de rede, proteção de atualização e compilação.
- `.github/workflows`: compilação automática no GitHub.
- `tests`: votação, autenticação, recuperação e transações.
- `docs`: instalação, comandos e registro da revisão.
- `SEGURANCA.md`: funcionamento e limites de segurança.

Os BATs redundantes, assistente antigo, lançadores HTA e resultados antigos foram retirados. O PowerShell, os arquivos `.spec` e `UrnaEscolar.iss` são necessários para criar o EXE e foram mantidos.

Somente a urna imprime. A Central deve permanecer aberta ou minimizada durante a eleição. Na Urna, ajuste o espaço antes do corte e execute o teste completo de ficha e assinaturas; esse valor é aplicado a todas as impressões. Antes do uso, teste os dois PCs, rede, impressora, corte, fonte Atkinson Hyperlegible Regular/Bold, zerésima, votação e boletim final.
