# Urna Eletrônica Escolar 2.3.0 — instalação unificada

## O arquivo que você usa

Use o mesmo **Instalar_Urna_Escolar_2.3.0.exe** nos dois computadores Windows 10/11 de 64 bits. O programa inclui seu próprio runtime; não usa o Python instalado no computador e não pede pip nem terminal. A instalação requer uma conta com permissão de administrador. O uso diário é pela conta normal do Windows.

Antes de desconectar a internet, instale Microsoft Edge, a fonte **Atkinson Hyperlegible Regular e Bold** nos dois PCs e o driver da impressora **apenas no PC da urna**. Confira data e hora. Atualize somente com a eleição em configuração ou encerrada; a atualização faz backup e bloqueia eleições lacradas/abertas.

## Ligue os equipamentos

Conecte os dois PCs por cabo às portas **LAN** do mesmo roteador. Deixe a porta WAN sem conexão à internet. Desative o Wi-Fi do roteador e dos PCs. O aplicativo não desliga esses rádios: essa preparação é feita no equipamento. Mantenha DHCP habilitado no roteador. Não use rede de convidados nem isolamento entre clientes.

## Computador 1 — Central + Mesa

1. Execute o instalador e escolha **Central da Eleição + Mesa Eleitoral**.
2. Abra a Central pelo atalho. Aguarde **Servidor ativo — HTTPS verificado**.
3. Clique **Abrir administração**. Na primeira vez, crie o administrador; depois entre com sua senha.
4. Prepare os dados da eleição, as chapas, os eleitores e um usuário **MESÁRIO**. Ainda não lacre a eleição.
5. Na Central, clique **Conectar computador da urna**. Entre como administrador, se necessário, e clique **Permitir conexão por 5 minutos**.

Para a Mesa Eleitoral, a Central oferece três formas de abertura: **Normal**, **Tela cheia** e **Modo quiosque**. O modo normal mostra toda a interface do navegador. Tela cheia pode ser alternada com **F11**. O modo quiosque esconde os controles do navegador e é o recomendado no dia da eleição; use **Alt+F4** para fechá-lo.

Não há seleção de impressora no computador da mesa. Mantenha a janela da Central aberta ou minimizada. Ela controla o servidor; o fechamento pede confirmação, e o sistema recusa o desligamento normal enquanto a votação estiver aberta. Se o Windows ou o processo encerrar inesperadamente, a urna perderá a conexão e bloqueará o uso até a recuperação.

## Computador 2 — Urna de votação

1. Execute **o mesmo instalador** e escolha **Urna de votação + impressora USB**.
2. Abra o aplicativo **Urna de Votação** e clique **Procurar Central**.
3. Compare o código mostrado nos dois PCs. Na Central, aprove somente se for igual. Na urna, clique **Códigos iguais — concluir conexão**.
4. Selecione a impressora USB instalada no Windows. Comece por **Driver Windows**. Use ESC/POS somente se o modelo e o driver forem compatíveis e o teste sair correto.
5. Em **Espaço em branco antes do corte**, comece com **30 mm**. O ajuste aceita de 10 a 80 mm e será aplicado à ficha de voto, zerésima, boletim de urna e demais impressões desse computador.
6. Clique **Imprimir teste completo de ficha, assinaturas e corte**. O sistema imprime duas amostras. Confirme apenas se a ficha, as três assinaturas e a área em branco saírem completas, com o corte depois do conteúdo.
7. Aguarde **Servidor conectado — HTTPS verificado** e escolha **Normal**, **Tela cheia** ou **Modo quiosque** na seção **Abrir Urna de Votação**. O modo quiosque é o recomendado no dia da eleição; use **Alt+F4** para retornar ao aplicativo.

A confirmação de impressão deve ser repetida depois de reiniciar o aplicativo ou mudar a impressora, o modo ou o espaço antes do corte. Se o texto ainda ficar perto da lâmina, aumente o valor em 5 mm e repita as duas amostras. Um driver pode informar “disponível” mesmo sem papel; o teste físico continua necessário. Não selecione impressoras PDF ou virtuais.

## Abra e encerre uma eleição de teste

1. Conecte a urna e confira a impressora antes de lacrar.
2. No Administrador, confira os cadastros e lacre a eleição.
3. Na Central, abra **Mesa Eleitoral**. Use o usuário MESÁRIO; a janela da Mesa mantém seu próprio acesso separado da Administração.
4. Inicie o procedimento de abertura, confira a zerésima impressa **na urna**, e confirme a abertura na Mesa.
5. Autorize os eleitores pela Mesa. Na cabine, confira a chapa e confirme o voto.
6. No encerramento, confira o BU impresso na mesma impressora. Os relatórios PDF ficam disponíveis no sistema.

## Se algo falhar

- **Central não encontrada:** mantenha a Central aberta, habilite o vínculo por cinco minutos, confira cabos, mesma rede, data/hora e aviso de firewall. Use Procurar Central novamente. Se houver duas Centrais, feche a que não será utilizada.
- **Conexão caiu:** o aplicativo tenta reencontrar a Central já vinculada. Se o IP mudar enquanto a cabine está aberta, a janela avisa; use Alt+F4 e Iniciar urna novamente. Não confirme outro voto enquanto a verificação estiver pendente.
- **Texto foi cortado:** aumente o espaço antes do corte na Urna, repita o teste completo e confirme somente quando a ficha e as três assinaturas saírem inteiras. A mudança passa a valer para todas as impressões seguintes.
- **Impressão não saiu:** confira papel, cabo e driver. Informe o problema ao mesário; somente ele autoriza a reimpressão. Confira e recolha qualquer cópia parcial ou duplicada antes de continuar.
- **Computador reiniciou durante a impressão:** um trabalho de resultado incerto não é impresso novamente por conta própria. Resolva pela Mesa. O diário de impressão impede repetição automática da mesma solicitação.
- **Fonte ausente:** instale as duas variantes na conta usada para executar o programa e abra novamente.
- **Servidor não inicia:** consulte Diagnóstico. Verifique se a versão antiga ainda está aberta. Não apague a pasta de dados para tentar resolver.
- **Aviso ao executar o instalador:** esta distribuição ainda não possui assinatura comercial de código. Não desative o antivírus; confira a procedência do arquivo e use a análise do Windows.

## Rotina diária

Ligar roteador e PCs → abrir Central e Urna → conferir conexão → testar o papel → abrir Mesa → realizar o procedimento eleitoral. Depois do primeiro vínculo, não há arquivo de configuração para copiar, IP para digitar ou certificado para escolher.

O programa usa arquivos internos instalados automaticamente. “Um arquivo” significa um único instalador entregue a você, não ausência de arquivos internos no Windows.

## Depois de uma eleição de teste

Se quiser iniciar outra eleição e manter os usuários, senhas, vínculo da Urna e impressora, encerre a votação e use **Administrador → Histórico → Iniciar nova eleição**. Para apagar também senhas, certificados, vínculos e configurações locais, siga [RESETAR_SISTEMA.md](RESETAR_SISTEMA.md). Feche a Central e a Urna antes de executar o reset completo.

## Limites da validação

Os testes automatizados verificam lógica, vínculo, transações, recuperação e empacotamento quando executados no Windows. Não comprovam o driver da Epson, o corte, falta de papel, desempenho dos PCs da escola nem a descoberta no roteador real. Antes da eleição oficial, faça uma eleição completa de teste nos dois equipamentos. Consulte REVISAO_CODIGO.md para os resultados efetivamente obtidos nesta entrega.
