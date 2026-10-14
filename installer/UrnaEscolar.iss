#define MyAppName "Urna Eletrônica Escolar"
#define MyAppVersion "2.3.0"

[Setup]
AppId={{30AC11E9-942E-47D7-9178-59B91F1478D2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=Projeto Urna Eletrônica Escolar
DefaultDirName={autopf}\Urna Escolar
DefaultGroupName=Urna Escolar
OutputDir=output
OutputBaseFilename=Instalar_Urna_Escolar_2.3.0
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
MinVersion=10.0
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayIcon={code:ApplicationIcon}

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Dirs]
Name: "{commonappdata}\UrnaEscolar"; Permissions: users-modify
Name: "{commonappdata}\UrnaEscolar\logs"; Permissions: users-modify; Check: IsVoting
Name: "{commonappdata}\UrnaEscolar\Servidor"; Permissions: users-modify; Check: IsCentral

[Files]
Source: "..\dist\UrnaEscolar\*"; DestDir: "{app}\Aplicativo"; Flags: recursesubdirs ignoreversion; Check: IsVoting
Source: "..\dist\UrnaEscolarServidor\*"; DestDir: "{app}\Servidor"; Flags: recursesubdirs ignoreversion; Check: IsCentral
Source: "..\dist\TransmissorEleitoral.exe"; DestDir: "{app}\Publicacao"; Flags: ignoreversion; Check: IsPublication
Source: "..\dist\VerificarAtualizacao.exe"; Flags: dontcopy
Source: "..\docs\GUIA_2.3.0.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\PUBLICACAO_E_PORTAL.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\PORTAL_CLOUDFLARE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\PROTOCOLO_PUBLICACAO.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\RESETAR_SISTEMA.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\REVISAO_CODIGO.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{group}\Assistente de Configuração.lnk"
Type: files; Name: "{group}\Servidor da Urna Escolar.lnk"
Type: files; Name: "{group}\Mesa Eleitoral.lnk"
Type: files; Name: "{group}\Urna de Votação.lnk"
Type: files; Name: "{group}\Central da Eleição.lnk"
Type: files; Name: "{group}\Publicação de Resultados.lnk"
Type: files; Name: "{commondesktop}\Central da Eleição.lnk"
Type: files; Name: "{commondesktop}\Urna de Votação.lnk"
Type: files; Name: "{commondesktop}\Publicação de Resultados.lnk"

[Icons]
Name: "{group}\Central da Eleição"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--central"; Check: IsCentral
Name: "{commondesktop}\Central da Eleição"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--central"; Check: IsCentral
Name: "{group}\Urna de Votação"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--urna"; Check: IsUrna
Name: "{commondesktop}\Urna de Votação"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--urna"; Check: IsUrna
Name: "{group}\Publicação de Resultados"; Filename: "{app}\Publicacao\TransmissorEleitoral.exe"; Check: IsPublication
Name: "{commondesktop}\Publicação de Resultados"; Filename: "{app}\Publicacao\TransmissorEleitoral.exe"; Check: IsPublication

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "UrnaEscolarServidor"; Flags: deletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "UrnaEscolarPrintAgent"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "UrnaEscolar"; ValueData: """{app}\Aplicativo\UrnaEscolar.exe"""; Flags: uninsdeletevalue; Check: IsVoting
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "UrnaEscolar"; Flags: deletevalue; Check: IsPublication

[Run]
Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Description: "Abrir Urna Eletrônica Escolar"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: IsVoting
Filename: "{app}\Publicacao\TransmissorEleitoral.exe"; Description: "Abrir Publicação de Resultados"; Flags: nowait postinstall skipifsilent runasoriginaluser; Check: IsPublication

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Servidor 8443"""; Flags: runhidden waituntilterminated; RunOnceId: "UrnaEscolarServidor8443"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Descoberta"""; Flags: runhidden waituntilterminated; RunOnceId: "UrnaEscolarDescoberta"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Aplicativo"""; Flags: runhidden waituntilterminated; RunOnceId: "UrnaEscolarAplicativo"

[Code]
var
  RolePage: TInputOptionWizardPage;

function IsCentral: Boolean;
begin
  Result := RolePage.SelectedValueIndex = 0;
end;

function IsUrna: Boolean;
begin
  Result := RolePage.SelectedValueIndex = 1;
end;

function IsPublication: Boolean;
begin
  Result := RolePage.SelectedValueIndex = 2;
end;

function IsVoting: Boolean;
begin
  Result := IsCentral or IsUrna;
end;

function ApplicationIcon(Param: String): String;
begin
  if IsPublication then Result := ExpandConstant('{app}\Publicacao\TransmissorEleitoral.exe')
  else Result := ExpandConstant('{app}\Aplicativo\UrnaEscolar.exe');
end;

procedure InitializeWizard;
var RequestedRole, DefaultRole: String; SavedRole: AnsiString;
begin
  RolePage := CreateInputOptionPage(wpWelcome, 'Como este computador será utilizado?', 'Escolha uma das três funções deste instalador.', 'Central: servidor, administração e mesa eleitoral. Urna: votação e impressora USB. Publicação: transmitir os pacotes do pendrive no computador com internet.', True, False);
  RolePage.Add('Central da Eleição + Mesa Eleitoral (computador 1)');
  RolePage.Add('Urna de votação + impressora USB (computador 2)');
  RolePage.Add('Publicação de resultados — Transmissor Eleitoral (computador com internet)');
  DefaultRole := 'central';
  if LoadStringFromFile(ExpandConstant('{commonappdata}\UrnaEscolar\role.json'), SavedRole) then
    if Pos('"publicacao"', String(SavedRole)) > 0 then DefaultRole := 'publicacao'
    else if Pos('"urna"', String(SavedRole)) > 0 then DefaultRole := 'urna';
  RequestedRole := ExpandConstant('{param:ROLE|' + DefaultRole + '}');
  if RequestedRole = 'publicacao' then RolePage.SelectedValueIndex := 2
  else if RequestedRole = 'urna' then RolePage.SelectedValueIndex := 1
  else RolePage.SelectedValueIndex := 0;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var ExitCode: Integer; MessageText: AnsiString;
begin
  Result := '';
  ExtractTemporaryFile('VerificarAtualizacao.exe');
  if not Exec(ExpandConstant('{tmp}\VerificarAtualizacao.exe'), '"' + ExpandConstant('{tmp}\upgrade-result.txt') + '"', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Result := 'Não foi possível verificar a instalação anterior. Nenhum arquivo foi substituído.'
  else if ExitCode <> 0 then begin
    if LoadStringFromFile(ExpandConstant('{tmp}\upgrade-result.txt'), MessageText) then Result := UTF8Decode(MessageText)
    else Result := 'Não foi possível criar o backup. Confira o espaço livre e as permissões.';
  end;
end;

procedure FirewallCommand(Parameters: String; Required: Boolean);
var ExitCode: Integer;
begin
  if not Exec(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall ' + Parameters, '', SW_HIDE, ewWaitUntilTerminated, ExitCode) or (ExitCode <> 0) then
    if Required then MsgBox('O Windows não permitiu configurar a rede local. Peça ao responsável pela rede para liberar o aplicativo Urna Escolar nas portas TCP 8443 e UDP 38443. O firewall continua ativado.', mbError, MB_OK);
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Role: String;
begin
  if CurStep = ssPostInstall then begin
    if IsCentral then Role := 'central'
    else if IsUrna then Role := 'urna'
    else Role := 'publicacao';
    SaveStringToFile(ExpandConstant('{commonappdata}\UrnaEscolar\role.json'), '{"role":"' + Role + '"}', False);
    FirewallCommand('delete rule name="Urna Escolar - Servidor 8443"', False);
    FirewallCommand('delete rule name="Urna Escolar - Descoberta"', False);
    FirewallCommand('delete rule name="Urna Escolar - Aplicativo"', False);
    if IsCentral then begin
      FirewallCommand('add rule name="Urna Escolar - Servidor 8443" dir=in action=allow protocol=TCP localport=8443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Servidor\UrnaEscolarServidor.exe') + '"', True);
      FirewallCommand('add rule name="Urna Escolar - Descoberta" dir=in action=allow protocol=UDP localport=38443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Servidor\UrnaEscolarServidor.exe') + '"', True);
    end else if IsUrna then
      FirewallCommand('add rule name="Urna Escolar - Aplicativo" dir=in action=allow protocol=UDP remoteport=38443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Aplicativo\UrnaEscolar.exe') + '"', True);
  end;
end;
