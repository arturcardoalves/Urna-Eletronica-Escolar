# Entrega da publicação eleitoral — 13/10/2026

Esta entrega integra a votação existente, o transporte por pendrive, o Transmissor Eleitoral e um portal preparado para **GitHub + Cloudflare Workers Free/D1**. O portal externo não foi publicado nesta sessão: ainda depende da conta, banco e referências de confiança do responsável.

## Implementado

- Endereço de publicação e impressão digital Ed25519 vinculados à lacração; chave privada única por eleição, protegida por DPAPI no Windows.
- Documentos públicos assinados, IDs únicos, SHA-256 dos arquivos, PDFs por urna e dois QR Codes no raster térmico.
- Exportação automática quando a Central detecta uma única mídia removível; escolha manual com várias mídias; reexportação dos mesmos bytes.
- Liberação de zerésima/BU para USB somente após o agente confirmar a impressão daquela versão. Falhas preservam documentos pendentes.
- Transmissor Windows independente, reconhecimento da mídia/pacotes, verificação offline, conferência da identidade esperada, confirmação do operador, HTTPS e comprovantes persistentes.
- Portal com configuração, chapas/integrantes/fotos, zerésimas, BUs, PDFs, contagens por urna, totalização parcial/definitiva, pendências e histórico de versões.
- Validação de chave cadastrada, eleição, assinatura, formato, hashes, sequência, duplicações e revisões. Retificações acrescentam notas e preservam os valores lacrados.
- Verificador no navegador e ferramenta independente offline. Assinatura válida e identidade reconhecida são diferenciadas.
- Empacotamento de fontes e recursos do EXE por seleção de arquivos; uploads antigos e dados de execução são excluídos sem apagar os originais.

## Correções relevantes

Uma urna sem votos não herda mais o resultado global: seu BU e pacote permanecem zerados. O modo sem identificação informa comparecimento não aferido no documento térmico. A exportação verifica junções/links antes de criar diretórios, impede destinos fora da mídia e recusa sobrescrever mesmo ID com conteúdo diferente. Retificações precisam da própria confirmação de impressão antes de exportar.

A revisão também preserva as melhorias anteriores do README, documentação, capturas oficiais e cartão de confirmação já aprovados nesta conversa.

## O que foi executado

| Verificação | Resultado e alcance |
|---|---|
| Suíte Python completa | **97 passaram, nenhuma falha ou skip**, em `test-results/final-all-tests.xml`. Os bancos são temporários. |
| Interface JavaScript | **14 passaram**; incluem impressão na tela VOTOU, recuperação, autorização, escolha e som. DOM/rede são simulados. |
| Verificador JavaScript | **2 passaram**; JSON canônico, Ed25519 válido e alteração recusada. |
| Cloudflare | **3 suítes passaram** com Worker/workerd e D1 emulados: pacotes Python, etapas, parcial/definitivo, PDFs, bytes originais, revisões e reenvio concorrente. Bundle em `deploy --dry-run` gerado. |
| Votação real do código em teste | Primeiro acesso, configuração, vinculação, lacração, zerésima, liberação, chapa/branco, duplicação bloqueada, impressão simulada, encerramento e apuração. Duas urnas votaram simultaneamente em clientes isolados sem cruzar os totais. |
| Transmissão HTTPS | Servidor TLS local real, CA específica, assinatura e comprovante; resposta interrompida depois da gravação e reenvio retornando o mesmo protocolo. |
| Impressão | Rasters completos de zerésima/BU a 576 pontos; os dois QR Codes foram decodificados automaticamente. Houve testes de erro/retomada, corte e assinatura 3 com drivers simulados. Nenhum papel foi impresso fisicamente. |
| Fotos | Imagem pública foi gerada sem o metadado privado colocado no PNG de teste. |
| Mídia | Reexportação idêntica, conflito, falha de escrita e junção para diretório externo bloqueados. Disco temporário representa a mídia; não foi feito ensaio em pendrive físico. |
| PDFs | Duas páginas do BU fictício renderizadas e inspecionadas visualmente: texto, hashes, QR Codes e assinaturas presentes. |
| Navegador | Página inicial/resultados do Worker, largura de 390 px sem expansão horizontal, QR/manifesto/PDF conferidos localmente. Uma limitação inicial da ferramenta foi resolvida após sua liberação. |
| Windows | Servidor, Central/Urna, guardião de atualização e transmissor compilados; instalador Inno Setup gerado. Autotestes e primeiro ADMIN/configuração DPAPI com Python externo fora do PATH, dados isolados e CA/hostname verificados. |

