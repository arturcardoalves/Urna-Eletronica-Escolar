# Subir o código e gerar o instalador

## Pelo site do GitHub

1. Crie ou abra o repositório desejado.
2. Envie o conteúdo desta pasta na raiz, sem uma subpasta envolvendo o projeto.
3. Confirme que `.github/workflows/build-windows-installer.yml` foi enviado. Essa pasta costuma ficar oculta no Explorador; o Git inclui ela normalmente.
4. Abra Actions → Build Windows Installer → Run workflow e selecione a branch enviada.
5. Aguarde a execução terminar. Se falhar, baixe Logs-instalacao-2.3.0.
6. Com todas as etapas aprovadas, baixe Instalador-Urna-Escolar-2.3.0 e extraia o EXE.

O GitHub compila com PowerShell em um Windows temporário. Não precisa compilar no seu computador para usar esse caminho.

## Enviar pelo PowerShell com Git

Abra o PowerShell nesta pasta. Para um repositório novo e vazio, substitua o endereço abaixo pelo endereço real:

```powershell
git init
git add .
git status --short
git commit -m "Revisao e limpeza da Urna Escolar 2.3.0"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/SEU_REPOSITORIO.git
git push -u origin main
```

Se o repositório já tem arquivos, clone-o primeiro e coloque esta versão no clone. Sobrepor arquivos não remove os antigos: confira a lista de remoções em REVISAO_CODIGO.md. Não use push forçado. Se origin já existe, confira `git remote -v` antes de alterar o endereço.

## Acionar e baixar com GitHub CLI

Opcional, com GitHub CLI instalado, dentro do repositório:

```powershell
gh auth login
gh workflow run build-windows-installer.yml --ref main
gh run list --workflow build-windows-installer.yml --limit 5
```

Copie o ID da execução recém-criada. Substitua 123456789 pelo ID real:

```powershell
gh run watch 123456789 --exit-status
gh run download 123456789 -n Instalador-Urna-Escolar-2.3.0 -D .\Instalador
Get-FileHash .\Instalador\Instalar_Urna_Escolar_2.3.0.exe -Algorithm SHA256
```

## Compilar localmente

Com Python 3.13 de 64 bits, Inno Setup 6 e Edge instalados:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\installer\BUILD_WINDOWS.ps1
```

Saída: installer/output/Instalar_Urna_Escolar_2.3.0.exe. O script para se houver erro. O teste de instalação automática dos dois papéis roda apenas no Windows descartável do GitHub. Testes físicos continuam necessários.
