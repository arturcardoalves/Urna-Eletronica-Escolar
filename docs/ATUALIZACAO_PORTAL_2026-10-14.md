# Atualização do portal — 14/10/2026

- Página inicial dedicada à última configuração publicada, sem catálogo. Vazia ou com todos os BUs recebidos: “Não há votações no momento.” Retificações antigas não mudam a eleição atual. O portal conhece somente as etapas transmitidas, sem consultar a urna offline.
- Verificador exclusivamente por câmera, sem campos de texto ou uploads. jsQR 1.4.0 fixado e servido localmente, com licença Apache-2.0. Conferência Ed25519 do QR e manifesto, identificadores, revisão e hash dos dados. Sem documento disponível, a identidade da chave não é apresentada como confirmada.
- Câmera desligada ao ler QR, parar, ocultar ou sair da página. URLs externas rejeitadas. Dados históricos preservados por endereço e QR.

## Validação executada

- Python: tests/test_publication.py e tests/test_transmission.py — 26 passaram (271 avisos de depreciação existentes).
- Node: tests/test_publication_js.js — 5 passaram, incluindo câmera simulada, permissão recusada e concessão tardia após navegação.
- Cloudflare local/workerd com D1 temporário: 5 passaram, incluindo QR térmico real decodificado com jsQR, adulteração, indisponibilidade, sequência de publicações, duplicação, múltiplas eleições e retificação antiga.
- pnpm run check e wrangler deploy --dry-run: concluídos.
- Deploy real confirmado pelo Wrangler: versão 56e6f883-1b74-4f89-9584-e50e0a2703a3.
- GET HTTPS no portal publicado: /health, /, /verify e /jsQR.js responderam 200. Página inicial sem eleição exibiu a mensagem solicitada. Verificador exibiu botão de câmera sem inputs/textarea.

URL: https://urna-escolar-portal.arturcardoalves.workers.dev

## Limitações

A câmera física de celulares, a permissão em Safari/Chrome reais e a leitura de documentos em papel com diferentes condições de iluminação não foram testadas presencialmente. Os testes de ciclo de câmera usam mocks; o teste do decoder usa o raster real de QR gerado pelo projeto. Não houve transmissão de eleição fictícia ao portal de produção nem alteração do banco de votação. O teste completo de assinatura publicado depende do cadastramento da chave e transmissão de uma eleição real pelo operador. Instalador e EXEs da entrega anterior não foram reconstruídos: esta atualização modifica o portal e sua documentação.
