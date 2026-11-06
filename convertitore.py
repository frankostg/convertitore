"""Convertitore di file con ruota delle conversioni.

Trascina uno o piu' file sulla finestra (o sull'icona del Desktop):
compare una ruota con tutte le conversioni possibili. Clicca un formato
e il file convertito viene salvato nella stessa cartella dell'originale.
"""
import ctypes
import glob
import math
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk
from tkinterdnd2 import DND_FILES, TkinterDnD

from testi import lingua, t

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except Exception:
    pass

# ----------------------------------------------------------------- formati
CATEGORIE = {
    "immagine": {"jpg", "jpeg", "png", "webp", "bmp", "gif", "tif", "tiff", "ico", "heic", "heif", "avif", "jfif"},
    "video": {"mp4", "mov", "avi", "mkv", "webm", "wmv", "flv", "m4v", "3gp", "mpg", "mpeg", "ts"},
    "audio": {"mp3", "wav", "flac", "ogg", "m4a", "aac", "wma", "opus", "aiff", "amr"},
    "pdf": {"pdf"},
    "word": {"doc", "docx", "odt", "rtf", "txt", "md"},
    "excel": {"xls", "xlsx", "xlsm", "ods", "csv"},
    "powerpoint": {"ppt", "pptx", "odp"},
}

DESTINAZIONI = {
    "immagine": ["png", "jpg", "webp", "pdf", "leggero", "grp:misura", "grp:ruota", "gif", "grp:altri"],
    "video": ["mp4", "leggero", "mkv", "mov", "avi", "webm", "gif", "mp3", "wav"],
    "audio": ["mp3", "wav", "flac", "ogg", "m4a", "aac", "leggero"],
    "pdf": ["word", "png", "jpg", "txt", "leggero", "grp:ruota"],
    "word": ["pdf", "docx", "txt", "rtf"],
    "excel": ["pdf", "xlsx", "csv"],
    "powerpoint": ["pdf", "pptx"],
}

# fette che aprono una seconda ruota (clic al centro per tornare indietro)
GRUPPI = {
    "immagine": {"grp:misura": ["r50", "r1920", "quadrata"],
                 "grp:ruota": ["dritta", "destra", "r180", "sinistra"],
                 "grp:altri": ["bmp", "tiff", "ico"]},
    "pdf": {"grp:ruota": ["r180", "destra", "sinistra"]},
}

# azioni che non cambiano formato: il file resta dello stesso tipo
AZIONI = {"leggero", "r50", "r1920", "quadrata", "destra", "sinistra", "r180", "dritta", "unisci"}
DESCRIZIONI = {
    "leggero": "Alleggerisco…", "r50": "Riduco al 50%…", "r1920": "Riduco a 1920 px…",
    "quadrata": "Ritaglio quadrata…", "destra": "Ruoto a destra…", "sinistra": "Ruoto a sinistra…",
    "r180": "Capovolgo…", "dritta": "Raddrizzo…", "unisci": "Unisco in un PDF…", "word": "Converto in Word…",
}

SOTTOTITOLI = {
    "png": "immagine", "jpg": "immagine", "webp": "leggera", "bmp": "immagine",
    "tiff": "alta qualità", "ico": "icona", "gif": "animazione", "pdf": "documento",
    "mp4": "video", "mkv": "video", "mov": "video", "avi": "video", "webm": "web",
    "mp3": "solo audio", "wav": "audio", "flac": "senza perdita", "ogg": "audio",
    "m4a": "audio", "aac": "audio", "txt": "solo testo", "docx": "Word", "rtf": "testo",
    "xlsx": "Excel", "csv": "tabella", "pptx": "PowerPoint",
    "unisci": "un solo PDF", "word": "modificabile", "leggero": "meno MB",
    "r50": "metà misura", "r1920": "lato lungo", "quadrata": "1080 · social",
    "destra": "90°", "sinistra": "90°", "r180": "capovolgi", "dritta": "foto storte",
    "grp:misura": "ridimensiona", "grp:ruota": "gira", "grp:altri": "bmp · tiff · ico",
    "appunti": "screenshot",
}

ETICHETTE = {"unisci": "UNISCI", "word": "WORD", "leggero": "LEGGERO", "r50": "50%", "r1920": "1920",
             "quadrata": "QUADRATA", "destra": "DESTRA", "sinistra": "SINISTRA", "r180": "180°",
             "dritta": "DRITTA", "grp:misura": "MISURA", "grp:ruota": "RUOTA", "grp:altri": "ALTRI",
             "appunti": "APPUNTI"}

# palette "sala comandi" (come il Jarvis): un colore per tipo di file
# un colore per tipo di file (usato con parsimonia: puntini, anello, fetta scelta)
COLORI = {
    "immagine": (56, 189, 248),
    "video": (167, 139, 250),
    "audio": (52, 211, 153),
    "pdf": (251, 146, 60),
    "word": (96, 165, 250),
    "excel": (163, 230, 53),
    "powerpoint": (251, 113, 133),
    "unione": (251, 146, 60),
    "unisci": (251, 146, 60),
    "appunti": (203, 213, 225),
}

# ruota senza file: una fetta per ogni tipo di file
PANORAMICA = ["cat:immagine", "cat:video", "cat:audio", "cat:pdf", "cat:word", "cat:excel", "cat:powerpoint"]
ETICHETTE.update({"cat:immagine": "IMMAGINI", "cat:video": "VIDEO", "cat:audio": "AUDIO", "cat:pdf": "PDF",
                  "cat:word": "WORD", "cat:excel": "EXCEL", "cat:powerpoint": "PPT"})
SOTTOTITOLI.update({k: " · ".join([d for d in DESTINAZIONI[k[4:]] if d not in AZIONI and ":" not in d][:3]) + " …"
                    for k in PANORAMICA})
NOMI_TIPO = {"immagine": "un'immagine", "video": "un video", "audio": "un audio", "pdf": "un PDF",
             "word": "un documento", "excel": "un foglio Excel", "powerpoint": "una presentazione"}

# nomi dei tipi come compaiono al centro della ruota
NOMI_CAT = {"immagine": "immagine", "video": "video", "audio": "audio", "pdf": "PDF", "word": "documento",
            "excel": "Excel", "powerpoint": "presentazione"}
if lingua() == "en":
    import testi as _testi_en
    for _tab, _en in ((ETICHETTE, _testi_en.EN_ETICHETTE), (SOTTOTITOLI, _testi_en.EN_SOTTOTITOLI),
                      (DESCRIZIONI, _testi_en.EN_DESCRIZIONI), (NOMI_TIPO, _testi_en.EN_NOMI_TIPO),
                      (NOMI_CAT, _testi_en.EN_NOMI_CAT)):
        _tab.update({k: v for k, v in _en.items() if k in _tab})
    SOTTOTITOLI.update({k: " · ".join([d for d in DESTINAZIONI[k[4:]] if d not in AZIONI and ":" not in d][:3]) + " …"
                        for k in PANORAMICA})

ALIAS = {"jpeg": "jpg", "jfif": "jpg", "tif": "tiff", "heif": "heic"}


def estensione(path):
    return os.path.splitext(path)[1].lower().lstrip(".")


def categoria(path):
    ext = estensione(path)
    for cat, exts in CATEGORIE.items():
        if ext in exts:
            return cat
    return None


def _filtra(chiavi, exts):
    """Toglie il formato che il file ha gia' (convertire un PNG in PNG non serve)."""
    return [d for d in chiavi if not (len(exts) == 1 and d in exts)]


_office = {}


def office_installato(app):
    """True se sul PC c'e' Microsoft Word / Excel / PowerPoint (registrati per l'automazione)."""
    if app not in _office:
        import winreg
        try:
            winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, rf"{app}.Application\CLSID"))
            _office[app] = True
        except OSError:
            _office[app] = False
    return _office[app]


OFFICE_APP = {"word": "Word", "excel": "Excel", "powerpoint": "PowerPoint"}


def opzioni_per(files):
    """Restituisce (categoria, lista di chiavi) valide per tutti i file."""
    cats = {categoria(f) for f in files}
    if None in cats:
        return None, []
    if len(cats) != 1:
        # immagini e PDF insieme: si possono unire in un unico PDF
        if cats == {"immagine", "pdf"}:
            return "unione", ["unisci"]
        return "misto", []
    cat = cats.pop()
    exts = {ALIAS.get(estensione(f), estensione(f)) for f in files}
    opz = _filtra(DESTINAZIONI[cat], exts)
    if cat == "pdf" and not office_installato("Word"):
        opz.remove("word")  # PDF -> Word lo fa Word: senza Office la fetta non c'e'
    if cat in OFFICE_APP and not office_installato(OFFICE_APP[cat]):
        return cat, []  # serve Office per questi documenti
    if cat in ("immagine", "pdf") and len(files) > 1:
        opz.insert(0, "unisci")
    return cat, opz


MAX_FILE = 2000  # una cartella enorme non deve bloccare la ruota


def espandi(percorsi):
    """Cartelle -> i file convertibili che contengono (anche nelle sottocartelle).
    Restituisce (file convertibili, quanti file ignorati perche' non supportati)."""
    trovati, ignorati = [], 0
    for p in percorsi:
        if os.path.isdir(p):
            for radice, cartelle, nomi in os.walk(p):
                cartelle[:] = sorted(c for c in cartelle if not c.startswith((".", "$")))
                for n in sorted(nomi, key=chiave_nome):
                    if n.startswith((".", "~$")):
                        continue
                    f = os.path.join(radice, n)
                    if categoria(f):
                        trovati.append(f)
                    else:
                        ignorati += 1
                    if len(trovati) >= MAX_FILE:
                        return trovati, ignorati
        elif os.path.isfile(p):
            if categoria(p):
                trovati.append(p)
            else:
                ignorati += 1
    return trovati, ignorati


def opzioni_gruppo(cat, gruppo, files):
    exts = {ALIAS.get(estensione(f), estensione(f)) for f in files}
    return _filtra(GRUPPI.get(cat, {}).get(gruppo, []), exts)


# ----------------------------------------------------------------- conversioni
def impostazioni():
    from impostazioni import leggi
    return leggi()


IMP = impostazioni()


