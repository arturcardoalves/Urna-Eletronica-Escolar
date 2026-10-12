# Urna Escolar — demonstracao independente

Execute `UrnaEscolar_Teste.exe`. Nao precisa instalar Python nem abrir a Central. Nao acessa banco, rede, senhas ou dados da eleicao real. Os votos ficam somente na memoria e desaparecem ao fechar.

1. Use as chapas ficticias 10, 20 e 30, ou BRANCO.
2. Escolha voto por Mouse ou Teclado. No teclado: digite dois numeros; Enter confirma, Backspace corrige e B seleciona branco.
3. O som toca ao confirmar. O botao Testar som permite conferir o volume.
4. Para imprimir votos, selecione a impressora e marque Imprimir cada voto. Para zeresima e boletim, use os botoes especificos (eles imprimem mesmo com o checkbox desmarcado).
5. Use Windows para o driver instalado (inclusive Microsoft Print to PDF) ou ESC/POS somente para termica compativel. Margem antes do corte: 10 a 80 mm, padrao 30.
6. Imprima a zeresima antes de votar. O boletim mostra os votos da sessao de teste, sem encerrar o teste. Para recomecar, use Zerar teste.
7. Reimprimir ultimo repete somente o documento, sem aumentar o total de votos. Confira fila e papel antes de repetir.

Todos os documentos trazem TESTE FICTICIO / SEM VALIDADE ELEITORAL. O modulo de impressao e o MP3 sao os do projeto. Sem a fonte Atkinson instalada, o raster de demonstracao usa Segoe UI; nao instala fontes. O aplicativo confirma envio ao driver, nao a saida fisica do papel. Esta demonstracao nao testa autenticacao, sigilo, rede nem prevencao de voto duplicado de uma eleicao real.

## Gerar o EXE novamente

Na raiz do repositorio, com as dependencias de compilacao instaladas:

```powershell
.\.build-venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath release-output/demo --workpath build/demo demo/urna_demo.spec
```

O parametro `--self-test` valida contagem ficticia, documentos rasterizados e inicializacao do Tk sem enviar trabalhos a impressora ou tocar som.

Validacao da entrega: EXE compilado localmente no Windows, com 28.075.659 bytes. Autoteste do EXE retornou codigo 0 (contagem, rasterizacao de voto/zeresima/boletim e Tk). Teste separado de interface Tk oculta confirmou voto por mouse, teclado, branco, rejeicao de numero invalido e bloqueio durante trabalho. Audio foi simulado nesse teste; som nos alto-falantes e impressao fisica permanecem para verificacao no equipamento. Nenhum trabalho foi enviado a impressora durante a validacao automatica.
