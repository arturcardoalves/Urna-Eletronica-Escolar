# Urna Escolar 2.4.0 — entrega local

## O que mudou

- **Impressão corrigida:** no modo Windows, zerésima e boletim caíam no formato de texto simples. Agora usam os mesmos desenhos gráficos de 576 pontos do modo ESC/POS: títulos maiores, destaques, totais, hashes e assinaturas. A divisão entre páginas do driver procura espaços em branco para não cortar as letras. O avanço antes da guilhotina continua configurável.
- **Teclado:** Delete é o padrão de CORRIGE no servidor, Administração, urna e demonstração. Uma migração única atualiza o antigo padrão Backspace somente em eleições ainda em CONFIG. Eleições lacradas e teclas personalizadas são preservadas.
- **Somente rede local:** retirados portal, Transmissor, QR Codes, pacotes assinados de publicação e solicitação/exportação por pendrive. O instalador oferece Central/Mesa e Urna. A lacração, autenticação, HTTPS local, integridade, relatórios PDF e histórico local continuam disponíveis.
- **Versão identificável:** Central, Urna, servidor, agente de impressão e instalador exibem 2.4.0. A demonstração continua claramente identificada como teste fictício.

## Limpeza

Removidos os diretórios `portal/`, `transmitter/`, `publication_core/`, rotas e interfaces de publicação, workflow Cloudflare, build do Transmissor, testes exclusivos desses módulos e documentação substituída. As dependências diretas qrcode e zxing-cpp deixaram de ser necessárias e foram retiradas.

Os testes úteis de votação em duas urnas foram preservados em `tests/test_multiple_urns.py`. As únicas referências de manutenção ao antigo Transmissor ficam na proteção de atualização e na retirada de seu executável/atalhos antigos. Não representam uma função disponível na versão nova.

Uma cópia anterior foi guardada fora do repositório, em `Backup_antes_2.4.0`. Não se apagam bancos eleitorais existentes, seus arquivos auxiliares ou as tabelas antigas de publicação durante esta atualização. A distribuição limpa não inclui esses dados nem o backup.

## Testes executados no código

Em Windows, **85 testes Python passaram**, incluindo votação, prevenção de duplicidade, duas urnas, recuperação, impressão simulada, teclado e migração. **15 testes JavaScript passaram**, incluindo Delete corrigindo a escolha e Backspace sem essa função no padrão.

Os novos testes do driver Windows recompõem os pedaços de todas as páginas e comparam cada pixel com o desenho original completo de zerésima e boletim. Também conferem os limites das páginas, avanço e ausência da impressão antiga como texto simples. Isso não equivale a imprimir no equipamento físico.

O workflow Windows gera o instalador, instala suas duas funções em ambiente descartável, executa autotestes sem Python externo no PATH e testa o primeiro uso do servidor HTTPS. Consulte a execução vinculada ao commit que será instalado; não reutilize artefatos 2.3.0.

## Uso

Baixe **Instalador-Urna-Escolar-2.4.0**, extraia o ZIP e execute `Instalar_Urna_Escolar_2.4.0.exe` em ambos os computadores. Atualize antes de lacrar; o instalador bloqueia atualização durante eleição lacrada ou aberta. Confira a versão na Central e na Urna após instalar.

Na Urna, escolha a impressora, papel 80 mm e modo Windows ou ESC/POS compatível. Mantenha Atkinson Hyperlegible Regular/Bold instalada. Repita a calibração e faça uma eleição fictícia completa: zerésima, voto em chapa, branco, correção com Delete, encerramento e boletim. No driver Windows, aumente a altura do formulário se quiser menos quebras de página.

## Limites

Impressora física, guilhotina, som, teclado físico e rede entre dois PCs da escola precisam de ensaio presencial. Os testes automatizados usam dados fictícios isolados e drivers simulados. Eles não garantem ausência absoluta de falhas ou imunidade a fraude. Os dados de teste não são carregados na eleição real.
