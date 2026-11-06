"""Testi dell'interfaccia in italiano e in inglese.

Nel codice i testi sono scritti in italiano dentro t("..."); se la lingua e' l'inglese
t() restituisce la traduzione da EN. Lingua: quella scelta nelle Impostazioni,
oppure ("auto") quella di Windows: italiano se Windows e' in italiano, altrimenti inglese.
"""
import ctypes

_lingua = None


def lingua():
    global _lingua
    if _lingua is None:
        from impostazioni import leggi
        scelta = leggi().get("lingua", "auto")
        if scelta in ("it", "en"):
            _lingua = scelta
        else:
            try:
                _lingua = "it" if (ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF) == 0x10 else "en"
            except Exception:
                _lingua = "it"
    return _lingua


def t(testo, **valori):
    inglese = lingua() == "en"
    s = EN.get(testo, testo) if inglese else testo
    s = s.format(**valori) if valori else s
    if inglese and valori.get("n") == 1:  # singolare: "1 file", non "1 files"
        s = s.replace(" files", " file").replace(" errors", " error").replace(" conversions", " conversion")
    return s


EN = {
    # impostazioni
    "Impostazioni": "Settings",
    "Ogni scelta si salva subito.": "Every choice is saved right away.",
    "Dove salvo i file convertiti": "Where converted files go",
    "Accanto all'originale": "Next to the original",
    "In una cartella fissa…": "In a fixed folder…",
    "Se il file esiste già": "If the file already exists",
    "Crea una copia numerata": "Make a numbered copy",
    "Sostituiscilo": "Replace it",
    "Quanto alleggerire con LEGGERO": "How much LIGHTER shrinks",
    "Più alleggerisci, più si perde qualità.": "The smaller the file, the lower the quality.",
    "Poco": "A little",
    "Medio": "Medium",
    "Molto": "A lot",
    "Lingua": "Language",
    "Vale dalla prossima ruota che si apre.": "Applies from the next wheel you open.",
    "Come Windows": "Same as Windows",
    "Sfera": "Orb",
    "Parte con Windows": "Starts with Windows",
    "Solo quando la apro": "Only when I open it",
    "Chiudi": "Close",
}

EN.update({
    # errori
    "errore imprevisto (dettagli nel registro errori)": "unexpected error (details in the error log)",
    "file non trovato: è stato spostato o cancellato?": "file not found: was it moved or deleted?",
    "file in uso da un altro programma: chiudilo e riprova": "file in use by another program: close it and try again",
    "file troppo grande per la memoria del PC": "file too large for this PC's memory",
    "immagine danneggiata o di un tipo non riconosciuto": "damaged image or unknown type",
    "immagine troppo grande (oltre i limiti di sicurezza)": "image too large (over the safety limit)",
    "Office non è riuscito ad aprire il file (serve Microsoft Office installato)": "Office could not open the file (Microsoft Office must be installed)",
    "conversione audio/video non riuscita": "audio/video conversion failed",
    "spazio sul disco esaurito": "the disk is full",
    "è già leggero, non si riduce di più": "it's already light, it won't get any smaller",
    "PDF protetto da password: aprilo, togli la password e riprova": "password-protected PDF: open it, remove the password and try again",
    "manca ffmpeg: reinstalla il Convertitore": "ffmpeg is missing: reinstall the app",
    "questo video non contiene audio": "this video has no audio",
    "il file non contiene la traccia richiesta (per esempio un video senza audio)": "the file doesn't have the requested track (for example a video with no audio)",
    "file audio/video danneggiato o incompleto": "damaged or incomplete audio/video file",
    "impossibile scrivere il file: cartella protetta o file aperto": "can't write the file: protected folder or file open",
    "è già più piccola di 1920 px": "it's already smaller than 1920 px",
    "PDF danneggiato o non leggibile": "damaged or unreadable PDF",
    "Office non risponde: conversione interrotta dopo 3 minuti": "Office isn't responding: stopped after 3 minutes",
    # nomi dei file creati
    "Immagini unite": "Merged images",
    "PDF unito": "Merged PDF",
    " (ruotata)": " (rotated)",
    " (ruotato)": " (rotated)",
    " (leggera)": " (light)",
    " (leggero)": " (light)",
    " (quadrata)": " (square)",
    " (dritta)": " (straightened)",
    " - pagina {n}": " - page {n}",
    "Appunti": "Clipboard",
    "Immagine dagli appunti": "Clipboard image",
    # ruota
    "Cosa converti?": "What are you converting?",
    "scegli un tipo, oppure\ntrascina qui il file": "pick a type, or\ndrop the file here",
    "trascina qui\n{cosa}": "drop\n{cosa} here",
    "prima trascina qui\n{cosa}": "first drop\n{cosa} here",
    "clic qui per tornare": "click here to go back",
    "Trascina qui\ni tuoi file": "Drop your\nfiles here",
    "immagini · video · audio\nPDF · Word · Excel": "images · video · audio\nPDF · Word · Excel",
    "{n} file": "{n} files",
    "{n} non supportati, ignorati": "{n} unsupported, skipped",
    "scegli cosa convertire": "choose what to convert",
    "di tipi diversi": "of different types",
    "immagini e PDF": "images and PDFs",
    "scegli il formato": "choose the format",
    "Annullo…": "Cancelling…",
    "screenshot": "screenshot",
    "{n} file copiati": "{n} copied files",
    "Rilascia uno o più file per vedere le conversioni": "Drop one or more files to see the conversions",
    "Formato non supportato": "Unsupported format",
    "{n} file che non so convertire": "{n} files I can't convert",
    "Scegli un tipo  ·  Esc per annullare": "Pick a type  ·  Esc to cancel",
    "{n} conversioni possibili": "{n} possible conversions",
    "Clicca un formato  ·  Esc o tasto destro per annullare": "Click a format  ·  Esc or right-click to cancel",
    "Converto in {cosa}…": "Converting to {cosa}…",
    "clic qui per annullare": "click here to cancel",
    "Annullato": "Cancelled",
    "Esc per ricominciare": "Esc to start over",
    "Clic al centro o Esc per annullare": "Click the centre or Esc to cancel",
    "{n} file già pronti": "{n} files already done",
    "nessun file creato": "no file created",
    "clicca qui per la cartella": "click here for the folder",
    "Clicca fuori o premi Esc per ricominciare": "Click outside or press Esc to start over",
    "\n(+ altri {n})": "\n(+ {n} more)",
    "Fatto": "Done",
    "salvato sul Desktop:\ncartella protetta": "saved to the Desktop:\nprotected folder",
    "clicca qui per\naprire la cartella": "click here to\nopen the folder",
    "Trascina altri file o clicca fuori per ricominciare": "Drop more files or click outside to start over",
    "{n} file pronti": "{n} files ready",
    "{n} file {cosa}": "{n} {cosa} files",
    "Errore": "Error",
    "{n} errori": "{n} errors",
    # tasto destro, sfera, avvisi
    "Converti…": "Convert…",
    "Il Convertitore è pronto": "The converter is ready",
    "Convertitore aggiornato a {v}": "Converter updated to {v}",
    "Clic per chiudere": "Click to close",
    "Trascina un file su questa sfera: si apre la ruota con i formati.": "Drop a file on this orb: the wheel of formats opens.",
    "Oppure selezionalo e premi Ctrl+Alt+C (o tasto destro, poi Converti…).": "Or select it and press Ctrl+Alt+C (or right-click, then Convert…).",
    "Il file nuovo compare accanto all'originale. Tasto destro sulla sfera per le impostazioni.": "The new file appears next to the original. Right-click the orb for settings.",
    "BENVENUTO": "WELCOME",
    "NOVITÀ": "WHAT'S NEW",
    "Apri la ruota": "Open the wheel",
    "Impostazioni…": "Settings…",
    "Nascondi per 30 minuti": "Hide for 30 minutes",
    "Chiudi la sfera": "Close the orb",
    "Versione {v}": "Version {v}",
})

