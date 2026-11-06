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

ShowLanguageDialog=no
LanguageDetectionMethod=uilanguage

[Languages]
; lingua scelta in automatico da quella di Windows (italiano, altrimenti inglese)
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "italiano"; MessagesFile: "compiler:Languages\Italian.isl"

[CustomMessages]
italiano.TaskSfera=Avvia la sfera insieme a Windows (trascini i file sopra e si apre la ruota)
english.TaskSfera=Start the orb with Windows (drop files on it and the wheel opens)
italiano.TaskDesktop=Icona sul Desktop
english.TaskDesktop=Desktop icon
italiano.NomeSfera=Sfera del Convertitore
english.NomeSfera=Converter orb
italiano.AvviaSfera=Avvia subito la sfera
english.AvviaSfera=Start the orb now

[Tasks]
Name: "sfera"; Description: "{cm:TaskSfera}"
Name: "desktop"; Description: "{cm:TaskDesktop}"

[Files]
Source: "dist\Convertitore\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{userprograms}\Convertitore"; Filename: "{app}\Convertitore.exe"
Name: "{userprograms}\{cm:NomeSfera}"; Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"
Name: "{userdesktop}\Convertitore"; Filename: "{app}\Convertitore.exe"; Tasks: desktop
Name: "{usersendto}\Convertitore"; Filename: "{app}\Convertitore.exe"
Name: "{userstartup}\Convertitore sfera"; Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"; Tasks: sfera

[Run]
; voce "Converti..." nel tasto destro di Esplora file
Filename: "{app}\Convertitore.exe"; Parameters: "--registra"; Flags: runhidden waituntilterminated
Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"; Description: "{cm:AvviaSfera}"; Flags: nowait postinstall

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
