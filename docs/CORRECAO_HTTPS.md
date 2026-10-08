# Central não reconhecia o servidor ativo

Diagnóstico de 08/10/2026: o servidor instalado respondeu a /health e /api/local/status, com banco disponível e estado CONFIG. A consulta pelo mesmo cliente HTTPS da Central falhou com `CERTIFICATE_VERIFY_FAILED: Missing Authority Key Identifier`.

O problema era a incompatibilidade do certificado gerado pelo projeto com a validação estrita ativada por padrão no Python 3.13. A falta de internet e o perfil público da Ethernet não causavam essa falha local.

## Correção

- Novas autoridades e certificados do servidor incluem os identificadores SKI/AKI. O certificado de servidor também inclui KeyUsage.
- Certificados de servidor antigos sem AKI são renovados na inicialização, mantendo a autoridade da Central.
- Quando a autoridade já existente não possui SKI, o cliente usa a compatibilidade anterior ao Python 3.13 exclusivamente para essa autoridade explicitamente fornecida. Assinatura, cadeia de confiança, validade e endereço do servidor continuam obrigatórios. Certificados novos mantêm a validação estrita.
- Não é necessário apagar bancos, autoridades, chaves ou vínculos para essa correção.
- O build agora testa HTTPS com o cliente real e a CA gerada, além do teste de disponibilidade com curl.

## Aplicar

Envie o conteúdo deste pacote ao GitHub, aguarde o workflow e baixe o novo instalador. Feche Urna e Central pelo aplicativo e instale o novo EXE como Central + Mesa no computador de teste. Não atualize se houver eleição lacrada ou aberta. Se usar dois PCs, atualize ambos.

Abra a Central novamente. O estado esperado é **Servidor ativo — HTTPS verificado**. A consulta local com o código corrigido já foi confirmada no servidor atual; o executável instalado ainda precisa ser substituído pelo novo build.

## Testes

Novos testes fazem handshakes TLS em memória com certificados reais: certificado novo em modo estrito; autoridade antiga com compatibilidade; rejeição de endereço incorreto; rejeição de autoridade não confiável. A consulta ao servidor instalado confirmou `CERT_REQUIRED` e `check_hostname=True`.

Referência técnica: https://docs.python.org/3.13/library/ssl.html#ssl.create_default_context
