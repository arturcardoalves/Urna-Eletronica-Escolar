# Portal gratuito: GitHub + Cloudflare

[← Publicação e operação](PUBLICACAO_E_PORTAL.md)

O portal de produção está em [`portal/cloudflare`](../portal/cloudflare). Usa **Workers Free + D1** e endereço HTTPS `workers.dev`. Não exige VPS, R2 nem domínio comprado. O GitHub mantém o código e executa os testes/builds; a Cloudflare recebe e publica os documentos.

O servidor Python em `portal/app.py` é uma referência funcional para testes locais do mesmo protocolo. Não é necessário hospedar Python para usar esta opção Cloudflare.

## Limites que precisam ser acompanhados

Segundo a documentação consultada em 13/10/2026, Workers Free limita requisições dinâmicas a 100 mil por dia e CPU a 10 ms por execução. Assets estáticos são gratuitos; D1 Free limita cada banco a 500 MB, com até 5 GB por conta e cotas diárias de leitura/escrita. Consulte os valores atuais antes de colocar a eleição no ar: [Workers](https://developers.cloudflare.com/workers/platform/limits/), [assets](https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/) e [D1](https://developers.cloudflare.com/d1/platform/limits/).

Os pacotes têm limite de **8 MiB**. São armazenados em blocos de 512 KiB para respeitar o limite de linha do D1; o ZIP usa entradas sem compressão, reduzindo processamento no Worker. PDFs e PNGs já possuem compressão interna. Fotos são redimensionadas pela Central e têm os metadados removidos. Não há mudança automática para plano pago nem descarte automático de eleições antigas. O uso real do plano gratuito, principalmente com fotos grandes e muitos acessos, precisa ser observado nas métricas da sua conta.

## Primeira publicação — computador com internet

Instale Node.js 24 e pnpm 11.25.0. Na pasta do repositório:

```powershell
Set-Location .\portal\cloudflare
pnpm install --frozen-lockfile --ignore-scripts
pnpm exec wrangler login
pnpm exec wrangler d1 create urna-escolar-publicacoes
```

A autenticação abre o navegador para você autorizar sua conta Cloudflare. Copie o `database_id` retornado para `wrangler.toml`, substituindo somente `00000000-0000-0000-0000-000000000000`. Não coloque token de conta no arquivo.

```powershell
pnpm exec wrangler d1 migrations apply urna-escolar-publicacoes --remote
pnpm run deploy
```

O comando retorna o endereço HTTPS do portal. Abra-o e confirme que aparece **Não há votações no momento**. Copie esse endereço para o painel administrativo antes da lacração. O banco começa sem eleições e sem credenciais compartilhadas.

## Reconhecer a chave da eleição

No painel da Central, salve o endereço do portal e obtenha UUID e impressão digital da chave. No computador de manutenção do portal, execute o cadastrador pela raiz do repositório, com Python e as dependências da ferramenta disponíveis:

```powershell
python -m portal.enroll --file 'C:\ConfiguracaoPortalUrna\trusted.json' --election 'UUID-COPIADO-DA-CENTRAL' --fingerprint 'SHA256-COPIADO-DA-CENTRAL' --url 'HTTPS-RETORNADO-PELA-CLOUDFLARE'
```

O comando gera uma credencial aleatória e a exibe uma vez. Guarde-a e entregue-a somente ao operador do transmissor. O arquivo contém referências públicas e **hashes** das credenciais, não chaves privadas da eleição nem o valor bruto da credencial. Mantenha-o fora do repositório e com acesso restrito: sua integridade determina quais chaves o portal reconhece.

Na pasta `portal/cloudflare`, envie o cadastro como secret, sem escrevê-lo no código:

```powershell
Get-Content -LiteralPath 'C:\ConfiguracaoPortalUrna\trusted.json' -Raw | pnpm exec wrangler secret put TRUST_REGISTRY
```

Cadastre cada nova eleição preservando as referências das anteriores. O portal recusa chaves novas ou eleições diferentes até esse cadastro confiável. Para revogar acesso, substitua apenas o hash da credencial daquela eleição no arquivo protegido e envie o secret novamente; preserve a impressão digital da chave lacrada.

## Usar o GitHub para atualizar

O workflow [`Portal Cloudflare - testes e publicacao`](../.github/workflows/portal-cloudflare.yml) testa o Worker com D1 emulado a cada mudança relevante. Publicar é uma execução manual com `publish=true`, após configurar o ID real do banco.

No GitHub, crie o ambiente `cloudflare` e os secrets `CLOUDFLARE_API_TOKEN` e `CLOUDFLARE_ACCOUNT_ID`. O token deve se limitar à conta correta e às permissões necessárias para editar Workers, assets e D1. Não use a Global API Key. O secret `TRUST_REGISTRY` deve ser cadastrado diretamente no Worker pelo comando acima; nunca o coloque em assets públicos.

Faça uma primeira publicação pela CLI para obter o endereço e criar as referências; depois use o workflow manual para atualizações. O envio do código por push executa testes, sem iniciar publicação automaticamente.

## Backup e recuperação

Mantenha os `.uepkg` originais e os comprovantes fora do Git. Exporte também o banco público:

```powershell
pnpm exec wrangler d1 export urna-escolar-publicacoes --remote --output 'C:\BackupsPortalUrna\publicacoes.sql'
```

Não salve esse SQL na pasta do projeto. D1 Free oferece Time Travel de sete dias, mas ele não substitui backup externo e ensaio de restauração. [Documentação de recuperação](https://developers.cloudflare.com/d1/reference/time-travel/).

Antes de substituir o banco por uma restauração, teste o backup em outro banco, confira IDs/hashes e mantenha cópia do original. Nunca apague resultados anteriores para liberar espaço durante uma eleição. Monitore armazenamento e uso; o portal pode recusar novas gravações ao atingir a cota, enquanto a Central mantém os documentos para envio posterior.

## O que foi validado e o que ainda depende da conta

Foi executado o Worker em `workerd`/Wrangler local com D1 real emulado, usando pacotes assinados pelo código Python: configuração, ordem das etapas, zerésimas, BUs, parcial/definitivo, PDFs, download idêntico, revisão anterior preservada e reenvio concorrente sem duplicação. O bundle também foi gerado em `deploy --dry-run`.

Em 14/10/2026, o banco D1 está configurado e o portal foi publicado em https://urna-escolar-portal.arturcardoalves.workers.dev. As rotas públicas foram conferidas por HTTPS; não foram enviados dados fictícios ao portal de produção. O cadastro de confiança `TRUST_REGISTRY` ainda está pendente e bloqueia transmissões até que UUID, impressão digital e credencial da eleição sejam cadastrados conforme este guia. Os secrets do GitHub só são necessários para publicar por Actions, não para a publicação manual já realizada.

As cotas e o limite de CPU do plano gratuito não são reproduzidos integralmente pelo emulador local. A câmera física de celulares e a leitura dos documentos impressos precisam de teste presencial. A interface atual usa somente câmera, sem campos de digitação ou upload; veja [o comportamento da página inicial e do verificador](PUBLICACAO_E_PORTAL.md#página-inicial-e-verificação-pela-câmera).
