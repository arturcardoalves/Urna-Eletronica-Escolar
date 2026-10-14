# Histórico de versões

Este arquivo registra somente versões e alterações que podem ser comprovadas pelo código e pelos documentos preservados no repositório.

## Revisão de 12/10/2026 — código 2.3.0

- Confirmação por mouse em cartão compacto centralizado; CORRIGIR vermelho.
- Cadastro com nome/turma obrigatórios e matrícula/turno opcionais.
- Som sempre habilitado e aviso de impressão na própria tela FIM/VOTOU.
- README renovado, quatro capturas oficiais com dados fictícios e guias de dúvidas e validação.
- Inclusão controlada das capturas no pacote de fontes; fotos eleitorais continuam excluídas.
- Essas mudanças mantêm o número 2.3.0; confira o commit e a data do build ao baixar o instalador.

## 2.3.0 — versão atual

### Aplicação e instalação

- Instalador único para **Central + Mesa Eleitoral** ou **Urna + impressora USB**.
- Aplicativo Windows único para iniciar, acompanhar e diagnosticar cada papel.
- Limpeza de builds, ambientes virtuais, caches, lançadores HTA/BAT e assistentes antigos que não participavam da compilação atual.
- Build automatizado no GitHub Actions com Python 3.13, testes e artefato do instalador.

### Rede e segurança

- Descoberta automática da Central na rede local.
- Vínculo com aprovação administrativa, código comparado nos dois computadores e certificado fixado.
- Correção de compatibilidade HTTPS com Python 3.13 e autoridades antigas do projeto.
- Token da Urna protegido pelo Windows e firewall limitado à rede local.
- Bloqueio de atualização durante eleição lacrada ou aberta, com backup antes da atualização.

### Operação

- Modos **Normal**, **Tela cheia** e **Quiosque** para Mesa e Urna.
- Perfis separados do Edge por área e modo.
- Reconexão automática quando o endereço da Central muda.
- Auditoria das funções existentes antes da limpeza do pacote.

### Impressão

- Impressão nativa executada pelo aplicativo da Urna.
- Ficha de voto, zerésima e boletim com suporte a Driver Windows e ESC/POS.
- Margem antes do corte configurável entre 10 e 80 mm, com padrão de 30 mm.
- Teste físico com duas amostras: ficha de voto e três assinaturas.
- Diário que impede repetição automática de um trabalho com resultado incerto.

### Testes

- Suíte automatizada com resultados por execução; consulte [Testes e validação](TESTES_E_VALIDACAO.md).
- Cobertura de votação, concorrência, autenticação, vínculo, TLS, impressão, recuperação, atualização e modos do navegador.

## 2.2.1 — versão legada

- Base anterior à instalação unificada.
- Utilizava documentos, lançadores e processos de build separados.
- Os arquivos antigos de geração do EXE foram retirados quando suas funções passaram para `installer/BUILD_WINDOWS.ps1`, o aplicativo unificado e o workflow do GitHub.

Não há garantia de compatibilidade de bancos ou instaladores antigos fora dos procedimentos de atualização descritos na versão 2.3.0.
# Publicação offline e portal — 13/10/2026

- Configuração pública vinculada à lacração, chave Ed25519 por eleição e pacotes assinados sem dados individuais de eleitores.
- Zerésima/BU por urna com PDFs públicos e dois QR Codes; exportação automática para uma mídia USB e reexportação idêntica.
- Transmissor Eleitoral Windows independente, verificação offline, confirmação do operador, HTTPS e comprovante idempotente.
- Portal Cloudflare Workers + D1 preparado para plano gratuito, arquivo de eleições, parcial/definitivo, versões e verificação pública.
- Correção do BU de urna sem votos: mantém zero, sem herdar o resultado agregado de outras urnas.
- Testes de assinatura, adulteração, transmissão HTTPS, recuperação de resposta perdida, mídia, concorrência e integração; validação local Workers/D1.
- Hospedagem externa e impressão física permanecem sujeitas à configuração e ensaio documentados.
