; Installatore del Convertitore (Inno Setup 6)
; Per rigenerarlo: prima PyInstaller (cartella dist\Convertitore con ffmpeg.exe), poi
;   "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe" installatore.iss
; Il risultato e' installatore\Convertitore-Setup.exe (lo crea crea_versione.ps1)

#ifndef Versione
  #define Versione "1.0"
#endif

[Setup]
AppId={{6E1B6F2C-7A43-4C1B-9E0B-5D3A2C7F1E90}
AppName=Convertitore
AppVersion={#Versione}
AppPublisher=Francesco Pagone
DefaultDirName={localappdata}\Programs\Convertitore
DisableDirPage=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installatore
OutputBaseFilename=Convertitore-Setup
SetupIconFile=convertitore.ico
UninstallDisplayIcon={app}\Convertitore.exe
UninstallDisplayName=Convertitore
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
Name: "sfera"; Description: "Avvia la sfera insieme a Windows (trascini i file sopra e si apre la ruota)"
Name: "desktop"; Description: "Icona sul Desktop"

[Files]
Source: "dist\Convertitore\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\Convertitore"; Filename: "{app}\Convertitore.exe"
Name: "{userprograms}\Sfera del Convertitore"; Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"
Name: "{userdesktop}\Convertitore"; Filename: "{app}\Convertitore.exe"; Tasks: desktop
Name: "{usersendto}\Convertitore"; Filename: "{app}\Convertitore.exe"
Name: "{userstartup}\Convertitore sfera"; Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"; Tasks: sfera

[Run]
; voce "Converti..." nel tasto destro di Esplora file
Filename: "{app}\Convertitore.exe"; Parameters: "--registra"; Flags: runhidden waituntilterminated
Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"; Description: "Avvia subito la sfera"; Flags: nowait postinstall

[UninstallRun]
Filename: "{app}\Convertitore.exe"; Parameters: "--rimuovi"; Flags: runhidden waituntilterminated; RunOnceId: "RimuoviMenu"
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im Convertitore.exe"; Flags: runhidden waituntilterminated; RunOnceId: "ChiudiSfera"

[Code]
procedure ChiudiConvertitore();
var
  Codice: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Convertitore.exe', '', SW_HIDE, ewWaitUntilTerminated, Codice);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  ChiudiConvertitore();
  Result := '';
end;