O Curl/Schannel inicialmente recusou o certificado privado porque não conseguiu consultar revogação offline. O teste foi repetido com a CA exata, hostname validado e `--ssl-revoke-best-effort`, que trata indisponibilidade dessa consulta. Não foi usado `-k` nesse teste final, nem alterada a política TLS do produto. [Comportamento oficial da opção](https://curl.se/docs/manpage.html#--ssl-revoke-best-effort).

Há avisos de depreciação em código existente (`utcnow`/`on_event`) e um aviso Inno Setup sobre áreas por usuário em instalação administrativa. Eles não causaram falha nas verificações executadas. Não equivalem a validação do instalador em todos os perfis Windows.

## O que ainda depende de validação/configuração externa

- Publicar na conta Cloudflare, substituir o ID D1, cadastrar a chave da comissão e a credencial, configurar os secrets GitHub e conferir o HTTPS no endereço retornado.
- Observar CPU, acessos e armazenamento no plano gratuito. O emulador local não reproduz todas as cotas da nuvem.
- Instalar o instalador final em um Windows limpo sem Python/Node e ensaiar os papéis Central/Urna. O teste de PATH é útil, mas não é uma instalação em máquina limpa.
- Conferir dois computadores físicos, roteador, firewall, reinicialização, falta de energia, som nos alto-falantes e impressão real de 80 mm, incluindo margem, guilhotina e leitura dos QR Codes por celulares.
- Ensaiar restauração dos dados e do perfil Windows que protege a chave DPAPI. Não presumir que copiar a chave para outro usuário basta.

Não há alegação de auditoria independente, sigilo absoluto ou invulnerabilidade. O portal publica declarações assinadas pelo emissor reconhecido; a comissão precisa conferir cadastro, documentos, fichas e totais.

## Arquivos e preparação limpa

Não foi excluído banco, eleição, foto ou backup real. O pacote final é uma cópia selecionada: exclui bancos/WAL/SHM, chaves, credenciais, uploads, pacotes eleitorais, logs, caches, dependências instaladas e saídas de testes/build. O EXE não inclui a pasta legada de uploads. Os PEMs encontrados nos runtimes são o conjunto público de CAs do `certifi`, sem chave privada.

O antigo validador gerado `validate.js` foi substituído por `validate.cjs`, para funcionar no runtime Workers sem `eval`; bundles intermediários ficam em `test-results`, fora da entrega. Nenhum arquivo funcional antigo foi removido por suposição. Testes úteis e recursos de licença foram preservados.

Os dados fictícios ficam nos testes e nas imagens explicativas; os serviços de produção iniciam vazios. O ZIP é relido e conferido contra seu manifesto SHA-256 pelo empacotador.

## Instruções definitivas

1. [Configurar o portal gratuito](PORTAL_CLOUDFLARE.md).
2. [Instalar e iniciar Central/Urna](GUIA_2.3.0.md).
3. [Configurar publicação, lacrar, imprimir, exportar e transmitir](PUBLICACAO_E_PORTAL.md).
4. [Verificar assinaturas e reconhecer a chave](PROTOCOLO_PUBLICACAO.md).
5. Fazer o ensaio presencial antes de usar dados reais.

## Arquivos alterados nesta entrega

Os caminhos abaixo incluem código integrado e documentação preservada da revisão anterior. Os binários e o ZIP final ficam fora do Git; alterações ainda não foram enviadas ao GitHub automaticamente.

- `.github/workflows/build-windows-installer.yml`
- `.github/workflows/portal-cloudflare.yml`
- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/ENTREGA_PUBLICACAO_2026-10-13.md`
- `docs/GUIA_2.3.0.md`
- `docs/imagens/capa.svg`
- `docs/imagens/portal-publico.png`
- `docs/imagens/README.md`
- `docs/imagens/urna-aguardando.jpg`
- `docs/imagens/urna-confirmacao.jpg`
- `docs/imagens/urna-escolha.jpg`
- `docs/imagens/urna-impressao.jpg`
- `docs/imagens/visao-geral.svg`
- `docs/PERGUNTAS_FREQUENTES.md`
- `docs/PORTAL_CLOUDFLARE.md`
- `docs/PROTOCOLO_PUBLICACAO.md`
- `docs/PUBLICACAO_E_PORTAL.md`
- `docs/TELAS.md`
- `docs/TESTES_E_VALIDACAO.md`
- `installer/build_assets.py`
- `installer/BUILD_TRANSMITTER.ps1`
- `installer/BUILD_WINDOWS.ps1`
- `installer/desktop_app.py`
- `installer/desktop.spec`
- `installer/package_source.py`
- `installer/requirements-build.txt`
- `installer/server.spec`
- `installer/transmitter.spec`
- `portal/__init__.py`
- `portal/app.py`
- `portal/cloudflare/document-schema.json`
- `portal/cloudflare/generate-validator.mjs`
- `portal/cloudflare/migrations/0001_publications.sql`
- `portal/cloudflare/package.json`
- `portal/cloudflare/pnpm-lock.yaml`
- `portal/cloudflare/pnpm-workspace.yaml`
- `portal/cloudflare/src/protocol.js`
- `portal/cloudflare/src/validate.cjs`
- `portal/cloudflare/src/views.js`
- `portal/cloudflare/src/worker.js`
- `portal/cloudflare/tests/portal.test.js`
- `portal/cloudflare/wrangler.toml`
- `portal/Dockerfile`
- `portal/enroll.py`
- `portal/requirements.txt`
- `portal/static/portal.css`
- `portal/static/verify.js`
- `portal/store.py`
- `portal/templates/base.html`
- `portal/templates/document.html`
- `portal/templates/election.html`
- `portal/templates/home.html`
- `portal/templates/verify.html`
- `README.md`
- `SEGURANCA.md`
- `tests/export_cloudflare_fixtures.py`
- `tests/test_build_assets.py`
- `tests/test_distribution.py`
- `tests/test_publication_js.js`
- `tests/test_publication.py`
- `tests/test_transmission.py`
- `transmitter/__init__.py`
- `transmitter/app.py`
- `transmitter/client.py`
- `transmitter/verify.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/integrity.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/main.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/models.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/publication_routes.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/publication.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/services.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/static/publication.js`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/templates/admin.html`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/templates/mesario.html`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/templates/publication.html`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/__init__.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/documents.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/keys.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/media.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/protocol.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/schema.py`
- `URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/requirements.txt`
- `URNA_ESCOLAR_SOURCE/03_URNA/print_agent/agent.py`
- `URNA_ESCOLAR_SOURCE/03_URNA/print_agent/requirements.txt`
