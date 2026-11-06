# Convertitore

Convertitore di file per Windows con una **ruota delle conversioni**: trascini un file e scegli il formato.

- **Sfera**: piccolo cerchio sempre a portata. Ci trascini sopra i file, oppure la clicchi con un file selezionato, e si apre la ruota.
- **Tasto destro → Converti…** su immagini, video, audio, PDF, Word, Excel e PowerPoint.
- **Aggiornamenti automatici**: la sfera controlla questa pagina Releases e si aggiorna da sola.

## Installazione

Scarica `Convertitore-Setup.exe` dall'[ultima versione](../../releases/latest) e aprilo.
Windows può mostrare "Windows ha protetto il PC": clicca **Ulteriori informazioni → Esegui comunque**.

Le conversioni Word/Excel/PowerPoint → PDF richiedono Microsoft Office installato.

## Nuova versione (per chi sviluppa)

1. Cambia il numero in `versione.py`.
2. `powershell -File crea_versione.ps1 -Note "cosa cambia" -Pubblica`

Lo script crea il Setup completo, il pacchetto di aggiornamento e `versione.json`, e li pubblica come nuova release.
Usa `-Completo` se sono cambiate le librerie: in quel caso l'aggiornamento automatico scarica il Setup intero.

Audio e video usano [FFmpeg](https://ffmpeg.org) (build di [gyan.dev](https://www.gyan.dev/ffmpeg/builds/), licenza GPL; i sorgenti sono disponibili su quei siti), incluso nell'installatore.
