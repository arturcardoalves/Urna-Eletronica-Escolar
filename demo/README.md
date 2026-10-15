# Urna Escolar — teste fictício independente

O arquivo está em `release-output/demo/UrnaEscolar_Teste.exe`. Abra-o diretamente no Windows: não precisa instalar Python nem abrir a Central. Não acessa banco, senhas, chaves ou dados da eleição real. Não transmite documentos ao portal. Os votos fictícios ficam somente em memória e desaparecem ao fechar.

1. Clique **Testar teclado**. Uma janela mostra o desenho do teclado e do teclado numérico. Pressione as teclas físicas: amarelo enquanto pressionadas, verde após soltar. O painel indica a tecla recebida e as funções **B = BRANCO**, **Delete = CORRIGE**, **Enter = CONFIRMA**. Clique no desenho para simular uma tecla (azul); isso não valida o hardware. **Limpar teste do teclado** reinicia os indicadores. Este painel não registra votos.
2. Na tela principal, selecione a impressora e o modo. **Windows** usa o driver instalado (inclusive Microsoft Print to PDF). **ESC/POS** exige impressora térmica compatível. Ajuste o avanço antes do corte entre 10 e 80 mm (padrão 30).
3. Imprima **Zerésima** antes de votar. Mostra todas as chapas e brancos zerados. Depois de votar, use **Zerar teste** para emitir outra zerésima.
4. Use **Imprimir voto BRANCO** e **Imprimir voto CHAPA 10** para testar apenas as fichas de papel. Esses dois botões não acrescentam votos ao boletim.
5. Para testar o fluxo completo e a contagem, escolha voto por **Mouse** ou **Teclado**, selecione/digite chapa 10, 20 ou 30 (ou B para branco), corrija com Delete se necessário e confirme com Enter ou CONFIRMA. O som toca ao confirmar. Marque **Imprimir cada voto** para imprimir nesse fluxo.
6. Imprima **Boletim** para conferir os votos registrados nesta sessão. As fichas de calibração do item 4 não entram nessa contagem. O teste comporta 100 votos fictícios; depois use Zerar teste.
7. **Reimprimir último** repete os mesmos dados, sem acrescentar voto. Confira fila e papel antes de repetir.

Todos os documentos trazem **TESTE FICTÍCIO — SEM VALIDADE ELEITORAL**. O módulo de impressão e o MP3 são os do projeto. Sem Atkinson instalada, o raster usa Segoe UI; o teste não instala fontes. O aplicativo confirma o envio ao driver, não a saída física do papel.

## Gerar novamente

Após preparar o ambiente de compilação do projeto:

```powershell
.\installer\BUILD_TESTE.ps1
```

O GitHub Actions também gera um artefato separado **Urna-Escolar-Teste-Ficticio**. O teste não é incluído na instalação de uma eleição real.

## Versão 2.4.0

A demonstração usa os mesmos documentos gráficos do sistema oficial, sem QR Codes. O teste de teclado usa Delete para CORRIGE. Os testes de impressão automatizados usam driver simulado; confira o papel, o som e o teclado físico nos equipamentos da escola.