# fette della ruota
EN_ETICHETTE = {
    "unisci": "MERGE", "word": "WORD", "leggero": "LIGHTER", "quadrata": "SQUARE", "destra": "RIGHT",
    "sinistra": "LEFT", "dritta": "STRAIGHT", "grp:misura": "SIZE", "grp:ruota": "ROTATE", "grp:altri": "MORE",
    "appunti": "CLIPBOARD", "cat:immagine": "IMAGES", "cat:video": "VIDEO", "cat:audio": "AUDIO", "cat:pdf": "PDF",
    "cat:word": "WORD", "cat:excel": "EXCEL", "cat:powerpoint": "PPT",
}
EN_SOTTOTITOLI = {
    "png": "image", "jpg": "image", "webp": "light", "bmp": "image", "tiff": "high quality", "ico": "icon",
    "gif": "animation", "pdf": "document", "mp4": "video", "mkv": "video", "mov": "video", "avi": "video",
    "webm": "web", "mp3": "audio only", "wav": "audio", "flac": "lossless", "ogg": "audio", "m4a": "audio",
    "aac": "audio", "txt": "text only", "docx": "Word", "rtf": "text", "xlsx": "Excel", "csv": "table",
    "pptx": "PowerPoint", "unisci": "one PDF", "word": "editable", "leggero": "fewer MB", "r50": "half size",
    "r1920": "long side", "quadrata": "1080 · social", "destra": "90°", "sinistra": "90°", "r180": "upside down",
    "dritta": "crooked photos", "grp:misura": "resize", "grp:ruota": "turn", "grp:altri": "bmp · tiff · ico",
    "appunti": "screenshot",
}
EN_DESCRIZIONI = {
    "leggero": "Shrinking…", "r50": "Resizing to 50%…", "r1920": "Resizing to 1920 px…", "quadrata": "Cropping square…",
    "destra": "Rotating right…", "sinistra": "Rotating left…", "r180": "Flipping…", "dritta": "Straightening…",
    "unisci": "Merging into one PDF…", "word": "Converting to Word…",
}
EN_NOMI_TIPO = {"immagine": "an image", "video": "a video", "audio": "an audio file", "pdf": "a PDF",
                "word": "a document", "excel": "an Excel sheet", "powerpoint": "a presentation"}
EN_NOMI_CAT = {"immagine": "image", "video": "video", "audio": "audio", "pdf": "PDF", "word": "document",
               "excel": "Excel", "powerpoint": "presentation"}
