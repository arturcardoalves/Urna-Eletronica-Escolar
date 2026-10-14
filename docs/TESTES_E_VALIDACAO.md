# Testes e validação

[← Página do projeto](../README.md) · [Revisão técnica](REVISAO_CODIGO.md)

## O que os resultados significam

**Automatizado:** código executado com entradas e verificações definidas. **Simulado:** alguma parte, como navegador, rede ou impressora, é substituída por uma resposta controlada. **Presencial:** verificação nos computadores e dispositivos que serão usados.

Uma simulação ajuda a encontrar falhas de lógica, mas não mede se o papel saiu, se o corte ficou correto ou se o roteador da escola permite a conexão.

## Registro desta revisão da documentação — 12/10/2026

**Entrega atual de publicação — 13/10/2026:** a suíte completa passou com **97 testes**, o Worker/D1 passou em três suítes locais, os executáveis e o instalador foram gerados, e o runtime/primeiro acesso foi conferido com Python externo fora do PATH. Veja as evidências, simulações e limitações no [relatório desta entrega](ENTREGA_PUBLICACAO_2026-10-13.md). O registro abaixo descreve a revisão anterior da documentação.

| Item | Resultado / evidência |
|---|---|
| JavaScript da interface | 14 testes aprovados, com `node --test tests/test_frontend.js`. |
| Cadastro de alunos | 6 testes aprovados, com `python tests/test_voter_registration.py`, banco em memória e dados fictícios. |
| Empacotador de fontes | 3 testes aprovados: exclusão de dados, rejeição de chave privada e inclusão apenas das capturas permitidas. Execução isolada do módulo de distribuição. |
| Documentação | Links e imagens locais verificados; a prévia HTML não foi conferida no navegador nesta sessão. A aparência exata no GitHub pode variar. |
| Pacote de fontes | ZIP relido e comparado ao manifesto SHA-256; presença das capturas e ausência de bancos, uploads eleitorais e resíduos de build verificadas. |
| Instalador Windows | Não foi recompilado nem reinstalado nesta revisão de documentação. Consulte a execução do commit no Actions. |
| Equipamento físico | Não houve impressão física, teste entre dois PCs ou ensaio de falta de energia nesta revisão. |

As capturas de votação foram feitas com os templates, CSS e JavaScript oficiais, respostas de API simuladas e nomes fictícios. Nenhuma eleição real foi usada para gerar as imagens.

## Onde estão os testes

| Arquivo | Área coberta |
|---|---|
| `tests/test_integration.py` | Fluxos do servidor, votação e consistência. |
| `tests/test_origin.py` | Verificação de origem das requisições. |
| `tests/test_voter_registration.py` | Cadastro/importação com matrícula opcional e duplicidades. |
| `tests/test_frontend.js` | Estado da interface, som, mensagens, impressão e recuperação simulada. |
| `tests/test_runtime.py` | Execução nativa e impressão. |
| `tests/test_tls.py` | Certificados e conexão TLS. |
| `tests/test_windows_delivery.py` | Entrega e execução Windows. |
| `tests/test_distribution.py` | Filtragem e integridade do pacote de código. |

O [workflow Windows](../.github/workflows/build-windows-installer.yml) chama o [script de build](../installer/BUILD_WINDOWS.ps1), que executa a suíte Python, gera os executáveis, verifica HTTPS e faz testes de inicialização/instalação no ambiente previsto. O resultado vale para aquela execução, não para todo instalador que tenha o número 2.3.0.

## Ensaio antes da eleição

Use dados fictícios. Registre data, versão/commit, computadores, modelo da impressora, driver, modo de impressão e margem.

- [ ] Instalar nos dois PCs e criar ADMIN e MESÁRIO no primeiro uso.
- [ ] Vincular Central e Urna, comparando os códigos exibidos.
- [ ] Confirmar comunicação com os PCs sem internet.
- [ ] Cadastrar/importar alunos e chapas e conferir a lista.
- [ ] Testar ficha, três assinaturas, margem e corte.
- [ ] Lacrar, emitir a zerésima e conferir que os totais são zero.
- [ ] Identificar/liberar um aluno pela Mesa e votar pelo mouse.
- [ ] Corrigir uma escolha antes de confirmar, votar em branco e testar teclado.
- [ ] Ouvir o som e conferir o papel de cada voto.
- [ ] Tentar liberar novamente o mesmo aluno e conferir o bloqueio.
- [ ] Ensaiar falta de papel e desconexão; resolver a pendência pela Mesa sem criar outro voto.
- [ ] Reiniciar em um teste controlado e conferir recuperação e consistência dos totais.
- [ ] Se forem usadas várias urnas, ensaiar operação simultânea.
- [ ] Encerrar, conferir BU e relatórios com os votos fictícios esperados.
- [ ] Preparar a eleição real usando o procedimento de nova eleição/reset adequado.

Pare o ensaio e corrija qualquer divergência antes de usar dados reais. Não provoque falhas para testar durante a eleição real.
