; Pacchetto di AGGIORNAMENTO del Convertitore (Inno Setup 6)
; Contiene solo Convertitore.exe (pochi MB): ffmpeg e librerie restano quelli gia' installati.
; Lo crea crea_versione.ps1; la sfera lo scarica da GitHub e lo installa in silenzio.

#ifndef Versione
  #define Versione "1.0"
#endif

[Setup]
AppId={{6E1B6F2C-7A43-4C1B-9E0B-5D3A2C7F1E90}
AppName=Convertitore
AppVersion={#Versione}
AppPublisher=Francesco Pagone
DefaultDirName={localappdata}\Programs\Convertitore
UsePreviousAppDir=yes
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableWelcomePage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
OutputDir=installatore
OutputBaseFilename=Convertitore-Aggiornamento
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

[Files]
Source: "dist\Convertitore\Convertitore.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\Convertitore.exe"; Parameters: "--registra"; Flags: runhidden waituntilterminated
; riaccende la sfera, che l'aggiornamento ha chiuso
Filename: "{app}\Convertitore.exe"; Parameters: "--sfera"; Flags: nowait

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  Codice: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im Convertitore.exe', '', SW_HIDE, ewWaitUntilTerminated, Codice);
  Sleep(800);
  Result := '';
end;
