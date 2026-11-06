# Crea (e se vuoi pubblica) una nuova versione del Convertitore.
#
#   1. cambia il numero in versione.py   (es. VERSIONE = "1.1")
#   2. powershell -File crea_versione.ps1 -Note "cosa cambia"            -> crea solo i file
#      powershell -File crea_versione.ps1 -Note "cosa cambia" -Pubblica  -> li mette anche su GitHub
#
#   -Completo : l'aggiornamento automatico usa il Setup intero invece del pacchetto piccolo.
#               Serve solo se cambiano le librerie (nuovi import, nuova versione di Python, ffmpeg...).
#
# Risultato nella cartella installatore\:
#   Convertitore-Setup.exe          installazione completa, da dare a chi non ce l'ha
#   Convertitore-Aggiornamento.exe  solo il programma (pochi MB), lo scarica la sfera
#   versione.json                   dice alla sfera qual e' l'ultima versione

param([string]$Note = "", [switch]$Pubblica, [switch]$Completo)
$ErrorActionPreference = "Stop"
$qui = $PSScriptRoot
Set-Location $qui
$py = "$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe"
$iscc = "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
$lavoro = Join-Path $env:TEMP "convertitore-build"

$v = (Select-String -Path "$qui\versione.py" -Pattern 'VERSIONE = "([0-9.]+)"').Matches[0].Groups[1].Value
Write-Host "== Convertitore $v =="

# 1. programma (Convertitore.exe + librerie)
& $py -m PyInstaller "$qui\app.py" --name Convertitore --noconfirm --windowed --onedir --log-level WARN `
    --icon "$qui\convertitore.ico" --add-data "$qui\convertitore.ico;." `
    --collect-all tkinterdnd2 --collect-all pillow_heif `
    --hidden-import win32com.client --hidden-import pythoncom --hidden-import aggiornamento --hidden-import pdf2docx --exclude-module fire `
    --distpath "$qui\dist" --workpath "$lavoro\work" --specpath "$lavoro"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller non e' riuscito" }
Copy-Item (Get-Command ffmpeg).Source "$qui\dist\Convertitore\ffmpeg.exe" -Force

# 2. installatori
& $iscc /Q "/DVersione=$v" "$qui\installatore.iss"; if ($LASTEXITCODE -ne 0) { throw "Setup non creato" }
& $iscc /Q "/DVersione=$v" "$qui\aggiornamento.iss"; if ($LASTEXITCODE -ne 0) { throw "Aggiornamento non creato" }

# 3. versione.json per la sfera
$file = if ($Completo) { "Convertitore-Setup.exe" } else { "Convertitore-Aggiornamento.exe" }
$sha = (Get-FileHash "$qui\installatore\$file" -Algorithm SHA256).Hash.ToLower()
$json = [ordered]@{ versione = $v; file = $file; sha256 = $sha; note = $Note } | ConvertTo-Json
[IO.File]::WriteAllText("$qui\installatore\versione.json", $json, (New-Object Text.UTF8Encoding $false))

Get-ChildItem "$qui\installatore" -Include "Convertitore-*.exe", "versione.json" -Recurse |
    ForEach-Object { "{0,-34} {1,8:N1} MB" -f $_.Name, ($_.Length / 1MB) }

# 4. pubblicazione su GitHub (la sfera scarica sempre dall'ultima release)
if ($Pubblica) {
    $testo = if ($Note) { $Note } else { "Convertitore $v" }
    $gh = (Get-Command gh -ErrorAction SilentlyContinue).Source
    if (-not $gh) { $gh = (Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\GitHub.cli_*\bin\gh.exe" | Select-Object -First 1).FullName }
    & $gh release create "v$v" "$qui\installatore\Convertitore-Setup.exe" "$qui\installatore\Convertitore-Aggiornamento.exe" `
        "$qui\installatore\versione.json" --repo torregiulia/convertitore --title "Convertitore $v" --notes $testo
    if ($LASTEXITCODE -ne 0) { throw "Pubblicazione su GitHub non riuscita" }
    Write-Host "Pubblicata: https://github.com/torregiulia/convertitore/releases/tag/v$v"
}