# quanto alleggerisce "Leggero" (Impostazioni: poco / medio / molto)
LIVELLI = {
    "poco": {"lato": 3200, "jpg": 86, "webp": 86, "pdf_dpi": 170, "pdf_q": 80, "pdf_lato": 2400, "video_lato": 1920, "crf": 25, "audio": "128k"},
    "medio": {"lato": 2560, "jpg": 78, "webp": 80, "pdf_dpi": 130, "pdf_q": 70, "pdf_lato": 1700, "video_lato": 1280, "crf": 28, "audio": "96k"},
    "molto": {"lato": 1600, "jpg": 68, "webp": 70, "pdf_dpi": 96, "pdf_q": 55, "pdf_lato": 1200, "video_lato": 854, "crf": 31, "audio": "64k"},
}


def livello():
    return LIVELLI.get(IMP.get("leggero"), LIVELLI["medio"])


def percorso_libero(cartella, nome, ext):
    out = os.path.join(cartella, f"{nome}.{ext}")
    if IMP.get("esistente") == "sostituisci":
        return out  # Impostazioni: sovrascrive il file convertito di prima (mai l'originale: ha un nome diverso)
    n = 1
    while os.path.exists(out):
        out = os.path.join(cartella, f"{nome} ({n}).{ext}")
        n += 1
    return out


CARTELLA_USCITA = None  # se impostata (immagine dagli appunti) i file finiscono qui


class Annullato(BaseException):
    """Conversione fermata da chi usa il programma. Deriva da BaseException apposta:
    le librerie che ignorano gli errori non la fermano."""


class Lavoro:
    """Stato della conversione in corso, condiviso tra la ruota e chi converte:
    avanzamento (0..1), richiesta di annullare, processi esterni da fermare."""

    def __init__(self, n=1):
        self.annulla = threading.Event()
        self.n, self.i = max(1, n), 0
        self.frazione = None      # None = non si sa quanto manca (rotellina)
        self.nome = ""
        self.processo = None      # ffmpeg in corso
        self.pid_office = None    # Word/Excel/PowerPoint aperto da noi
        self.spostati = False     # file salvati sul Desktop perche' la cartella era protetta

    def controlla(self):
        if self.annulla.is_set():
            raise Annullato()

    def parte(self, frac):
        """Avanzamento del file corrente (0..1) -> avanzamento totale."""
        self.frazione = (self.i + max(0.0, min(1.0, frac))) / self.n
        self.controlla()

    def ferma(self):
        """Chiamata dalla ruota (clic al centro o Esc): ferma subito i processi esterni."""
        self.annulla.set()
        if self.processo is not None:
            try:
                self.processo.kill()
            except OSError:
                pass
        if self.pid_office:
            termina_processo(self.pid_office)


LAVORO = Lavoro()


def termina_processo(pid):
    subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"], capture_output=True, creationflags=0x08000000)


_scrivibili = {}


def cartella_scrivibile(cartella):
    """Prova davvero a scrivere: os.access non basta su OneDrive e cartelle protette."""
    if cartella not in _scrivibili:
        prova = os.path.join(cartella, f".convertitore-prova-{os.getpid()}")
        try:
            with open(prova, "w") as fh:
                fh.write("ok")
            os.remove(prova)
            _scrivibili[cartella] = True
        except OSError:
            _scrivibili[cartella] = False
    return _scrivibili[cartella]


def cartella_per(src):
    """Dove salvare: accanto all'originale, oppure sul Desktop se li' non si puo' scrivere."""
    if CARTELLA_USCITA:
        return CARTELLA_USCITA
    fissa = IMP.get("cartella")
    if fissa and os.path.isdir(fissa) and cartella_scrivibile(fissa):
        return fissa  # Impostazioni: tutti i file convertiti in una cartella sola
    cartella = os.path.dirname(os.path.abspath(src))
    if cartella_scrivibile(cartella):
        return cartella
    LAVORO.spostati = True
    return cartella_desktop()


def uscita(src, ext, suffisso=""):
    base = os.path.splitext(os.path.basename(src))[0] + suffisso
    return percorso_libero(cartella_per(src), base, ext)


def cartella_desktop():
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:  # CSIDL_DESKTOPDIRECTORY
        return buf.value
    return os.path.join(os.path.expanduser("~"), "Desktop")


def troppo_grande(src, out):
    """Per "leggero": se il risultato non pesa meno dell'originale non serve a niente."""
    if os.path.getsize(out) >= os.path.getsize(src) * 0.97:
        os.remove(out)
        raise RuntimeError(t("è già leggero, non si riduce di più"))


def mostra_in_cartella(files):
    """Apre la cartella in Esplora file con i file indicati gia' selezionati."""
    files = [os.path.normpath(f) for f in files if os.path.exists(f)]
    if not files:
        return
    try:
        sh, ole = ctypes.windll.shell32, ctypes.windll.ole32
        ole.CoInitialize(None)
        cartella = ctypes.c_void_p()
        if sh.SHParseDisplayName(os.path.dirname(files[0]), None, ctypes.byref(cartella), 0, None) != 0:
            raise OSError("cartella non trovata")
        figli = []
        for f in files[:200]:
            p = ctypes.c_void_p()
            if sh.SHParseDisplayName(f, None, ctypes.byref(p), 0, None) == 0:
                figli.append(p)
        arr = (ctypes.c_void_p * len(figli))(*[p.value for p in figli])
        if sh.SHOpenFolderAndSelectItems(cartella, len(figli), arr, 0) != 0:
            raise OSError("apertura non riuscita")
        for p in figli + [cartella]:
            ole.CoTaskMemFree(p)
    except Exception:
        subprocess.Popen(["explorer", "/select,", files[0]])


def trova_ffmpeg():
    # versione installata: ffmpeg.exe viaggia insieme al Convertitore
    for cartella in (os.path.dirname(sys.executable), os.path.dirname(os.path.abspath(__file__))):
        incluso = os.path.join(cartella, "ffmpeg.exe")
        if getattr(sys, "frozen", False) and os.path.exists(incluso):
            return incluso
    p = shutil.which("ffmpeg")
    if p:
        return p
    pattern = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\ffmpeg.exe")
    trovati = glob.glob(pattern)
    return trovati[0] if trovati else None


NO_WINDOW = 0x08000000


def su_bianco(im):
    """Toglie la trasparenza mettendo uno sfondo bianco (JPG, BMP e PDF non la supportano)."""
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        sfondo = Image.new("RGB", im.size, (255, 255, 255))
        sfondo.paste(im, mask=im.getchannel("A"))
        return sfondo
    return im.convert("RGB")


def ha_trasparenza(im):
    return im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)


def salva_come_originale(im, src, suffisso):
    """Salva un'immagine modificata nello stesso formato dell'originale."""
    ext = ALIAS.get(estensione(src), estensione(src))
    if ext in ("heic", "avif"):
        ext = "jpg"  # formati che non tutti sanno aprire: meglio un JPG
    out = uscita(src, ext, suffisso)
    if ext in ("jpg", "bmp"):
        su_bianco(im).save(out, "JPEG" if ext == "jpg" else "BMP", **({"quality": 92} if ext == "jpg" else {}))
    elif ext == "ico":
        im.convert("RGBA").save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    elif ext == "gif":
        im.convert("RGBA").convert("P", palette=Image.ADAPTIVE).save(out)
    elif ext == "webp":
        im.save(out, quality=88)
    else:
        im.save(out)
    return out


def modifica_immagine(src, key):
    from PIL import ImageOps
    im = Image.open(src)
    im.seek(0)
    im = ImageOps.exif_transpose(im)  # le foto del telefono vanno girate come dice l'EXIF
    if key == "leggero":
        lv = livello()
        im.thumbnail((lv["lato"], lv["lato"]), Image.LANCZOS)
        if ha_trasparenza(im):
            out = uscita(src, "webp", t(" (leggera)"))
            im.save(out, quality=lv["webp"], method=6)
        else:
            out = uscita(src, "jpg", t(" (leggera)"))
            su_bianco(im).save(out, "JPEG", quality=lv["jpg"], optimize=True, progressive=True)
        troppo_grande(src, out)
        return [out]
    if key == "r50":
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS)
        return [salva_come_originale(im, src, " (50%)")]
    if key == "r1920":
        if max(im.size) <= 1920:
            raise RuntimeError(t("è già più piccola di 1920 px"))
        im.thumbnail((1920, 1920), Image.LANCZOS)
        return [salva_come_originale(im, src, " (1920)")]
    if key == "quadrata":
        im = ImageOps.fit(im, (1080, 1080), Image.LANCZOS)
        return [salva_come_originale(im, src, t(" (quadrata)"))]
    if key == "dritta":
        # exif_transpose l'ha gia' raddrizzata
        return [salva_come_originale(im, src, t(" (dritta)"))]
    gradi = {"destra": Image.Transpose.ROTATE_270, "sinistra": Image.Transpose.ROTATE_90,
             "r180": Image.Transpose.ROTATE_180}[key]
    return [salva_come_originale(im.transpose(gradi), src, t(" (ruotata)"))]


