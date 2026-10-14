# Revisão para o novo EXE — 14/10/2026

O código atual foi revisado e recompilado no Windows. A eleição continua offline; a publicação externa permanece separada. Nenhum banco, foto, voto, senha ou backup real foi apagado para produzir esta entrega.

## Ajustes desta revisão

- Build Windows no GitHub fixa Node 24 para os testes de interface e Ed25519.
- Cada build usa uma pasta de dados de teste com UUID novo. O teste não reutiliza um banco de compilação anterior.
- Novo `installer/smoke_frozen.py` verifica os executáveis compilados em perfil e banco descartáveis, com Python externo removido do PATH. É executado também no workflow após gerar o transmissor.
- Novo teste da rota administrativa de exportação: mesário e acesso local sem credencial são recusados; zerésima sem confirmação de impressão não sai para USB; reexportação mantém bytes; arquivo adulterado com mesmo ID não é sobrescrito.
- Instalador inclui guias de publicação, Cloudflare, protocolo e recuperação, além do guia de instalação. Regras de remoção do firewall recebem RunOnceId.
- Guia de instalação explica a separação entre votação offline, mídia e transmissor independente. Documentação Cloudflare reflete o portal publicado e o cadastro de confiança ainda pendente.

## Testes efetivamente executados

| Área | Evidência |
|---|---|
| Suíte Python completa | **99 passaram**, sem falhas ou skips; `test-results/final-all-tests-2026-10-14.xml`. 869 avisos de depreciação existentes. |
| JavaScript oficial e verificador | **19 passaram** no build: teclado/mouse, tela de impressão, som, recuperação, assinaturas e câmera simulada. |
| Worker Cloudflare + D1 emulado | **5 passaram**: assinatura Python/JavaScript, sequência, duplicação, PDFs, revisões, QR térmico decodificado, eleição atual e resposta após falha. Dados fictícios somente no emulador. |
| USB pela Administração | Exportação e reexportação por rotas reais, permissões e confirmação de impressão. Pasta temporária representa o pendrive. |
| Transporte e impressora | A suíte exercita HTTPS local, resposta perdida após gravação, mesmo comprovante no reenvio, drivers simulados e recuperação. |
| Dependências | `pip check`: nenhuma dependência quebrada. Sintaxe compilada antes do build. |
| EXEs Windows | Servidor, Central/Urna, proteção de atualização e Transmissor recompilados; autotestes passaram. |
| Primeiro uso congelado | Com EXEs reais: HTTPS com CA/hostname, primeiro ADMIN (segundo cadastro recusado), aluno só com nome/turma, chapa, mesário, urna, chave DPAPI, lacração, pacote/PDF público e bloqueios após lacração. `test-results/frozen-final-2026-10-14.log`. Dados descartados depois. |
| Conteúdo do runtime | Nenhum DB, WAL, SHM, pacote eleitoral ou chave privada nos runtimes. Módulos de publicação presentes nos três executáveis. Os dois PEMs são certificados públicos de CA do certifi. `test-results/package-audit-2026-10-14.json`. |
| Instalador | Inno Setup concluiu a compilação. Não executei a instalação sobre este computador nem modifiquei suas regras de firewall/registro. |
| Fonte limpa | Gerada por allowlist e relida com conferência SHA-256 de cada arquivo. Sem bancos, dados de eleição, chaves, credenciais, caches, ambientes virtuais ou resultados de teste. |

## Pendência de operação que precisa ser concluída

A consulta à conta Cloudflare em 14/10/2026 retornou lista de secrets vazia. O portal **não tem `TRUST_REGISTRY` cadastrado**. Isso bloqueia transmissões até que as referências da eleição e a credencial sejam cadastradas. Não é uma configuração que o instalador deva embutir: cada eleição gera sua própria chave.

Antes de lacrar a eleição real:

1. Na Administração → Publicação e mídia USB, salve `https://urna-escolar-portal.arturcardoalves.workers.dev`.
2. Copie o UUID e a impressão digital pública da chave gerados pela Central.
3. Cadastre-os no portal com a ferramenta `portal.enroll` e envie o cadastro pelo `wrangler secret put TRUST_REGISTRY`, seguindo [PORTAL_CLOUDFLARE.md](PORTAL_CLOUDFLARE.md).
4. Guarde a credencial com o operador do Transmissor. Nunca a coloque no GitHub ou no código.
5. Lacre, exporte a configuração e transmita; depois transmita zerésimas e boletins na sequência. Confira cada comprovante.

O Transmissor valida o endereço lacrado, UUID, chave, assinatura, hashes e retorno do servidor. Os testes não transmitiram eleições fictícias ao portal público. A verificação ponta a ponta da sua eleição no portal depende desse cadastro e do envio pelo operador.

## Limites presenciais

Ainda precisam de ensaio: instalador em Windows limpo sem Python, dois computadores físicos e roteador/firewall, pendrive físico, impressora de 80 mm (papel, margem e guilhotina), som nos alto-falantes, falta de energia e câmera dos celulares. Os testes de câmera usam mocks; o decoder leu QR real gerado pelo sistema em raster. O instalador mantém um aviso sobre limpeza de entradas HKCU antigas em instalação administrativa; a instalação com credenciais de outro usuário deve ser conferida presencialmente.

## Recompilar

Na raiz da cópia de código, no Windows com Python 3.13, Node 24 e Inno Setup 6 para compilação:

```powershell
.\installer\BUILD_WINDOWS.ps1
.\installer\BUILD_TRANSMITTER.ps1
.\.build-venv\Scripts\python.exe .\installer\smoke_frozen.py
```

O GitHub Actions prepara os runtimes de compilação e executa esses processos. Os computadores da votação e o computador do transmissor usam os EXEs e não precisam de Python/Node. O portal já publicado permanece independente do instalador; sua atualização usa o workflow/comandos próprios.
