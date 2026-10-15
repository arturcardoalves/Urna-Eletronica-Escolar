# Segurança e privacidade

[← Página do projeto](README.md) · [Roteiro de teste](docs/TESTES_E_VALIDACAO.md)

A Urna Eletrônica Escolar é um projeto para eleições estudantis em rede local. Os controles abaixo estão presentes no código, mas não equivalem a certificação independente, proteção de hardware eleitoral ou garantia de sigilo absoluto.

## Contas e permissões

- O primeiro ADMIN é criado no computador da Central, por acesso local. A distribuição não cadastra uma senha administrativa universal.
- Senhas têm mínimo de 10 caracteres e são armazenadas com hash Argon2, não como texto de senha.
- ADMIN e MESÁRIO possuem papéis distintos. As rotas aplicam autenticação e permissões no servidor; ocultar um botão não é a única restrição.
- Sessões têm expiração. Cookies usam HttpOnly e SameSite estrito; no acesso HTTPS, também usam Secure.
- Requisições de alteração recebidas pelo navegador passam por verificação de origem. Uma rejeição de origem não deve ser resolvida desativando essa proteção.

Referências: [autenticação](URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/auth.py), [senhas e criptografia](URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/security.py), [rotas e primeiro uso](URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/main.py).

## Comunicação entre os computadores

A Central usa HTTPS em **TCP 8443**; a descoberta usa **UDP 38443**. A instalação gera seus próprios certificados e chaves. Anúncios na rede ajudam a localizar a Central, mas não comprovam sua identidade: o vínculo exige aprovação e comparação de código nos dois computadores.

O instalador limita as regras de entrada à sub-rede local, nos perfis de rede do Windows. Isso não impede acesso por alguém que já esteja nessa mesma rede. Use uma rede dedicada, supervisione os equipamentos e não exponha a Central à internet.

A credencial da Urna é protegida pelo Windows para a conta local que a usa. Essa proteção não torna seguro um computador comprometido por malware ou controlado por um administrador mal-intencionado.

## Registro do voto e repetição

No fluxo com identificação, a Mesa libera o aluno. A autorização é vinculada à Urna e consumida no registro; o estado do eleitor é atualizado na mesma operação transacional. Repetir uma autorização usada não deve criar um segundo voto.

**No modo sem identificação, não há controle de uma participação por pessoa.** A aplicação pode impedir repetição da mesma solicitação, mas não reconhecer uma pessoa que inicia outra sessão. A eleição que precisa desse controle deve usar cadastro nominal e liberação pela Mesa.

Lacração, verificação de integridade e hashes ajudam a detectar alterações nos elementos verificados. Um hash precisa de uma referência confiável para comparação; alguém que controle todos os arquivos, chaves e registros pode comprometer essas evidências.

Referência: [regras eleitorais](URNA_ESCOLAR_SOURCE/01_SERVIDOR_ADMIN/app/services.py).

## Sigilo: o que é separado e o que exige cuidado

O registro do voto não contém nome, matrícula ou horário do eleitor. A escolha é criptografada, e a posição de exportação/recontagem é aleatória. Os registros de comparecimento são separados da escolha.

Isso reduz a associação direta, mas não elimina toda possibilidade de correlação. Observação da cabine, ordem de atendimento, metadados operacionais, snapshots do banco e acesso ao processo de impressão podem revelar informações. A infraestrutura de impressão do Windows e a memória dos processos também fazem parte do ambiente a proteger.

O aplicativo de impressão mantém um diário com identificadores opacos e estados, sem salvar a escolha ou horários nesse diário. **Isso não é uma promessa de ausência de dados em toda a fila/driver da impressora.** Controle o acesso ao computador, aos papéis, às cópias parciais e aos backups.

A ficha física não deve ser usada como comprovante pessoal da escolha: siga a orientação de dobrar e depositar na urna física da eleição, com o procedimento definido pela comissão.

## Falha de impressão

O registro digital e a saída do papel são etapas diferentes. Se o registro já ocorreu, uma falha da impressora não o desfaz. A Urna mantém a pendência e a Mesa resolve a situação.

Um trabalho de resultado incerto não é repetido automaticamente. A reimpressão precisa de intervenção autorizada; confira se a primeira ficha saiu total ou parcialmente antes de continuar. O aceite do trabalho pelo driver não comprova entrega física do papel.

Referência: [diário e execução nativa](installer/native_runtime.py).

## Dados, backups e atualização

| Local no Windows | Conteúdo |
|---|---|
| `C:\ProgramData\UrnaEscolar\Servidor` | Banco da eleição, certificados, chaves e arquivos associados. |
| `%LOCALAPPDATA%\UrnaEscolar` | Configuração da conta, vínculo e diário local de impressão. |
| `C:\ProgramData\UrnaEscolar\logs` | Registros operacionais do aplicativo. |

Backups contêm material sensível, inclusive hashes de senha e chaves. Guarde-os fora do GitHub e restrinja o acesso. Não publique bancos, certificados privados, credenciais, uploads de eleições ou logs sem revisão.

O `.gitignore` reduz envios acidentais, mas não remove arquivos já rastreados. O pacote de fontes aplica uma lista de arquivos permitidos e verifica hashes. Atualizações são bloqueadas com eleição lacrada/aberta; o procedimento de atualização preserva dados com backup. Não altere manualmente os arquivos da aplicação durante uma eleição lacrada.

## Antes de usar em uma eleição

Faça um [ensaio completo](docs/TESTES_E_VALIDACAO.md) nos equipamentos finais. Separe acessos administrativos e de operação, mantenha supervisão e confira documentos e totais. Modo quiosque facilita a cabine, mas não bloqueia todo o sistema operacional.

## Como relatar um problema

Para dúvidas gerais, use as [Issues](https://github.com/arturcardoalves/Urna-Eletronica-Escolar/issues) com versão, passos e mensagens já revisadas. Não publique dados de alunos, senhas, tokens, banco ou chaves. Se a falha revelar acesso indevido ou material sensível, procure um canal privado com o responsável antes de expor detalhes exploráveis.

Não há, nesta documentação, alegação de auditoria independente ou de invulnerabilidade. Resultados executados, simulações e testes presenciais pendentes estão separados em [Testes e validação](docs/TESTES_E_VALIDACAO.md).
