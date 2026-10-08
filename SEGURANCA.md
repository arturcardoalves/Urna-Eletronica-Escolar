# Segurança — Urna Eletrônica Escolar 2.3.0

Projeto destinado a eleições escolares em rede local isolada. Não oferece as garantias de hardware de uma urna oficial.

O servidor usa HTTPS na porta TCP 8443; a descoberta usa UDP 38443. Anúncios de rede não são prova de identidade: a vinculação exige aprovação administrativa e comparação do código ligado ao certificado nos dois PCs. As regras de firewall do instalador limitam a entrada à sub-rede local, em qualquer perfil do Windows.

A versão unificada imprime pelo aplicativo nativo da urna e não inicia um servidor HTTP de impressão separado. Banco, certificados e chaves ficam em C:\ProgramData\UrnaEscolar\Servidor. Configuração e diário local ficam em %LOCALAPPDATA%\UrnaEscolar. A credencial da urna usa a proteção de dados do Windows para o usuário atual.

O voto não contém nome nem matrícula. O diário de impressão guarda IDs opacos e estados, sem escolhas ou horários. Impressão interrompida exige intervenção do mesário e não se repete automaticamente.

Hashes e cadeias de auditoria ajudam a detectar alterações; uma pessoa com controle administrativo total dos computadores pode comprometer o sistema. Controle físico, acesso restrito e guarda externa dos comprovantes continuam necessários.

Não envie bancos, chaves, certificados, credenciais ou dados de uma eleição ao GitHub. O .gitignore cobre os diretórios conhecidos. O teste do servidor durante a compilação usa test-results/runtime; instalação automática é restrita ao runner do GitHub.

Antes da eleição, teste os dois equipamentos, rede, fonte, impressão, corte, falta de papel e recuperação. Não atualize com eleição lacrada ou aberta.
