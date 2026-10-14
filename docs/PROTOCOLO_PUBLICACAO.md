# Formato, confiança e verificação

[← Operação](PUBLICACAO_E_PORTAL.md) · [Segurança geral](../SEGURANCA.md)

## O que a assinatura comprova

Uma assinatura Ed25519 válida comprova que os dados foram assinados pela chave privada correspondente e que o conteúdo assinado não mudou. A identidade da comissão depende de reconhecer previamente a impressão digital dessa chave por um meio confiável. O portal não aceita automaticamente qualquer chave apresentada pela mídia.

A assinatura não torna correto um cadastro errado, um computador comprometido ou uma contagem produzida por software adulterado. A comparação com os documentos impressos, a guarda das fichas, o controle dos computadores e a auditoria da comissão continuam necessários. Não há promessa de segurança ou sigilo absolutos.

## Pacote `.uepkg`, versão 1

O contêiner ZIP contém somente:

- `manifest.json`: envelope com manifesto e assinatura Ed25519;
- `document.pdf`: documento público;
- `photo-N.png`: imagens públicas das chapas previstas no próprio manifesto, quando existem.

O limite do pacote é 8 MiB. Nomes arbitrários, diretórios, arquivos adicionais, duplicatas, caminhos relativos, contêiner criptografado, JSON com chaves repetidas e campos fora do esquema público são recusados. O verificador Python aceita ZIP padrão limitado; os pacotes emitidos atualmente usam entradas sem compressão, que o Worker gratuito reconhece sem descompressão.

O manifesto tem exatamente `document`, `public_key` e `assets`. `assets` registra tamanho e SHA-256 de cada arquivo. O envelope tem exatamente `manifest` e `signature`. A assinatura é calculada sobre:

```text
URNA-PUBLICATION-V1\0 + JSON_CANONICO_ASCII(manifest)
```

Aqui `\0` representa um byte nulo. O JSON canônico tem chaves ordenadas, separadores sem espaços, Unicode escapado, inteiros sem conversão e nenhuma constante não finita. Chave Ed25519 e assinatura usam Base64 URL-safe sem padding. A impressão digital é SHA-256 dos 32 bytes da chave pública, em hexadecimal minúsculo.

O esquema é definido em [`publication_core/schema.py`](../URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/publication_core/schema.py). O Worker usa o JSON Schema correspondente e um validador pré-compilado, acompanhado de validações semânticas de identificação, contagens e datas; não gera código com `eval` no runtime Cloudflare.

O documento identifica UUID da eleição, urnas, documento, tipo e revisão; contém configuração pública, motivo e hash da revisão anterior, referência da configuração e contagens por urna. Também assina versão do sistema, horários públicos de zerésima/abertura/encerramento e hashes de zerésima/conjunto de votos quando aplicáveis. Eleitores são representados somente por quantidades agregadas, nunca por registros individuais.

O sistema existente oferece voto em chapa e branco. **Não foi criada uma opção de voto nulo.** O campo público `null` fica zero nos documentos atuais; registros internos inválidos interrompem a publicação e não são reinterpretados como votos nulos. Isso evita esconder uma falha de integridade sob uma categoria eleitoral.

## QR de verificação

O QR é uma URL HTTPS com fragmento contendo:

```text
UE1|eleicao_uuid|documento_uuid|urna_uuid_ou_-|tipo|revisao|sha256_documento|chave_publica|assinatura
```

A assinatura do QR usa o prefixo separado `URNA-QR-V1\0` e os oito primeiros campos. O fragmento não é necessário para o servidor consultar o documento; o navegador o processa localmente. Essa separação impede reutilizar uma assinatura de pacote como se fosse assinatura de QR.

O QR carrega um **resumo assinado**, e não todas as contagens. Para verificar correspondência com o papel, use o pacote/manifesto, confira o hash indicado pelo QR e compare cada valor exibido. Para verificar o PDF, confira também o SHA-256 do arquivo no manifesto assinado. Um QR legítimo pode ser colado em um papel diferente: a comparação dos valores continua indispensável.

## Verificação independente e offline

No Transmissor Eleitoral, abra o pacote, informe a impressão digital obtida da comissão e clique **Verificar selecionado**. Isso não usa internet nem consulta o portal.

Também é possível verificar pelo código Python, da raiz do projeto:

```powershell
python -m transmitter.verify 'E:\UrnaEscolar_Publicacao\ID-ELEICAO\ID-DOCUMENTO.uepkg' --fingerprint 'SHA256-CONFIAVEL' --election 'UUID-CONFIAVEL' --qr 'TEXTO-OU-URL-DO-QR'
```

O comando verifica assinatura, todos os arquivos, identidade esperada e correspondência QR/pacote, antes de mostrar os dados para confronto com o papel.

O verificador web também usa Ed25519 localmente. Se a chave confiável não for informada, ele diferencia **assinatura válida** de **identidade confirmada**. Não envia arquivos de conferência ao portal. Ed25519 exige suporte do navegador: [Web Crypto no navegador](https://developer.mozilla.org/en-US/docs/Web/API/SubtleCrypto/verify) e [Web Crypto Workers](https://developers.cloudflare.com/workers/runtime-apis/web-crypto/).

## Proteção contra duplicação e alteração

O portal combina ID, hash do pacote e chave reconhecida por eleição. Reenvio idêntico retorna o protocolo original. Mesmo ID com outros bytes é recusado. Revisões precisam seguir a sequência e referenciar o hash anterior. Os arquivos e contagens aceitos não são sobrescritos.

No D1, documento, comprovante e blocos do pacote são gravados em um batch atômico. Restrições únicas e condições SQL protegem contra reenvios concorrentes e totalização que exceda o cadastro. Ao baixar arquivos, o portal reconstrói o pacote e confere seu SHA-256 antes de responder.

As notas de retificação implementadas não mudam valores da eleição lacrada. Corrigir configuração eleitoral exige o fluxo de nova eleição, com nova identidade, e não apagar ou substituir versões antigas no portal.

## Chaves, credenciais e dados

A chave privada Ed25519 fica na Central, protegida por DPAPI do usuário Windows. Não vai ao pendrive, ao transmissor, ao GitHub ou à Cloudflare. O portal armazena somente dados públicos e arquivos assinados. A credencial de transmissão é independente da chave eleitoral; seu hash fica no cadastro protegido do portal.

O portal nunca precisa de certificado da rede eleitoral, senha do administrador/mesário, chave RSA dos votos ou acesso ao banco eleitoral. Proteja também a conta GitHub, a conta Cloudflare e o cadastro de chaves confiáveis: quem controlar esses acessos pode alterar o portal ou quais emissores ele reconhece.
