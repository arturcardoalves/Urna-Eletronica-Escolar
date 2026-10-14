# Dúvidas do dia a dia

[← Página do projeto](../README.md) · [Guia de instalação](GUIA_2.3.0.md)

## Preciso de internet para votar?

Depois de instalar o programa, Edge, fontes e driver, não. Central e Urna precisam se comunicar pela rede local. O aviso “Sem internet” do Windows não significa, por si só, que a rede local parou.

## Basta ligar os cabos? Preciso configurar o roteador?

Normalmente basta conectar os dois PCs às portas LAN do mesmo roteador, se ele já estiver com DHCP ativo e permitir comunicação entre os clientes. Redes de convidados, isolamento de clientes e regras da escola podem exigir ajuste pela TI. A documentação não presume que qualquer rede esteja pronta.

Não é preciso fixar o IP no cenário padrão. Um cabo direto entre dois computadores, sem roteador, não é o mesmo cenário.

## Qual endereço abre a administração?

Prefira **Abrir administração**, no aplicativo da Central. O primeiro ADMIN deve ser criado nesse computador, pelo endereço local. Um IP de rede não serve para o primeiro cadastro. Depois da configuração, o acesso depende de o servidor estar ativo e do vínculo/certificado correto.

Se aparecer “Origem da requisição não permitida”, reabra pelo aplicativo e confira se está usando a versão atual. Não misture páginas antigas com endereços HTTP/HTTPS diferentes. Não desligue a validação de origem para contornar o erro. Persistindo, registre a versão e a mensagem para diagnóstico.

## Existe senha padrão?

Não há uma senha ADMIN universal na distribuição. A pessoa responsável cria o primeiro usuário na Central. A senha precisa ter ao menos 10 caracteres. Contas fictícias usadas pelos testes do código não são cadastradas automaticamente na instalação real.

## Posso cadastrar só nome e turma?

Sim. Matrícula e turno são opcionais. Sem matrícula, o sistema gera um código interno; sem turno, usa “Não informado”. CSV: colunas `Nome,Turma`. XLSX: cada aba representa uma turma e basta a coluna `Nome`.

A mesma combinação de nome/turma gera o mesmo código, ajudando a evitar duplicações na reimportação. Homônimos na mesma turma precisam de códigos distintos informados manualmente. Se você mudar nome ou turma, revise possíveis registros duplicados antes de lacrar.

## O som está sempre ligado?

O sistema sempre tenta tocar o som de conclusão. O Windows pode estar mudo, o alto-falante desconectado ou o navegador pode restringir áudio. Teste no computador da cabine antes da eleição.

## O voto não foi impresso. Ele foi perdido?

Uma falha de impressão após o registro não apaga o voto. A Mesa deve resolver a pendência e, se necessário, autorizar reimpressão. Não libere outro voto para compensar e não reinicie a eleição para tentar recuperar uma ficha.

Se a rede caiu antes da confirmação, aguarde a verificação do estado. A tela tenta descobrir se o voto foi registrado. Não presuma nem que houve registro nem que deve votar novamente.

## O texto ou a assinatura foi cortado. O que ajusto?

No aplicativo da Urna, aumente **Espaço em branco antes do corte**. O padrão é 30 mm, ajustável entre 10 e 80 mm. Repita o teste completo e confira as duas amostras. O ajuste vale para as impressões seguintes daquele computador. Driver, tamanho de papel e compatibilidade ESC/POS também precisam estar corretos.

## O modo quiosque impede qualquer acesso ao computador?

Não. Ele oculta os controles do navegador, mas não é uma proteção completa do Windows. Use supervisão da cabine e uma conta comum. F11 alterna tela cheia; Alt+F4 fecha a janela da cabine. A Central deve continuar aberta durante a operação.

## Posso ensaiar com um computador só?

O mini executável em `demo/` permite testar interação com dados fictícios, som e impressão, separado da eleição real. Isso não valida o vínculo entre Central e Urna, o servidor completo nem a rede de dois computadores. Para aprovar o uso real, ensaie com os dois PCs e a impressora final.

## O que são Logs-instalacao no GitHub?

São registros das etapas de compilação e teste. Ajudam a entender por que um build falhou; não são o instalador. Para instalar, baixe o artefato **Instalador-Urna-Escolar-2.3.0** de uma execução bem-sucedida.

## Como começo de novo depois do teste?

**Iniciar nova eleição** preserva usuários e vínculos e arquiva a eleição anterior. **Reset completo** apaga também dados, acessos, certificados e configurações. Consulte [o guia de reset](RESETAR_SISTEMA.md) antes de executar os BAT e preserve qualquer dado importante fora do pacote.

## Posso atualizar durante a votação?

Não. A atualização é bloqueada enquanto a eleição estiver lacrada ou aberta. Planeje atualizações antes da preparação final. Alterações no código e nos arquivos podem invalidar a conferência de integridade de uma eleição lacrada.

## QR code prova que o boletim é autêntico?

Um QR de texto antigo, por si só, não comprova autenticidade. Com a publicação habilitada antes da lacração, há QR de consulta e QR com resumo Ed25519 assinado. Compare a impressão digital da chave com a referência da comissão e confira os valores do manifesto/PDF com o papel. [Como verificar](PROTOCOLO_PUBLICACAO.md).

## O portal exige internet na urna?

Não. A Central assina e exporta para um pendrive. Outro computador com internet usa o Transmissor Eleitoral para enviar ao portal. A votação continua offline se o site estiver indisponível. [Operação](PUBLICACAO_E_PORTAL.md) e [Cloudflare gratuito](PORTAL_CLOUDFLARE.md).