def converti_immagine(src, key):
    if key in AZIONI:
        return modifica_immagine(src, key)
    im = Image.open(src)
    animata = getattr(im, "is_animated", False)
    if not animata:
        from PIL import ImageOps
        im = ImageOps.exif_transpose(im)  # foto del telefono: dritte anche nel nuovo formato
    out = uscita(src, key)
    if key in ("jpg", "bmp", "pdf"):
        im = su_bianco(im)
        kw = {"quality": 92} if key == "jpg" else {}
        im.save(out, "JPEG" if key == "jpg" else key.upper(), **kw)
    elif key == "ico":
        im.convert("RGBA").save(out, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    elif key in ("gif", "webp") and animata:
        im.save(out, save_all=True, loop=0)
    elif key == "webp":
        im.save(out, quality=88)
    else:
        if key == "gif" and im.mode == "RGBA":
            im = im.convert("P", palette=Image.ADAPTIVE)
        im.save(out)
    return [out]


def chiave_nome(f):
    """Ordine naturale: "foto 2" prima di "foto 10"."""
    import re
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", os.path.basename(f))]


# PDF: pypdfium2 (pagine in immagini, testo) e pikepdf (unisci, ruota, alleggerisci).
# Licenze BSD/Apache e MPL: si possono usare in un programma a pagamento.

def apri_pdf(src):
    """Apre il PDF con pikepdf; errori chiari per file danneggiati o con password."""
    import pikepdf
    try:
        return pikepdf.open(src)
    except pikepdf.PasswordError as e:
        raise RuntimeError(t("PDF protetto da password: aprilo, togli la password e riprova")) from e
    except Exception as e:
        raise RuntimeError(t("PDF danneggiato o non leggibile")) from e


def apri_pdfium(src):
    import pypdfium2 as pdfium
    try:
        return pdfium.PdfDocument(src)
    except Exception as e:
        if "password" in str(e).lower():
            raise RuntimeError(t("PDF protetto da password: aprilo, togli la password e riprova")) from e
        raise RuntimeError(t("PDF danneggiato o non leggibile")) from e


def alleggerisci_pdf(src):
    """Ricomprime le foto dentro il PDF (piu' piccole e in JPEG) e compatta il file."""
    import io
    import pikepdf
    lv = livello()
    out = uscita(src, "pdf", t(" (leggero)"))
    with apri_pdf(src) as pdf:
        fatte = set()
        n = len(pdf.pages)
        for i, pagina in enumerate(pdf.pages):
            LAVORO.parte(i / n * 0.9)
            for raw in pagina.images.values():
                if raw.objgen in fatte:
                    continue
                fatte.add(raw.objgen)
                try:
                    if "/Mask" in raw or "/Decode" in raw or raw.get("/ImageMask", False):
                        continue  # trasparenze particolari: meglio non toccarle
                    img = pikepdf.PdfImage(raw)
                    if img.bits_per_component != 8 or img.mode not in ("RGB", "L"):
                        continue
                    filtro = [str(f) for f in img.filters]
                    w, h = img.width, img.height
                    if max(w, h) <= lv["pdf_lato"] and "/DCTDecode" in filtro:
                        continue  # gia' piccola e gia' JPEG
                    if w * h < 40_000:
                        continue  # icone e loghi: non conviene
                    pil = img.as_pil_image()
                    pil = pil.convert("L" if img.mode == "L" else "RGB")
                    pil.thumbnail((lv["pdf_lato"], lv["pdf_lato"]), Image.LANCZOS)
                    buf = io.BytesIO()
                    pil.save(buf, "JPEG", quality=lv["pdf_q"], optimize=True)
                    raw.write(buf.getvalue(), filter=pikepdf.Name.DCTDecode)
                    raw.Width, raw.Height = pil.size
                    raw.BitsPerComponent = 8
                    raw.ColorSpace = pikepdf.Name.DeviceGray if pil.mode == "L" else pikepdf.Name.DeviceRGB
                    if "/DecodeParms" in raw:
                        del raw.DecodeParms
                except Exception:
                    continue  # un'immagine strana non deve fermare tutto
        LAVORO.parte(0.92)
        pdf.remove_unreferenced_resources()
        pdf.save(out, compress_streams=True, recompress_flate=True,
                 object_stream_mode=pikepdf.ObjectStreamMode.generate)
    troppo_grande(src, out)
    return [out]


def ruota_pdf(src, key):
    delta = {"destra": 90, "sinistra": 270, "r180": 180}[key]
    out = uscita(src, "pdf", t(" (ruotato)"))
    with apri_pdf(src) as pdf:
        n = len(pdf.pages)
        for i, pagina in enumerate(pdf.pages):
            pagina.rotate(delta, relative=True)
            LAVORO.parte((i + 1) / n * 0.8)
        pdf.save(out)
    return [out]


def pdf_in_testo(src):
    doc = apri_pdfium(src)
    out = uscita(src, "txt")
    try:
        with open(out, "w", encoding="utf-8") as fh:
            for i in range(len(doc)):
                if i:
                    fh.write("\n\n" + t("----- pagina {n} -----", n=i + 1) + "\n\n")
                pagina = doc[i]
                testo = pagina.get_textpage()
                fh.write(testo.get_text_range().replace("\r\n", "\n"))
                testo.close()
                pagina.close()
                LAVORO.parte((i + 1) / len(doc))
    except BaseException:
        if os.path.exists(out):
            os.remove(out)
        raise
    finally:
        doc.close()
    return [out]


def pdf_in_immagini(src, key):
    doc = apri_pdfium(src)
    outs = []
    try:
        n = len(doc)
        for i in range(n):
            LAVORO.parte(i / n)
            pagina = doc[i]
            im = pagina.render(scale=170 / 72).to_pil()
            pagina.close()
            suff = "" if n == 1 else t(" - pagina {n}", n=i + 1)
            out = uscita(src, key, suff)
            if key == "jpg":
                im.convert("RGB").save(out, "JPEG", quality=90)
            else:
                im.save(out)
            outs.append(out)
    except Annullato:
        for o in outs:  # niente pagine a meta': tolgo quelle gia' create di questo PDF
            os.remove(o)
        raise
    finally:
        doc.close()
    return outs


def pdf_in_word(src):
    """PDF -> Word modificabile con Microsoft Word (la fetta compare solo se Word c'e').
    Word riceve una copia con un nome nuovo: se una volta si e' chiuso male su un file,
    la volta dopo chiede "Aprirlo?" e resterebbe fermo li'."""
    import shutil
    import tempfile
    import uuid
    apri_pdf(src).close()  # controlla subito password e file danneggiati
    out = uscita(src, "docx")
    cartella = os.path.join(tempfile.gettempdir(), "Convertitore")
    os.makedirs(cartella, exist_ok=True)
    copia = os.path.join(cartella, f"pdf-{uuid.uuid4().hex[:12]}.pdf")
    shutil.copyfile(src, copia)
    try:
        return converti_office(copia, "docx", "word", out=out)
    except Exception as e:
        if type(e).__name__ == "com_error":
            raise RuntimeError(t("Word non è riuscito a convertire il PDF: serve Office attivato e aggiornato")) from e
        raise
    finally:
        try:
            os.remove(copia)
        except OSError:
            pass


def converti_pdf(src, key):
    if key == "word":
        return pdf_in_word(src)
    if key == "leggero":
        return alleggerisci_pdf(src)
    if key in ("destra", "sinistra", "r180"):
        return ruota_pdf(src, key)
    if key == "txt":
        return pdf_in_testo(src)
    return pdf_in_immagini(src, key)


def unisci_pdf(files):
    """Mette PDF e immagini (in ordine di nome) in un unico PDF."""
    import io
    import pikepdf
    from PIL import ImageOps
    files = sorted(files, key=chiave_nome)
    aperti = []  # pikepdf vuole i PDF di origine aperti finche' non salva
    try:
        unito = pikepdf.new()
        for k, f in enumerate(files):
            LAVORO.frazione = k / len(files)
            LAVORO.nome = os.path.basename(f)
            LAVORO.controlla()
            if categoria(f) == "pdf":
                d = apri_pdf(f)
            else:
                buf = io.BytesIO()
                su_bianco(ImageOps.exif_transpose(Image.open(f))).save(buf, "PDF", resolution=150)
                buf.seek(0)
                d = pikepdf.open(buf)
            aperti.append(d)
            unito.pages.extend(d.pages)
        nome = t("Immagini unite") if all(categoria(f) == "immagine" for f in files) else t("PDF unito")
        out = percorso_libero(cartella_per(files[0]), nome, "pdf")
        unito.save(out, compress_streams=True, object_stream_mode=pikepdf.ObjectStreamMode.generate)
    finally:
        for d in aperti:
            d.close()
    return [out]


FFMPEG_ARGS = {
    "mp4": ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
    "mkv": ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-c:a", "aac", "-b:a", "192k"],
    "mov": ["-c:v", "libx264", "-preset", "fast", "-crf", "22", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"],
    "avi": ["-c:v", "mpeg4", "-q:v", "3", "-c:a", "libmp3lame", "-q:a", "3"],
    "webm": ["-c:v", "libvpx-vp9", "-crf", "33", "-b:v", "0", "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus", "-b:a", "128k"],
    "gif": ["-vf", "fps=12,scale='min(560,iw)':-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse", "-an"],
    "mp3": ["-vn", "-c:a", "libmp3lame", "-q:a", "2"],
    "wav": ["-vn", "-c:a", "pcm_s16le"],
    "flac": ["-vn", "-c:a", "flac"],
    "ogg": ["-vn", "-c:a", "libvorbis", "-q:a", "5"],
    "m4a": ["-vn", "-c:a", "aac", "-b:a", "192k"],
    "aac": ["-vn", "-c:a", "aac", "-b:a", "192k"],
}
def argomenti_leggero(video):
    """Video al massimo 1280 px (livello medio: va bene per WhatsApp e email), audio MP3."""
    lv = livello()
    if not video:
        return ["-vn", "-c:a", "libmp3lame", "-b:a", lv["audio"]]
    l = lv["video_lato"]
    return ["-vf", f"scale=w='min({l},iw)':h='min({l},ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v", "libx264", "-preset", "medium", "-crf", str(lv["crf"]), "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "96k" if lv["audio"] != "64k" else "64k", "-movflags", "+faststart"]



def esamina_media(ff, src):
    """(durata in secondi o None, ha audio?, ha video?) dall'intestazione che ffmpeg stampa."""
    import re
    r = subprocess.run([ff, "-hide_banner", "-i", src], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", creationflags=NO_WINDOW)
    testo = r.stderr or ""
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", testo)
    durata = (int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) or None) if m else None
    flussi = re.findall(r"Stream #\S+.*?: (Audio|Video):", testo)
    return durata, "Audio" in flussi, "Video" in flussi


def converti_ffmpeg(src, key):
    ff = trova_ffmpeg()
    if not ff:
        raise RuntimeError(t("manca ffmpeg: reinstalla il Convertitore"))
    if key == "leggero":
        video = categoria(src) == "video"
        out = uscita(src, "mp4" if video else "mp3", t(" (leggero)"))
        argomenti = argomenti_leggero(video)
    else:
        out = uscita(src, key)
        argomenti = FFMPEG_ARGS[key]
    durata, ha_audio, ha_video = esamina_media(ff, src)
    solo_audio = "-vn" in argomenti
    if solo_audio and not ha_audio and (ha_video or durata):
        raise RuntimeError(t("questo video non contiene audio"))
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-nostats", "-progress", "pipe:1", "-y", "-i", src, *argomenti, out]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
    LAVORO.processo = proc
    errori = []
    lettore = threading.Thread(target=lambda: errori.extend(proc.stderr.read().splitlines()), daemon=True)
    lettore.start()
    try:
        for riga in proc.stdout:
            if LAVORO.annulla.is_set():
                proc.kill()
                break
            if riga.startswith("out_time_us=") and durata:
                try:
                    LAVORO.frazione = (LAVORO.i + max(0.0, min(1.0, int(riga.split("=", 1)[1]) / 1e6 / durata))) / LAVORO.n
                except ValueError:
                    pass
        proc.wait()
    finally:
        LAVORO.processo = None
    lettore.join(timeout=2)
    if LAVORO.annulla.is_set() or proc.returncode != 0:
        if os.path.exists(out):
            try:
                os.remove(out)
            except OSError:
                pass
        LAVORO.controlla()  # annullato: esce da qui
        raise RuntimeError("ffmpeg: " + (errori[-1] if errori else "errore sconosciuto"))
    if key == "leggero":
        troppo_grande(src, out)
    return [out]


OFFICE_TEMPO_MAX = 180  # secondi per file: oltre, Office viene chiuso (si e' bloccato)
OFFICE_EXE = {"word": "WINWORD.EXE", "excel": "EXCEL.EXE", "powerpoint": "POWERPNT.EXE"}


def pid_di(nome_exe):
    r = subprocess.run(["tasklist", "/FI", f"IMAGENAME eq {nome_exe}", "/FO", "CSV", "/NH"],
                       capture_output=True, text=True, creationflags=NO_WINDOW)
    pids = set()
    for riga in r.stdout.splitlines():
        parti = riga.strip().strip('"').split('","')
        if len(parti) > 1 and parti[1].isdigit():
            pids.add(int(parti[1]))
    return pids


def domanda_office(pid):
    """Testo di una finestra di dialogo che Office (processo pid) ha aperto e aspetta risposta, o None."""
    import win32gui
    import win32process
    trovata = []

    def finestra(h, _):
        # Office lavora nascosto: qualunque sua finestra visibile e' una domanda che aspetta risposta
        if not win32gui.IsWindowVisible(h) or win32process.GetWindowThreadProcessId(h)[1] != pid:
            return
        x0, y0, x1, y1 = win32gui.GetWindowRect(h)
        if x1 - x0 < 60 or y1 - y0 < 40:
            return
        testi = []
        win32gui.EnumChildWindows(h, lambda c, _: testi.append(win32gui.GetWindowText(c))
                                  if win32gui.GetClassName(c) == "Static" and win32gui.GetWindowText(c) else None, None)
        testo = " ".join(testi) or win32gui.GetWindowText(h)
        trovata.append(testo.replace("\r", " ").replace("\n", " ").strip() or "?")
    try:
        win32gui.EnumWindows(finestra, None)
    except Exception:
        return None
    return trovata[0] if trovata else None


def converti_office(src, key, cat, out=None):
    """Word/Excel/PowerPoint aperti di nascosto. Ricordo il loro processo per poterli
    chiudere se l'utente annulla, se si bloccano o se si fermano su una domanda."""
    prima = pid_di(OFFICE_EXE[cat])
    scaduto = threading.Event()
    domanda = []

    def sorveglia():
        vista_da = None
        while not fatto.wait(0.3):
            if LAVORO.pid_office is None:
                nuovi = pid_di(OFFICE_EXE[cat]) - prima
                if nuovi:
                    LAVORO.pid_office = min(nuovi)
            if LAVORO.annulla.is_set() and LAVORO.pid_office:
                termina_processo(LAVORO.pid_office)  # annullato prima che conoscessi il processo
                return
            if LAVORO.pid_office:
                # una finestra di Office che aspetta una risposta: nessuno la vedrebbe, inutile aspettare
                testo = domanda_office(LAVORO.pid_office)
                vista_da = (vista_da or time.monotonic()) if testo else None
                if testo and time.monotonic() - vista_da > 2:
                    domanda.append(testo)
                    termina_processo(LAVORO.pid_office)
                    return
            if time.monotonic() - inizio > OFFICE_TEMPO_MAX:
                scaduto.set()
                if LAVORO.pid_office:
                    termina_processo(LAVORO.pid_office)
                return
    fatto, inizio = threading.Event(), time.monotonic()
    threading.Thread(target=sorveglia, daemon=True).start()
    try:
        return _converti_office(src, key, cat, out)
    except Exception as e:
        LAVORO.controlla()
        if domanda:
            raise RuntimeError(t("Office si è fermato su una domanda: «{testo}»", testo=accorcia(domanda[0], 90))) from e
        if scaduto.is_set():
            raise RuntimeError(t("Office non risponde: conversione interrotta dopo 3 minuti")) from e
        raise
    finally:
        fatto.set()
        LAVORO.pid_office = None


def _converti_office(src, key, cat, out=None):
    import pythoncom
    import win32com.client as win32
    pythoncom.CoInitialize()
    src = os.path.abspath(src)
    out = out or uscita(src, key)
    try:
        if cat == "word":
            app = win32.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
            if src.lower().endswith(".pdf"):
                import winreg
                with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\Office\{app.Version}\Word\Options") as k:
                    winreg.SetValueEx(k, "DisableConvertPdfWarning", 0, winreg.REG_DWORD, 1)
            try:
                d = app.Documents.Open(src, ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False)
                d.SaveAs2(out, FileFormat={"pdf": 17, "txt": 7, "rtf": 6, "docx": 16}[key])
                d.Close(False)
            finally:
                app.Quit()
        elif cat == "excel":
            app = win32.DispatchEx("Excel.Application")
            app.Visible = False
            app.DisplayAlerts = False
            try:
                wb = app.Workbooks.Open(src, ReadOnly=True)
                if key == "pdf":
                    wb.ExportAsFixedFormat(0, out)
                elif key == "csv":
                    wb.SaveAs(out, 62, Local=True)
                else:
                    wb.SaveAs(out, 51)
                wb.Close(False)
            finally:
                app.Quit()
        else:
            app = win32.DispatchEx("PowerPoint.Application")
            try:
                p = app.Presentations.Open(src, ReadOnly=True, WithWindow=False)
                p.SaveAs(out, {"pdf": 32, "pptx": 24}[key])
                p.Close()
            finally:
                app.Quit()
    finally:
        pythoncom.CoUninitialize()
    return [out]


REGISTRO = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Convertitore", "errori.log")


def registra_errore(f, key, e):
    """Dettagli tecnici nel registro (per l'assistenza); all'utente va solo la frase chiara."""
    import traceback
    try:
        os.makedirs(os.path.dirname(REGISTRO), exist_ok=True)
        if os.path.exists(REGISTRO) and os.path.getsize(REGISTRO) > 1_000_000:
            os.replace(REGISTRO, REGISTRO + ".1")
        with open(REGISTRO, "a", encoding="utf-8") as fh:
            fh.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')}  {key}  {f}\n")
            fh.write("".join(traceback.format_exception(e)))
    except OSError:
        pass


def messaggio(e):
    """Traduce un errore tecnico in una frase che si capisce."""
    testo = str(e)
    basso = testo.lower()
    nome = type(e).__name__
    if isinstance(e, FileNotFoundError):
        return t("file non trovato: è stato spostato o cancellato?")
    if isinstance(e, PermissionError):
        return t("file in uso da un altro programma: chiudilo e riprova")
    if isinstance(e, MemoryError):
        return t("file troppo grande per la memoria del PC")
    if nome == "UnidentifiedImageError" or "cannot identify image" in basso:
        return t("immagine danneggiata o di un tipo non riconosciuto")
    if nome == "DecompressionBombError":
        return t("immagine troppo grande (oltre i limiti di sicurezza)")
    if nome == "com_error":
        return t("Office non è riuscito ad aprire il file (serve Microsoft Office installato)")
    if testo.startswith("ffmpeg: "):
        dettaglio = basso
        if "does not contain any stream" in dettaglio or "matches no streams" in dettaglio:
            return t("il file non contiene la traccia richiesta (per esempio un video senza audio)")
        if "invalid data" in dettaglio or "moov atom not found" in dettaglio or "could not find codec" in dettaglio:
            return t("file audio/video danneggiato o incompleto")
        if "no space left" in dettaglio:
            return t("spazio sul disco esaurito")
        if "permission denied" in dettaglio:
            return t("impossibile scrivere il file: cartella protetta o file aperto")
        return t("conversione audio/video non riuscita")
    if "no space left" in basso or getattr(e, "errno", None) == 28:
        return t("spazio sul disco esaurito")
    if isinstance(e, RuntimeError):
        return testo  # messaggi gia' scritti per l'utente
    return t("errore imprevisto (dettagli nel registro errori)")


def converti(files, cat, key, avanzamento=None, lavoro=None):
    """Converte tutti i file. Restituisce (lista output, lista errori).
    Se l'utente annulla, si ferma e restituisce cio' che era gia' pronto."""
    global LAVORO
    LAVORO = lavoro or Lavoro(len(files))
    LAVORO.n = 1 if key == "unisci" else len(files)
    outs, errori = [], []
    if key == "unisci":
        try:
            outs = unisci_pdf(files)
        except Annullato:
            pass
        except Exception as e:  # noqa: BLE001
            registra_errore(files[0], key, e)
            errori.append(messaggio(e))
        return outs, errori
    for i, f in enumerate(files):
        LAVORO.i, LAVORO.nome = i, os.path.basename(f)
        LAVORO.frazione = i / LAVORO.n if LAVORO.n > 1 else None
        if avanzamento:
            avanzamento(i, len(files), os.path.basename(f))
        try:
            LAVORO.controlla()
            if not os.path.exists(f):
                raise FileNotFoundError(f)
            if cat == "immagine":
                outs += converti_immagine(f, key)
            elif cat == "pdf":
                outs += converti_pdf(f, key)
            elif cat in ("video", "audio"):
                outs += converti_ffmpeg(f, key)
            else:
                outs += converti_office(f, key, cat)
        except Annullato:
            break
        except Exception as e:  # noqa: BLE001
            registra_errore(f, key, e)
            errori.append(f"{os.path.basename(f)}: {messaggio(e)}")
    return outs, errori


# ----------------------------------------------------------------- grafica
W, H = 600, 660
CX, CY = 300, 350
R_IN, R_OUT = 108, 238
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    Z = ctypes.windll.user32.GetDpiForSystem() / 96
except Exception:
    Z = 1.0
S = 2  # supersampling per bordi morbidi
ZW, ZH = int(W * Z), int(H * Z)
BG = (14, 17, 27)
ACC = (125, 211, 252)     # accento neutro (ruota con piu' tipi)
ACC2 = (167, 139, 250)
INK = (241, 245, 255)
INK2 = (148, 160, 190)
FONTS = r"C:\Windows\Fonts"
_font_cache = {}


def font(size, bold=True):
    """Bahnschrift: il carattere "tecnico" che c'e' su tutti i Windows 10/11."""
    k = ("b", size, bold)
    if k not in _font_cache:
        try:
            f = ImageFont.truetype(os.path.join(FONTS, "bahnschrift.ttf"), size)
            f.set_variation_by_name("SemiBold" if bold else "Regular")
        except Exception:
            try:
                f = ImageFont.truetype(os.path.join(FONTS, "segoeuib.ttf" if bold else "segoeui.ttf"), size)
            except OSError:
                f = ImageFont.load_default()
        _font_cache[k] = f
    return _font_cache[k]


def font_mono(size):
    k = ("m", size)
    if k not in _font_cache:
        try:
            _font_cache[k] = ImageFont.truetype(os.path.join(FONTS, "consola.ttf"), size)
        except OSError:
            _font_cache[k] = font(size, False)
    return _font_cache[k]


POPUP = False          # True quando la ruota compare da sola sopra il mouse
KEY = (1, 2, 3)        # colore reso trasparente in modalità popup
KEYHEX = "#010203"
R_PIATTO = R_OUT + 44  # raggio del disco scuro in modalità popup
_maschera = None


def maschera_piatto():
    global _maschera
    if _maschera is None:
        _maschera = Image.new("L", (W * S, H * S), 0)
        r = R_PIATTO * S
        ImageDraw.Draw(_maschera).ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], fill=255)
    return _maschera


def bagliore(img, layer):
    """Aggiunge un bagliore; in popup lo taglia dentro il disco per non sporcare la trasparenza."""
    if POPUP:
        vuoto = Image.new("RGBA", layer.size, (0, 0, 0, 0))
        layer = Image.composite(layer, vuoto, maschera_piatto())
    img.alpha_composite(layer)


def font_simboli(size):
    try:
        return ImageFont.truetype(os.path.join(FONTS, "seguisym.ttf"), size)
    except OSError:
        return font(size)


def _cerchio(d, r, **kw):
    d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], **kw)


