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
UninstallDisplayIcon={app}\Aplicativo\UrnaEscolar.exe

[Languages]
Name: "portuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Dirs]
Name: "{commonappdata}\UrnaEscolar"; Permissions: users-modify
Name: "{commonappdata}\UrnaEscolar\logs"; Permissions: users-modify
Name: "{commonappdata}\UrnaEscolar\Servidor"; Permissions: users-modify; Check: IsCentral

[Files]
Source: "..\dist\UrnaEscolar\*"; DestDir: "{app}\Aplicativo"; Flags: recursesubdirs ignoreversion
Source: "..\dist\UrnaEscolarServidor\*"; DestDir: "{app}\Servidor"; Flags: recursesubdirs ignoreversion; Check: IsCentral
Source: "..\dist\VerificarAtualizacao.exe"; Flags: dontcopy
Source: "..\docs\GUIA_2.3.0.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{group}\Assistente de Configuração.lnk"
Type: files; Name: "{group}\Servidor da Urna Escolar.lnk"
Type: files; Name: "{group}\Mesa Eleitoral.lnk"
Type: files; Name: "{group}\Urna de Votação.lnk"
Type: files; Name: "{group}\Central da Eleição.lnk"

[Icons]
Name: "{group}\Central da Eleição"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--central"; Check: IsCentral
Name: "{commondesktop}\Central da Eleição"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--central"; Check: IsCentral
Name: "{group}\Urna de Votação"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--urna"; Check: IsUrna
Name: "{commondesktop}\Urna de Votação"; Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Parameters: "--urna"; Check: IsUrna

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "UrnaEscolarServidor"; Flags: deletevalue
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueName: "UrnaEscolarPrintAgent"; Flags: deletevalue
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "UrnaEscolar"; ValueData: """{app}\Aplicativo\UrnaEscolar.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\Aplicativo\UrnaEscolar.exe"; Description: "Abrir Urna Eletrônica Escolar"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Servidor 8443"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Descoberta"""; Flags: runhidden waituntilterminated
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""Urna Escolar - Aplicativo"""; Flags: runhidden waituntilterminated

[Code]
var
  RolePage: TInputOptionWizardPage;

function IsCentral: Boolean;
begin
  Result := RolePage.SelectedValueIndex = 0;
end;

function IsUrna: Boolean;
begin
  Result := not IsCentral;
end;

procedure InitializeWizard;
var RequestedRole: String;
begin
  RolePage := CreateInputOptionPage(wpWelcome, 'Como este computador será utilizado?', 'Use o mesmo instalador nos dois computadores.', 'No computador da mesa, escolha Central. No computador conectado à impressora, escolha Urna.', True, False);
  RolePage.Add('Central da Eleição + Mesa Eleitoral (computador 1)');
  RolePage.Add('Urna de votação + impressora USB (computador 2)');
  RequestedRole := ExpandConstant('{param:ROLE|central}');
  if RequestedRole = 'urna' then RolePage.SelectedValueIndex := 1 else RolePage.SelectedValueIndex := 0;
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
    if IsCentral then Role := 'central' else Role := 'urna';
    SaveStringToFile(ExpandConstant('{commonappdata}\UrnaEscolar\role.json'), '{"role":"' + Role + '"}', False);
    FirewallCommand('delete rule name="Urna Escolar - Servidor 8443"', False);
    FirewallCommand('delete rule name="Urna Escolar - Descoberta"', False);
    FirewallCommand('delete rule name="Urna Escolar - Aplicativo"', False);
    if IsCentral then begin
      FirewallCommand('add rule name="Urna Escolar - Servidor 8443" dir=in action=allow protocol=TCP localport=8443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Servidor\UrnaEscolarServidor.exe') + '"', True);
      FirewallCommand('add rule name="Urna Escolar - Descoberta" dir=in action=allow protocol=UDP localport=38443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Servidor\UrnaEscolarServidor.exe') + '"', True);
    end else
      FirewallCommand('add rule name="Urna Escolar - Aplicativo" dir=in action=allow protocol=UDP remoteport=38443 remoteip=LocalSubnet profile=any program="' + ExpandConstant('{app}\Aplicativo\UrnaEscolar.exe') + '"', True);
  end;
end;