def _mescola(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def sfondo():
    """Disco di vetro scuro: ombra morbida, riflesso in alto, bordo sottilissimo."""
    n = (W * S, H * S)
    if not POPUP:
        img = Image.new("RGBA", n, BG + (255,))
    else:
        img = Image.new("RGBA", n, (0, 0, 0, 0))
        ombra = Image.new("RGBA", n, (0, 0, 0, 0))
        dd = ImageDraw.Draw(ombra)
        r = (R_PIATTO - 6) * S
        dd.ellipse([CX * S - r, CY * S - r + 8 * S, CX * S + r, CY * S + r + 8 * S], fill=(0, 0, 0, 120))
        img.alpha_composite(ombra.filter(ImageFilter.GaussianBlur(9 * S)))
        disco = Image.new("RGBA", n, (0, 0, 0, 0))
        _cerchio(ImageDraw.Draw(disco), R_PIATTO * S, fill=BG + (244,))
        img.alpha_composite(disco)
    # riflesso: luce che scende dall'alto del disco
    luce = Image.new("RGBA", n, (0, 0, 0, 0))
    r = 240 * S
    ImageDraw.Draw(luce).ellipse([CX * S - r, CY * S - r - 150 * S, CX * S + r, CY * S + r - 150 * S], fill=(120, 140, 200, 34))
    bagliore(img, luce.filter(ImageFilter.GaussianBlur(60 * S)))
    if POPUP:
        d = ImageDraw.Draw(img)
        _cerchio(d, (R_PIATTO - 0.5) * S, outline=(255, 255, 255, 34), width=S)
        _cerchio(d, (R_PIATTO - 1.5) * S, outline=(0, 0, 0, 90), width=S)
    return img


def settore(a0, a1, r1, r2, passi=40):
    pts = []
    for k in range(passi + 1):
        a = math.radians(a0 + (a1 - a0) * k / passi)
        pts.append((CX * S + r2 * S * math.cos(a), CY * S + r2 * S * math.sin(a)))
    for k in range(passi, -1, -1):
        a = math.radians(a0 + (a1 - a0) * k / passi)
        pts.append((CX * S + r1 * S * math.cos(a), CY * S + r1 * S * math.sin(a)))
    return pts


def fetta_tonda(a0, a1, r1, r2, raggio=7):
    """Maschera di una fetta con gli angoli arrotondati: sfoco e ritaglio a meta' (bordi lisci)."""
    m = Image.new("L", (W * S, H * S), 0)
    ImageDraw.Draw(m).polygon(settore(a0, a1, r1, r2, passi=60), fill=255)
    x0, y0, x1, y1 = m.getbbox()
    pad = raggio * 3 * S
    box = (max(0, x0 - pad), max(0, y0 - pad), min(m.width, x1 + pad), min(m.height, y1 + pad))
    pezzo = m.crop(box).filter(ImageFilter.GaussianBlur(raggio * S))
    pezzo = pezzo.point(lambda v: max(0, min(255, (v - 128) * 6 + 128)))
    m.paste(pezzo, box[:2])
    return m


_neutre = {}


def _geometria(n, i, attiva=False):
    passo = 360 / n
    gap = (5.0 / ((R_IN + R_OUT) / 2)) * 180 / math.pi if n > 1 else 0  # stacco costante di ~5 px
    a0 = -90 + i * passo - passo / 2 + gap / 2
    return a0, a0 + passo - gap, R_IN + 10, R_OUT + (6 if attiva else 0)


def _maschera_fetta(n, a0, a1, r1, r2):
    if n > 1:
        return fetta_tonda(a0, a1, r1, r2)
    m = Image.new("L", (W * S, H * S), 0)
    _cerchio(ImageDraw.Draw(m), r2 * S, fill=255)
    _cerchio(ImageDraw.Draw(m), r1 * S, fill=0)
    return m


def _scritte(img, n, i, key, testo, sub, col=None, spenta=False):
    a0, a1, r1, r2 = _geometria(n, i, attiva=col is None)
    am = math.radians((a0 + a1) / 2)
    rm = (r1 + r2) / 2 * S
    tx, ty = CX * S + rm * math.cos(am), CY * S + rm * math.sin(am)
    d = ImageDraw.Draw(img)
    d.text((tx, ty - 7 * S), ETICHETTE.get(key, key.upper()), font=font(int((21 if n <= 8 else 18) * S)), fill=testo, anchor="mm")
    d.text((tx, ty + 14 * S), SOTTOTITOLI.get(key, ""), font=font(int(11 * S), bold=False), fill=sub, anchor="mm")
    if col is not None:
        # puntino del colore del tipo
        q = 2.6 * S
        px, py = tx, ty - 27 * S  # sopra l'etichetta
        d.ellipse([px - q, py - q, px + q, py + q], fill=col + (70 if spenta else 230,))


def _nucleo(img, colori, spenta):
    d = ImageDraw.Draw(img)
    _cerchio(d, (R_IN - 2) * S, fill=(9, 11, 19, 255))
    unico = len(set(colori)) == 1
    c1, c2 = (colori[0], _mescola(colori[0], (255, 255, 255), 0.35)) if unico else (ACC, ACC2)
    r = (R_IN - 2) * S
    for k in range(180):
        t = abs(((k / 180) * 2) - 1)
        d.arc([CX * S - r, CY * S - r, CX * S + r, CY * S + r], k * 2 - 90, k * 2 - 87.5,
              fill=_mescola(c1, c2, t) + (90 if spenta else 210,), width=int(1.6 * S))


def _ruota_neutra(base, opzioni, colori, spenta):
    """Tutte le fette a riposo (vetro, bordo sottile, scritte, puntino): si disegna una volta sola."""
    k = (id(base), tuple(opzioni), tuple(colori), spenta)
    if k not in _neutre:
        if len(_neutre) > 24:
            _neutre.clear()
        n = len(opzioni)
        img = base.copy()
        unione = Image.new("L", img.size, 0)
        for i in range(n):
            a0, a1, r1, r2 = _geometria(n, i)
            unione.paste(255, mask=_maschera_fetta(n, a0, a1, r1, r2))
        vetro = Image.new("RGBA", img.size, (255, 255, 255, 0))
        vetro.putalpha(unione.point(lambda v: v * (8 if spenta else 14) // 255))
        img.alpha_composite(vetro)
        linea = Image.new("RGBA", img.size, (255, 255, 255, 0))
        linea.putalpha(unione.filter(ImageFilter.FIND_EDGES).point(lambda v: min(255, v) * (14 if spenta else 26) // 255))
        img.alpha_composite(linea)
        for i, key in enumerate(opzioni):
            _scritte(img, n, i, key, INK + (90 if spenta else 240,), INK2 + (80 if spenta else 255,), colori[i], spenta)
        _nucleo(img, colori, spenta)
        _neutre[k] = img
    return _neutre[k]


def disegna_ruota(base, opzioni, colore, hover, spenta=False):
    """`colore` e' un colore unico oppure una lista (un colore per fetta)."""
    colori = colore if isinstance(colore, list) else [colore] * len(opzioni)
    img = _ruota_neutra(base, opzioni, colori, spenta)
    if hover is None or spenta:
        return img.resize((ZW, ZH), Image.LANCZOS)
    img = img.copy()
    n, col = len(opzioni), colori[hover]
    a0, a1, r1, r2 = _geometria(n, hover, attiva=True)
    maschera = _maschera_fetta(n, a0, a1, r1, r2)
    x0, y0, x1, y1 = maschera.getbbox()
    pad = 40 * S
    box = (max(0, x0 - pad), max(0, y0 - pad), min(img.width, x1 + pad), min(img.height, y1 + pad))
    # lavoro solo nel riquadro della fetta: molto piu' veloce
    m = maschera.crop(box)
    pezzo = img.crop(box)
    glow = Image.new("RGBA", m.size, col + (0,))
    glow.putalpha(m.point(lambda v: v * 150 // 255))
    pezzo.alpha_composite(glow.filter(ImageFilter.GaussianBlur(16 * S)))
    sf = Image.new("RGBA", m.size, (0, 0, 0, 0))
    ds = ImageDraw.Draw(sf)
    cx, cy = CX * S - box[0], CY * S - box[1]
    for k in range(24, -1, -1):
        t = k / 24
        rr = (r1 + (r2 - r1) * t) * S
        c = _mescola(_mescola(col, (0, 0, 0), 0.18), _mescola(col, (255, 255, 255), 0.22), t)
        ds.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=c + (255,))
    pezzo.paste(sf, (0, 0), m)
    img.paste(pezzo, box[:2])
    _scritte(img, n, hover, opzioni[hover], (12, 14, 24, 255), (12, 14, 24, 190))
    _nucleo(img, colori, spenta)
    return img.resize((ZW, ZH), Image.LANCZOS)


def disegna_attesa(base, evidenzia=False):
    img = base.copy()
    d = ImageDraw.Draw(img)
    _cerchio(d, (R_IN - 2) * S, fill=(9, 11, 19, 255), outline=ACC + (200 if evidenzia else 110,), width=int(1.6 * S))
    r = R_OUT * S
    for k in range(120):
        t = abs(((k / 120) * 2) - 1)
        d.arc([CX * S - r, CY * S - r, CX * S + r, CY * S + r], k * 3, k * 3 + 1.6,
              fill=_mescola(ACC, ACC2, t) + (170 if evidenzia else 60,), width=2 * S)
    if evidenzia:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        _cerchio(ImageDraw.Draw(glow), R_OUT * S, outline=ACC + (200,), width=8 * S)
        bagliore(img, glow.filter(ImageFilter.GaussianBlur(14 * S)))
    return img.resize((ZW, ZH), Image.LANCZOS)


def barra_scura(root):
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


def leggi_appunti():
    """Cosa c'e' negli appunti: ("immagine", img), ("file", [percorsi]) oppure None."""
    try:
        from PIL import ImageGrab
        c = ImageGrab.grabclipboard()
    except Exception:
        return None
    if isinstance(c, Image.Image):
        return "immagine", c
    if isinstance(c, list):
        files = espandi([f for f in c if isinstance(f, str)])[0]
        if files:
            return "file", files
    return None


def accorcia(testo, n=26):
    return testo if len(testo) <= n else testo[: n - 1] + "…"


# ----------------------------------------------------------------- app
class App:
    def __init__(self, root, iniziali):
        self.root = root
        root.title("Convertitore")
        if POPUP:
            # niente finestra: solo la ruota, centrata sul mouse, sopra a tutto
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            px, py = root.winfo_pointerxy()
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            x = min(max(px - CX * Z, -(CX - R_PIATTO) * Z), sw - (CX + R_PIATTO) * Z)
            y = min(max(py - CY * Z, -(CY - R_PIATTO) * Z), sh - (CY + R_PIATTO) * Z - 48 * Z)
            root.geometry(f"{ZW}x{ZH}+{int(x)}+{int(y)}")
        else:
            root.geometry(f"{ZW}x{ZH}")
        root.resizable(False, False)
        root.configure(bg="#0e111b")
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convertitore.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)
        if not POPUP:
            barra_scura(root)

        self.cv = tk.Canvas(root, width=ZW, height=ZH, bg=KEYHEX if POPUP else "#0e111b", highlightthickness=0)
        self.cv.pack()
        self.base = sfondo()
        self.img_id = self.cv.create_image(0, 0, anchor="nw")
        self.titolo = self.cv.create_text((W / 2) * Z, (40) * Z, text="C O N V E R T I T O R E", fill="#f1f5ff", font=("Bahnschrift SemiBold", -int(20 * Z)))
        self.sotto = self.cv.create_text((W / 2) * Z, (66) * Z, text="", fill="#94a0be", font=("Bahnschrift", -int(13 * Z)))
        self.c1 = self.cv.create_text((CX) * Z, (CY - 22) * Z, text="", fill="#f1f5ff", font=("Bahnschrift SemiBold", -int(17 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.c2 = self.cv.create_text((CX) * Z, (CY + 8) * Z, text="", fill="#94a0be", font=("Bahnschrift", -int(13 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.c3 = self.cv.create_text((CX) * Z, (CY + 32) * Z, text="", fill="#94a0be", font=("Bahnschrift", -int(12 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.piede = self.cv.create_text((W / 2) * Z, (H - 22) * Z, text="", fill="#6b7694", font=("Bahnschrift", -int(12 * Z)))

        self.cv.drop_target_register(DND_FILES)
        self.cv.dnd_bind("<<DropEnter>>", lambda e: self._attesa(True) if self.stato == "attesa" else e.action)
        self.cv.dnd_bind("<<DropLeave>>", lambda e: self._ridisegna_stato())
        self.cv.dnd_bind("<<Drop>>", self._drop)
        self.cv.bind("<Motion>", self._muovi)
        self.cv.bind("<Button-1>", self._clic)
        self.cv.bind("<Button-3>", lambda e: self.reset())
        root.bind("<Escape>", lambda e: self._annulla() if self.stato == "lavoro" else self.reset())

        self.cache = {}
        self.hover = None
        self.stato = "attesa"
        self.files, self.cat, self.opz = [], None, []
        self.gruppo, self.appunti = None, None
        self.tutti, self.ignorati = None, 0
        self.risultati = []
        self.spin = None
        self.lavoro = None
        self.angolo = 0
        if POPUP:
            # finestra a strati: la disegna Windows con bordi morbidi veri
            import strati
            self.strati = strati
            self.opacita = 0.0
            self.scala = 1.0
            self.chiudendo = False
            self.animando, self._pronta = False, None
            self.corrente = None
            self.hwnd = strati.rendi_a_strati(root)
            for item in (self.titolo, self.sotto, self.piede):
                self.cv.itemconfigure(item, state="hidden")
            root.bind("<FocusOut>", lambda e: root.after(200, self._perso_fuoco))
            if iniziali:
                self.carica(iniziali)
            else:
                self._panoramica()
                self._sorveglia()
            self._anima(+1, self.root.focus_force)
        else:
            self.reset()
            if iniziali:
                root.after(100, lambda: self.carica(iniziali))

    # -- modalità popup
    def _anima(self, verso, fine=None):
        """Apertura (+1): la ruota cresce dal centro con un leggero rimbalzo e compare.
        Chiusura (-1): si ritira e svanisce.
        Prima prepara il fotogramma (la parte lenta), poi fa partire l'orologio: cosi'
        l'animazione si vede tutta, anche se il primo disegno richiede tempo."""
        durata = 0.42 if verso > 0 else 0.28
        self.animando, self._pronta = True, None
        if verso > 0:
            self.scala, self.opacita = 0.6, 0.0
        self._presenta()  # prepara l'immagine (con opacita' 0 in apertura: ancora invisibile)

        def parti():
            t0 = time.perf_counter()

            def passo():
                t = min(1.0, (time.perf_counter() - t0) / durata)
                if verso > 0:
                    c1 = 1.3                            # "rimbalzo": supera di poco e torna
                    e = 1 + (c1 + 1) * (t - 1) ** 3 + c1 * (t - 1) ** 2
                    self.scala = 0.6 + 0.4 * e
                    self.opacita = min(1.0, t * 2.2)
                else:
                    e = t * t * (3 - 2 * t)             # parte piano, accelera, si ferma dolce
                    self.scala = 1 - 0.25 * e
                    self.opacita = 1 - e
                self._presenta()
                if t < 1:
                    self.root.after(4, passo)
                    return
                self.animando, self._pronta = False, None
                self.scala = 1.0
                if fine:
                    fine()
            passo()
        if verso > 0:
            # aspetta che Windows abbia davvero mostrato la finestra
            self.root.after(30, lambda: self._quando_visibile(parti))
        else:
            parti()

    def _quando_visibile(self, poi, tentativi=40):
        try:
            if ctypes.windll.user32.IsWindowVisible(self.hwnd) or tentativi <= 0:
                poi()
            else:
                self.root.after(10, lambda: self._quando_visibile(poi, tentativi - 1))
        except tk.TclError:
            pass

    def _perso_fuoco(self):
        try:
            if POPUP and self.stato not in ("lavoro", "panoramica", "categoria") and self.root.focus_get() is None:
                self.chiudi()
        except (tk.TclError, KeyError):
            pass

    def chiudi(self):
        def distruggi():
            try:
                self.root.destroy()
            except tk.TclError:
                pass
        if not POPUP or self.corrente is None:
            distruggi()
            return
        if self.chiudendo:
            return
        self.chiudendo = True
        self._anima(-1, distruggi)

    def _sopra_ruota(self):
        px, py = self.root.winfo_pointerxy()
        x = (px - self.root.winfo_rootx()) / Z
        y = (py - self.root.winfo_rooty()) / Z
        return math.hypot(x - CX, y - CY) < R_PIATTO

    def _chiudi_dopo(self):
        """Chiude la ruota a lavoro finito, ma non finché il mouse ci sta sopra."""
        try:
            if self._sopra_ruota():
                self.root.after(700, self._chiudi_dopo)
            else:
                self.chiudi()
        except tk.TclError:
            pass

    # -- stati
    def _mostra(self, pil):
        if POPUP:
            self.corrente, self._pronta = pil, None
            self._presenta()
            return
        self.tkimg = ImageTk.PhotoImage(pil)
        self.cv.itemconfigure(self.img_id, image=self.tkimg)

    def _presenta(self):
        """Popup: compone ruota + scritte centrali + rotellina e la passa a Windows."""
        if not POPUP or self.corrente is None:
            return
        if self.animando and self._pronta is not None:
            self._fotogramma(self._pronta)  # animazione: immagine gia' pronta, solo da ridimensionare
            return
        img = self.corrente.copy()
        d = ImageDraw.Draw(img)
        blocchi = []
        for item, dim, gr in ((self.c1, 17, True), (self.c2, 13, False), (self.c3, 12, False)):
            testo = self.cv.itemcget(item, "text")
            if not testo:
                continue
            f = font(int(dim * Z), bold=gr)
            colore = self.cv.itemcget(item, "fill")
            righe = []
            for par in testo.split("\n"):
                riga = ""
                for parola in par.split(" "):
                    prova = (riga + " " + parola).strip()
                    if riga and d.textlength(prova, font=f) > 180 * Z:
                        righe.append(riga)
                        riga = parola
                    else:
                        riga = prova
                righe.append(riga)
            alt_riga = int(dim * Z * 1.32)
            blocchi.append((righe, f, colore, alt_riga))
        gap = 6 * Z
        totale = sum(len(b[0]) * b[3] for b in blocchi) + gap * max(0, len(blocchi) - 1)
        y = CY * Z - totale / 2
        for righe, f, colore, alt_riga in blocchi:
            for riga in righe:
                cy_riga = y + alt_riga / 2
                if riga[:1] in ("✓", "⚠"):
                    # simbolo col font dei simboli (Segoe UI non ce l'ha), poi il resto
                    simbolo, resto = riga[0], riga[1:]
                    fs = font_simboli(f.size)
                    ls, lr = d.textlength(simbolo, font=fs), d.textlength(resto, font=f)
                    x0 = CX * Z - (ls + lr) / 2
                    d.text((x0, cy_riga), simbolo, font=fs, fill=colore, anchor="lm")
                    d.text((x0 + ls, cy_riga), resto, font=f, fill=colore, anchor="lm")
                else:
                    d.text((CX * Z, cy_riga), riga, font=f, fill=colore, anchor="mm")
                y += alt_riga
            y += gap
        if self.stato == "lavoro":
            # anello disegnato in alta risoluzione e poi ridotto: bordi lisci
            r = R_IN - 12
            k = 3
            lato = int((2 * r + 8) * Z)
            strato = Image.new("RGBA", (lato * k, lato * k), (0, 0, 0, 0))
            m = 4 * Z * k
            dd = ImageDraw.Draw(strato)
            col = COLORI[self.cat]
            frazione = self.lavoro.frazione if self.lavoro else None
            if frazione is None:
                # non si sa quanto manca: rotellina
                dd.arc([m, m, lato * k - m, lato * k - m], -self.angolo - 80, -self.angolo, fill=col + (255,), width=int(3 * Z * k))
            else:
                # quanto manca: binario tenue + arco pieno che cresce in senso orario dall'alto
                dd.arc([m, m, lato * k - m, lato * k - m], 0, 360, fill=col + (40,), width=int(3 * Z * k))
                if frazione > 0.002:
                    dd.arc([m, m, lato * k - m, lato * k - m], -90, -90 + 360 * frazione, fill=col + (255,), width=int(3 * Z * k))
            strato = strato.resize((lato, lato), Image.LANCZOS)
            img.alpha_composite(strato, (int(CX * Z - lato / 2), int(CY * Z - lato / 2)))
        if self.animando:
            # preparata una volta (gia' nel formato di Windows), poi ogni fotogramma la ridimensiona e basta
            self._pronta = Image.frombytes("RGBA", img.size, self.strati.premoltiplica(img))
            self._fotogramma(self._pronta)
            return
        try:
            self.strati.disegna(self.hwnd, img, self.opacita)
        except Exception:
            pass

    def _fotogramma(self, pronta):
        """Apertura/chiusura: ruota in scala attorno al suo centro, con dissolvenza."""
        img = pronta
        if abs(self.scala - 1) > 0.001:
            w, h = pronta.size
            nw, nh = max(1, round(w * self.scala)), max(1, round(h * self.scala))
            piccola = pronta.resize((nw, nh), Image.BILINEAR)
            ox, oy = round(CX * Z * (1 - self.scala)), round(CY * Z * (1 - self.scala))
            img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            if self.scala < 1:
                img.paste(piccola, (ox, oy))
            else:  # rimbalzo oltre il 100%: si ritaglia al centro
                img.paste(piccola.crop((-ox, -oy, -ox + w, -oy + h)), (0, 0))
        try:
            self.strati.disegna(self.hwnd, img, self.opacita, img.tobytes())
        except Exception:
            pass

    def _testi(self, a="", b="", c="", sotto="", piede=""):
        self._pronta = None
        self.cv.itemconfigure(self.c1, text=a, fill="#f1f5ff")
        self.cv.itemconfigure(self.c2, text=b)
        self.cv.itemconfigure(self.c3, text=c)
        self.cv.itemconfigure(self.sotto, text=sotto)
        self.cv.itemconfigure(self.piede, text=piede)
        self._impila()

    def _impila(self):
        """Dispone le tre righe centrali una sotto l'altra, centrate."""
        righe = [i for i in (self.c1, self.c2, self.c3) if self.cv.itemcget(i, "text")]
        alt = [self.cv.bbox(i)[3] - self.cv.bbox(i)[1] for i in righe]
        gap = 6 * Z
        y = CY * Z - (sum(alt) + gap * (len(righe) - 1)) / 2
        for i, h in zip(righe, alt):
            self.cv.coords(i, CX * Z, y)
            y += h + gap
        self._presenta() if POPUP else None

    def _attesa(self, evidenzia=False):
        key = ("attesa", evidenzia)
        if key not in self.cache:
            self.cache[key] = disegna_attesa(self.base, evidenzia)
        self._mostra(self.cache[key])

    def _ridisegna_stato(self):
        if self.stato == "attesa":
            self._attesa(False)
        elif self.stato in ("ruota", "panoramica", "categoria", "tipi"):
            self._ruota()

    # -- ruota senza file (clic sulla sfera senza niente di selezionato)
    def _panoramica(self):
        self.stato, self.cat, self.opz, self.hover = "panoramica", None, list(PANORAMICA), None
        if self.appunti is None:
            self.appunti = leggi_appunti() or False
        if self.appunti:
            # c'e' uno screenshot (o dei file copiati): fetta in piu' per convertirli subito
            SOTTOTITOLI["appunti"] = t("screenshot") if self.appunti[0] == "immagine" else t("{n} file copiati", n=len(self.appunti[1]))
            self.opz.append("appunti")
        self._ruota()
        self._testi(t("Cosa converti?"), t("scegli un tipo, oppure\ntrascina qui il file"))

    def _categoria(self, cat):
        self.stato, self.cat, self.opz, self.hover = "categoria", cat, list(DESTINAZIONI[cat]), None
        self._ruota()
        self._testi(ETICHETTE["cat:" + cat].capitalize(), t("trascina qui\n{cosa}", cosa=NOMI_TIPO[cat]), t("clic qui per tornare"))

    def _sorveglia(self):
        """Ruota senza file: resta aperta mentre trascini un file verso di lei,
        si chiude se clicchi altrove."""
        if self.stato not in ("panoramica", "categoria"):
            return
        try:
            premuto = ctypes.windll.user32.GetAsyncKeyState(0x01) & 0x8000
            if self.root.focus_get() is None and not premuto and not self._sopra_ruota() and self.opacita >= 1:
                self.chiudi()
                return
            self.root.after(400, self._sorveglia)
        except (tk.TclError, KeyError):
            pass

    def reset(self):
        if self.stato == "lavoro":
            return
        if POPUP:
            self.chiudi()
            return
        self.stato = "attesa"
        self.files, self.risultati = [], []
        self.hover = None
        self.cv.configure(cursor="")
        self._attesa(False)
        self._testi(t("Trascina qui\ni tuoi file"), t("immagini · video · audio\nPDF · Word · Excel"),
                    sotto="", piede=t("Rilascia uno o più file per vedere le conversioni"))

    def _ruota(self, spenta=False):
        key = ("ruota", tuple(self.opz), self.cat, self.hover, spenta)
        colore = COLORI[self.cat] if self.cat else [COLORI[k[4:] if k.startswith("cat:") else k] for k in self.opz]
        if key not in self.cache:
            if len(self.cache) > 60:
                self.cache = {k: v for k, v in self.cache.items() if k[0] == "attesa"}
            self.cache[key] = disegna_ruota(self.base, self.opz, colore, self.hover, spenta)
        self._mostra(self.cache[key])

    def carica(self, files, nome=None, da_tipi=False):
        if self.stato == "lavoro":
            return
        self.nome_mostrato = nome
        if not da_tipi:
            files, self.ignorati = espandi(files)
            self.tutti = None
        if not files:
            if not self.ignorati:  # niente da convertire (file spariti): chiudo e basta
                self.root.after(10, self.chiudi) if POPUP else self.reset()
                return
            if POPUP:
                self.stato = "fatto"
                self._attesa(False)
                self.root.after(2500, self.chiudi)
            else:
                self.reset()
            self._testi(t("Formato non supportato"), t("{n} file che non so convertire", n=self.ignorati),
                        piede=t("Esc per ricominciare"))
            return
        cats = {categoria(f) for f in files}
        if len(cats) > 1:
            self._tipi(files)
            return
        cat, opz = opzioni_per(files)
        if not opz:
            if POPUP:
                self.stato = "fatto"
                self._attesa(False)
                self.root.after(3500, self.chiudi)
            self._testi(t("Serve Microsoft Office"), t("per convertire {cosa}", cosa=NOMI_TIPO.get(cat, cat)),
                        piede=t("Esc per ricominciare"))
            return
        self.files, self.cat, self.opz, self.principali, self.gruppo = files, cat, opz, opz, None
        self.stato, self.hover = "ruota", None
        self._ruota()
        self._testi_file()

    def _tipi(self, files):
        """File di tipi diversi (o una cartella): prima scegli quali convertire."""
        self.tutti = files
        conta = {}
        for f in files:
            conta[categoria(f)] = conta.get(categoria(f), 0) + 1
        opz = [f"cat:{c}" for c in CATEGORIE if c in conta]
        for c in conta:
            SOTTOTITOLI[f"cat:{c}"] = t("{n} file", n=conta[c])
        if "immagine" in conta and "pdf" in conta:
            opz.append("unisci")  # foto e PDF tutti insieme in un PDF
        self.files, self.cat, self.opz, self.gruppo = files, None, opz, None
        self.stato, self.hover = "tipi", None
        self._ruota()
        extra = t("{n} non supportati, ignorati", n=self.ignorati) if self.ignorati else t("scegli cosa convertire")
        self._testi(t("{n} file", n=len(files)), t("di tipi diversi"), extra,
                    piede=t("Scegli un tipo  ·  Esc per annullare"))

    def _testi_file(self):
        files, cat = self.files, self.cat
        tipo = t("immagini e PDF") if cat == "unione" else NOMI_CAT.get(cat, cat)
        if len(files) == 1:
            nome = self.nome_mostrato or os.path.basename(files[0])
            a, b = accorcia(nome, 22), f"{tipo}  ·  {self._peso(files[0])}"
        else:
            a, b = t("{n} file", n=len(files)), tipo
        c = t("clic qui per tornare") if self.gruppo or self.tutti else t("scegli il formato")
        if not self.gruppo and not self.tutti and getattr(self, "ignorati", 0):
            c = t("{n} non supportati, ignorati", n=self.ignorati)
        if self.gruppo:
            a = ETICHETTE[self.gruppo].capitalize()
        self._testi(a, b, c, sotto=t("{n} conversioni possibili", n=len(self.opz)),
                    piede=t("Clicca un formato  ·  Esc o tasto destro per annullare"))

    @staticmethod
    def _peso(f):
        n = os.path.getsize(f)
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} TB"

    # -- eventi
    def _drop(self, e):
        self.carica(list(self.root.tk.splitlist(e.data)))
        if POPUP:
            self.root.focus_force()
        return e.action

    def _indice(self, x, y):
        dx, dy = x - CX, y - CY
        r = math.hypot(dx, dy)
        if not (R_IN <= r <= R_OUT + 14):
            return None
        ang = (math.degrees(math.atan2(dy, dx)) + 90) % 360
        passo = 360 / len(self.opz)
        return int(((ang + passo / 2) % 360) // passo)

    def _muovi(self, e):
        e.x, e.y = e.x / Z, e.y / Z
        if self.stato in ("ruota", "panoramica", "categoria", "tipi"):
            h = self._indice(e.x, e.y)
            if h != self.hover:
                self.hover = h
                self.cv.configure(cursor="hand2" if h is not None else "")
                self._ruota()
        elif self.stato == "fatto":
            dentro = math.hypot(e.x - CX, e.y - CY) < R_IN
            self.cv.configure(cursor="hand2" if dentro and self.risultati else "")
        elif self.stato == "lavoro":
            dentro = math.hypot(e.x - CX, e.y - CY) < R_IN
            self.cv.configure(cursor="hand2" if dentro else "watch")

    def _clic(self, e):
        e.x, e.y = e.x / Z, e.y / Z
        centro = math.hypot(e.x - CX, e.y - CY) < R_IN
        if self.stato == "panoramica":
            i = self._indice(e.x, e.y)
            if i is not None and self.opz[i] == "appunti":
                self._usa_appunti()
            elif i is not None:
                self._categoria(self.opz[i][4:])
            elif not centro and math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "categoria":
            if centro:
                self._panoramica()
            elif self._indice(e.x, e.y) is not None:
                self._testi(self.etichetta_cat(), t("prima trascina qui\n{cosa}", cosa=NOMI_TIPO[self.cat]), t("clic qui per tornare"))
                self.cv.itemconfigure(self.c1, fill="#fbbf24")
                self._presenta() if POPUP else None
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "ruota":
            i = self._indice(e.x, e.y)
            if i is not None and self.opz[i].startswith("grp:"):
                # seconda ruota (misura, ruota, altri formati)
                self.gruppo = self.opz[i]
                self.opz, self.hover = opzioni_gruppo(self.cat, self.gruppo, self.files), None
                self._ruota()
                self._testi_file()
            elif i is not None:
                self._avvia(self.opz[i])
            elif centro and self.gruppo:
                self.gruppo, self.opz, self.hover = None, self.principali, None
                self._ruota()
                self._testi_file()
            elif centro and self.tutti:
                self._tipi(self.tutti)  # torna alla scelta del tipo
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "tipi":
            i = self._indice(e.x, e.y)
            if i is not None and self.opz[i] == "unisci":
                self.files = [f for f in self.tutti if categoria(f) in ("immagine", "pdf")]
                self.cat = "unione"
                self._avvia("unisci")
            elif i is not None:
                scelta = self.opz[i][4:]
                tutti = self.tutti
                self.carica([f for f in tutti if categoria(f) == scelta], da_tipi=True)
                self.tutti = tutti
                self._testi_file()
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "lavoro":
            if centro:
                self._annulla()
        elif self.stato == "fatto":
            if math.hypot(e.x - CX, e.y - CY) < R_IN and self.risultati:
                mostra_in_cartella(self.risultati)
                if POPUP:
                    self.chiudi()
            else:
                self.reset()

    def _usa_appunti(self):
        global CARTELLA_USCITA
        tipo, valore = self.appunti
        if tipo == "file":
            self.carica(valore)
            return
        # screenshot: lo salvo come BMP temporaneo, i file convertiti vanno sul Desktop
        cartella = os.path.join(os.environ.get("TEMP", cartella_desktop()), "Convertitore")
        os.makedirs(cartella, exist_ok=True)
        nome = t("Appunti") + time.strftime(" %Y-%m-%d %H.%M.%S")
        tmp = os.path.join(cartella, nome + ".bmp")
        su_bianco(valore).save(tmp, "BMP")
        fissa = IMP.get("cartella")
        CARTELLA_USCITA = fissa if fissa and os.path.isdir(fissa) else cartella_desktop()
        self.carica([tmp], nome=t("Immagine dagli appunti"))

    def etichetta_cat(self):
        return ETICHETTE["cat:" + self.cat].capitalize()

    # -- conversione
    def _avvia(self, key):
        self.stato = "lavoro"
        self.hover = None
        self.cv.configure(cursor="watch")
        self._ruota(spenta=True)
        self.etichetta = ETICHETTE.get(key, key.upper())
        if key in DESCRIZIONI:
            self._testi(DESCRIZIONI[key], "", "", piede=t("Clic al centro o Esc per annullare"))
        else:
            self._testi(t("Converto in {cosa}…", cosa=self.etichetta), "", "", piede=t("Clic al centro o Esc per annullare"))
        self.azione = key in AZIONI
        self.angolo = 0
        self.lavoro = Lavoro(len(self.files))
        self.cv.itemconfigure(self.c3, text=t("clic qui per annullare"))
        self._impila()
        self._ultimo_testo = None
        self._gira()
        threading.Thread(target=self._lavora, args=(key,), daemon=True).start()

    def _annulla(self):
        """Clic al centro o Esc mentre converte."""
        if self.stato != "lavoro" or self.lavoro is None or self.lavoro.annulla.is_set():
            return
        self.lavoro.ferma()
        self._testi(t("Annullo…"), "", "")
        self.cv.itemconfigure(self.c1, fill="#fbbf24")
        self._presenta() if POPUP else None

    def _testo_avanzamento(self):
        """Percentuale (e "2 di 5") sotto il titolo, aggiornata mentre lavora."""
        lv = self.lavoro
        if lv is None or lv.annulla.is_set():
            return
        righe = []
        if lv.frazione is not None:
            righe.append(f"{int(lv.frazione * 100)}%")
        if lv.n > 1:
            righe.append(f"{min(lv.i + 1, lv.n)} di {lv.n} · {accorcia(lv.nome, 18)}")
        testo = "\n".join(righe)
        if testo != self._ultimo_testo:
            self._ultimo_testo = testo
            self.cv.itemconfigure(self.c2, text=testo)
            self._impila()

    def _gira(self):
        if self.stato == "lavoro":
            self._testo_avanzamento()
        if POPUP:
            if self.stato == "lavoro":
                self.angolo = (self.angolo - 12) % 360
                self._presenta()
                self.root.after(33, self._gira)
            return
        if self.spin:
            self.cv.delete(self.spin)
        if self.stato != "lavoro":
            self.spin = None
            return
        col = "#%02x%02x%02x" % COLORI[self.cat]
        r = R_IN - 12
        self.spin = self.cv.create_arc((CX - r) * Z, (CY - r) * Z, (CX + r) * Z, (CY + r) * Z, start=self.angolo, extent=80,
                                       style="arc", outline=col, width=3 * Z)
        self.angolo = (self.angolo - 12) % 360
        self.root.after(30, self._gira)

    def _lavora(self, key):
        try:
            outs, errori = converti(self.files, self.cat, key, lavoro=self.lavoro)
        except Exception as ex:  # noqa: BLE001
            registra_errore(self.files[0] if self.files else "", key, ex)
            outs, errori = [], [messaggio(ex)]
        self.root.after(0, lambda: self._fine(outs, errori))

    def _fine(self, outs, errori):
        self.stato = "fatto"
        self.risultati = outs
        self.cv.configure(cursor="")
        self._ruota(spenta=True)
        annullato = self.lavoro is not None and self.lavoro.annulla.is_set()
        spostati = self.lavoro is not None and self.lavoro.spostati
        if annullato:
            self._testi(t("Annullato"), t("{n} file già pronti", n=len(outs)) if outs else t("nessun file creato"),
                        t("clicca qui per la cartella") if outs else "",
                        piede=t("Clicca fuori o premi Esc per ricominciare"))
            self.cv.itemconfigure(self.c1, fill="#fbbf24")
            self._presenta()
            if POPUP:
                self.root.after(2200, self._chiudi_dopo)
        elif outs and not errori:
            n = len(outs)
            self._testi("✓  " + t("Fatto"), (t("{n} file pronti", n=n) if self.azione else t("{n} file {cosa}", n=n, cosa=self.etichetta)) if n > 1
                        else accorcia(os.path.basename(outs[0]), 24),
                        t("salvato sul Desktop:\ncartella protetta") if spostati else t("clicca qui per\naprire la cartella"),
                        piede=t("Trascina altri file o clicca fuori per ricominciare"))
            self.cv.itemconfigure(self.c1, fill="#4ade80")
            self._presenta()
            if POPUP:
                self.root.after(2500, self._chiudi_dopo)
        else:
            msg = errori[0] if errori else t("nessun file creato")
            if len(errori) > 1:
                msg += t("\n(+ altri {n})", n=len(errori) - 1)
            self._testi("⚠  " + (t("Errore") if not outs else t("{n} errori", n=len(errori))), accorcia(msg, 110),
                        t("clicca qui per la cartella") if outs else "",
                        piede=t("Clicca fuori o premi Esc per ricominciare"))
            self.cv.itemconfigure(self.c1, fill="#fb7185")
            self._presenta()


PORTA = 47615


def raccogli(files):
    """Quando selezioni piu' file e scegli "Converti...", Windows avvia un processo per
    file. Il primo li raccoglie tutti (via una porta locale), gli altri escono."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        srv.bind(("127.0.0.1", PORTA))
    except OSError:
        srv.close()
        for _ in range(15):
            try:
                with socket.create_connection(("127.0.0.1", PORTA), timeout=1) as c:
                    c.sendall("\n".join(files).encode("utf-8"))
                return None
            except OSError:
                time.sleep(0.1)
        return files
    srv.listen(64)
    srv.settimeout(0.45)
    tutti = list(files)
    while True:
        try:
            conn, _ = srv.accept()
        except socket.timeout:
            break
        with conn:
            conn.settimeout(1)
            dati = b""
            while True:
                pezzo = conn.recv(65536)
                if not pezzo:
                    break
                dati += pezzo
        tutti += [f for f in dati.decode("utf-8").split("\n") if f]
    srv.close()
    visti, unici = set(), []
    for f in tutti:
        k = os.path.normcase(os.path.abspath(f))
        if k not in visti:
            visti.add(k)
            unici.append(f)
    return unici


def main():
    global POPUP
    files = sys.argv[1:]
    if files == ["--impostazioni"]:
        import impostazioni as finestra_imp
        finestra_imp.finestra()
        return
    if files == ["--ruota"]:
        files = []
        POPUP = True
    elif files:
        files = raccogli(files)
        if files is None:
            return
        POPUP = True
    root = TkinterDnD.Tk()
    App(root, files)
    root.mainloop()


if __name__ == "__main__":
    main()
