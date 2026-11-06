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
    if cat in ("immagine", "pdf") and len(files) > 1:
        opz.insert(0, "unisci")
    return cat, opz


def opzioni_gruppo(cat, gruppo, files):
    exts = {ALIAS.get(estensione(f), estensione(f)) for f in files}
    return _filtra(GRUPPI.get(cat, {}).get(gruppo, []), exts)


# ----------------------------------------------------------------- conversioni
def percorso_libero(cartella, nome, ext):
    out = os.path.join(cartella, f"{nome}.{ext}")
    n = 1
    while os.path.exists(out):
        out = os.path.join(cartella, f"{nome} ({n}).{ext}")
        n += 1
    return out


CARTELLA_USCITA = None  # se impostata (immagine dagli appunti) i file finiscono qui


def uscita(src, ext, suffisso=""):
    base = os.path.splitext(os.path.basename(src))[0] + suffisso
    return percorso_libero(CARTELLA_USCITA or os.path.dirname(src), base, ext)


def cartella_desktop():
    buf = ctypes.create_unicode_buffer(260)
    if ctypes.windll.shell32.SHGetFolderPathW(None, 0x10, None, 0, buf) == 0:  # CSIDL_DESKTOPDIRECTORY
        return buf.value
    return os.path.join(os.path.expanduser("~"), "Desktop")


def troppo_grande(src, out):
    """Per "leggero": se il risultato non pesa meno dell'originale non serve a niente."""
    if os.path.getsize(out) >= os.path.getsize(src) * 0.97:
        os.remove(out)
        raise RuntimeError("è già leggero, non si riduce di più")


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
        im.thumbnail((2560, 2560), Image.LANCZOS)
        if ha_trasparenza(im):
            out = uscita(src, "webp", " (leggera)")
            im.save(out, quality=80, method=6)
        else:
            out = uscita(src, "jpg", " (leggera)")
            su_bianco(im).save(out, "JPEG", quality=78, optimize=True, progressive=True)
        troppo_grande(src, out)
        return [out]
    if key == "r50":
        im = im.resize((max(1, im.width // 2), max(1, im.height // 2)), Image.LANCZOS)
        return [salva_come_originale(im, src, " (50%)")]
    if key == "r1920":
        if max(im.size) <= 1920:
            raise RuntimeError("è già più piccola di 1920 px")
        im.thumbnail((1920, 1920), Image.LANCZOS)
        return [salva_come_originale(im, src, " (1920)")]
    if key == "quadrata":
        im = ImageOps.fit(im, (1080, 1080), Image.LANCZOS)
        return [salva_come_originale(im, src, " (quadrata)")]
    if key == "dritta":
        # exif_transpose l'ha gia' raddrizzata
        return [salva_come_originale(im, src, " (dritta)")]
    gradi = {"destra": Image.Transpose.ROTATE_270, "sinistra": Image.Transpose.ROTATE_90,
             "r180": Image.Transpose.ROTATE_180}[key]
    return [salva_come_originale(im.transpose(gradi), src, " (ruotata)")]


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


def converti_pdf(src, key):
    import pymupdf
    if key == "word":
        # pdf2docx: funziona anche senza Office installato
        from pdf2docx import Converter
        out = uscita(src, "docx")
        cv = Converter(src)
        try:
            cv.convert(out)
        finally:
            cv.close()
        return [out]
    doc = pymupdf.open(src)
    if key == "leggero":
        out = uscita(src, "pdf", " (leggero)")
        try:
            doc.rewrite_images(dpi_threshold=160, dpi_target=130, quality=70)
        except Exception:
            pass  # PDF senza immagini: si guadagna solo dalla compressione
        try:
            doc.subset_fonts()
        except Exception:
            pass
        doc.save(out, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True)
        doc.close()
        troppo_grande(src, out)
        return [out]
    if key in ("destra", "sinistra", "r180"):
        delta = {"destra": 90, "sinistra": 270, "r180": 180}[key]
        for page in doc:
            page.set_rotation((page.rotation + delta) % 360)
        out = uscita(src, "pdf", " (ruotato)")
        doc.save(out, garbage=3, deflate=True)
        return [out]
    if key == "txt":
        out = uscita(src, "txt")
        with open(out, "w", encoding="utf-8") as fh:
            for i, page in enumerate(doc):
                if i:
                    fh.write("\n\n----- pagina %d -----\n\n" % (i + 1))
                fh.write(page.get_text())
        return [out]
    outs = []
    for i, page in enumerate(doc):
        suff = "" if len(doc) == 1 else f" - pagina {i + 1}"
        out = uscita(src, key, suff)
        pix = page.get_pixmap(dpi=170)
        if key == "jpg":
            pix.save(out, jpg_quality=90)
        else:
            pix.save(out)
        outs.append(out)
    return outs


def unisci_pdf(files):
    """Mette PDF e immagini (in ordine di nome) in un unico PDF."""
    import io
    import pymupdf
    from PIL import ImageOps
    files = sorted(files, key=chiave_nome)
    out_doc = pymupdf.open()
    for f in files:
        if categoria(f) == "pdf":
            with pymupdf.open(f) as d:
                out_doc.insert_pdf(d)
        else:
            buf = io.BytesIO()
            su_bianco(ImageOps.exif_transpose(Image.open(f))).save(buf, "PDF", resolution=150)
            with pymupdf.open("pdf", buf.getvalue()) as d:
                out_doc.insert_pdf(d)
    nome = "Immagini unite" if all(categoria(f) == "immagine" for f in files) else "PDF unito"
    out = percorso_libero(CARTELLA_USCITA or os.path.dirname(files[0]), nome, "pdf")
    out_doc.save(out, garbage=3, deflate=True)
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
# "leggero": video al massimo 1280 px (va bene per WhatsApp e email), audio MP3 a 96 kbps
LEGGERO_VIDEO = ["-vf", "scale=w='min(1280,iw)':h='min(1280,ih)':force_original_aspect_ratio=decrease:force_divisible_by=2",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "28", "-pix_fmt", "yuv420p",
                 "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart"]
LEGGERO_AUDIO = ["-vn", "-c:a", "libmp3lame", "-b:a", "96k"]


def converti_ffmpeg(src, key):
    ff = trova_ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg non trovato: installalo con  winget install Gyan.FFmpeg")
    if key == "leggero":
        video = categoria(src) == "video"
        out = uscita(src, "mp4" if video else "mp3", " (leggero)")
        argomenti = LEGGERO_VIDEO if video else LEGGERO_AUDIO
    else:
        out = uscita(src, key)
        argomenti = FFMPEG_ARGS[key]
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", src, *argomenti, out]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0:
        if os.path.exists(out):
            os.remove(out)
        raise RuntimeError((r.stderr or "errore ffmpeg").strip().splitlines()[-1])
    if key == "leggero":
        troppo_grande(src, out)
    return [out]


def converti_office(src, key, cat):
    import pythoncom
    import win32com.client as win32
    pythoncom.CoInitialize()
    src = os.path.abspath(src)
    out = uscita(src, key)
    try:
        if cat == "word":
            app = win32.DispatchEx("Word.Application")
            app.Visible = False
            app.DisplayAlerts = 0
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


def converti(files, cat, key, avanzamento):
    """Converte tutti i file. Restituisce (lista output, lista errori)."""
    if key == "unisci":
        return unisci_pdf(files), []
    outs, errori = [], []
    for i, f in enumerate(files):
        avanzamento(i, len(files), os.path.basename(f))
        try:
            if cat == "immagine":
                outs += converti_immagine(f, key)
            elif cat == "pdf":
                outs += converti_pdf(f, key)
            elif cat in ("video", "audio"):
                outs += converti_ffmpeg(f, key)
            else:
                outs += converti_office(f, key, cat)
        except Exception as e:  # noqa: BLE001
            errori.append(f"{os.path.basename(f)}: {e}")
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
        files = [f for f in c if isinstance(f, str) and os.path.isfile(f) and categoria(f)]
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
        root.bind("<Escape>", lambda e: self.reset())

        self.cache = {}
        self.hover = None
        self.stato = "attesa"
        self.files, self.cat, self.opz = [], None, []
        self.gruppo, self.appunti = None, None
        self.risultati = []
        self.spin = None
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
            # rotellina disegnata in alta risoluzione e poi ridotta: bordi lisci
            r = R_IN - 12
            k = 3
            lato = int((2 * r + 8) * Z)
            strato = Image.new("RGBA", (lato * k, lato * k), (0, 0, 0, 0))
            m = 4 * Z * k
            ImageDraw.Draw(strato).arc([m, m, lato * k - m, lato * k - m], -self.angolo - 80, -self.angolo,
                                       fill=COLORI[self.cat] + (255,), width=int(3 * Z * k))
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
        elif self.stato in ("ruota", "panoramica", "categoria"):
            self._ruota()

    # -- ruota senza file (clic sulla sfera senza niente di selezionato)
    def _panoramica(self):
        self.stato, self.cat, self.opz, self.hover = "panoramica", None, list(PANORAMICA), None
        if self.appunti is None:
            self.appunti = leggi_appunti() or False
        if self.appunti:
            # c'e' uno screenshot (o dei file copiati): fetta in piu' per convertirli subito
            SOTTOTITOLI["appunti"] = "screenshot" if self.appunti[0] == "immagine" else f"{len(self.appunti[1])} file copiati"
            self.opz.append("appunti")
        self._ruota()
        self._testi("Cosa converti?", "scegli un tipo, oppure\ntrascina qui il file")

    def _categoria(self, cat):
        self.stato, self.cat, self.opz, self.hover = "categoria", cat, list(DESTINAZIONI[cat]), None
        self._ruota()
        self._testi(ETICHETTE["cat:" + cat].capitalize(), f"trascina qui\n{NOMI_TIPO[cat]}", "clic qui per tornare")

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
        self._testi("Trascina qui\ni tuoi file", "immagini · video · audio\nPDF · Word · Excel",
                    sotto="", piede="Rilascia uno o più file per vedere le conversioni")

    def _ruota(self, spenta=False):
        key = ("ruota", tuple(self.opz), self.cat, self.hover, spenta)
        colore = COLORI[self.cat] if self.cat else [COLORI[k[4:] if k.startswith("cat:") else k] for k in self.opz]
        if key not in self.cache:
            if len(self.cache) > 60:
                self.cache = {k: v for k, v in self.cache.items() if k[0] == "attesa"}
            self.cache[key] = disegna_ruota(self.base, self.opz, colore, self.hover, spenta)
        self._mostra(self.cache[key])

    def carica(self, files, nome=None):
        if self.stato == "lavoro":
            return
        self.nome_mostrato = nome
        files = [f for f in files if os.path.isfile(f)]
        if not files:
            if POPUP:
                self.root.after(10, self.chiudi)
            else:
                self.reset()
            return
        cat, opz = opzioni_per(files)
        if not opz:
            if POPUP:
                self.stato = "fatto"
                self._attesa(False)
                self.root.after(2500, self.chiudi)
            else:
                self.reset()
            if cat == "misto":
                self._testi("File di tipo diverso", "Trascina file dello\nstesso tipo insieme", piede="Esc per ricominciare")
            else:
                ext = estensione(files[0]) or "?"
                self._testi("Formato non supportato", f".{ext}", piede="Esc per ricominciare")
            return
        self.files, self.cat, self.opz, self.principali, self.gruppo = files, cat, opz, opz, None
        self.stato, self.hover = "ruota", None
        self._ruota()
        self._testi_file()

    def _testi_file(self):
        files, cat = self.files, self.cat
        tipo = "immagini e PDF" if cat == "unione" else cat
        if len(files) == 1:
            nome = self.nome_mostrato or os.path.basename(files[0])
            a, b = accorcia(nome, 22), f"{tipo}  ·  {self._peso(files[0])}"
        else:
            a, b = f"{len(files)} file", tipo
        c = "clic qui per tornare" if self.gruppo else "scegli il formato"
        if self.gruppo:
            a = ETICHETTE[self.gruppo].capitalize()
        self._testi(a, b, c, sotto=f"{len(self.opz)} conversioni possibili",
                    piede="Clicca un formato  ·  Esc o tasto destro per annullare")

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
        if self.stato in ("ruota", "panoramica", "categoria"):
            h = self._indice(e.x, e.y)
            if h != self.hover:
                self.hover = h
                self.cv.configure(cursor="hand2" if h is not None else "")
                self._ruota()
        elif self.stato == "fatto":
            dentro = math.hypot(e.x - CX, e.y - CY) < R_IN
            self.cv.configure(cursor="hand2" if dentro and self.risultati else "")

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
                self._testi(self.etichetta_cat(), f"prima trascina qui\n{NOMI_TIPO[self.cat]}", "clic qui per tornare")
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
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
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
        nome = time.strftime("Appunti %Y-%m-%d %H.%M.%S")
        tmp = os.path.join(cartella, nome + ".bmp")
        su_bianco(valore).save(tmp, "BMP")
        CARTELLA_USCITA = cartella_desktop()
        self.carica([tmp], nome="Immagine dagli appunti")

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
            self._testi(DESCRIZIONI[key], "", "", piede="Attendi, non chiudere la finestra")
        else:
            self._testi("Converto…", f"in {self.etichetta}", "", piede="Attendi, non chiudere la finestra")
        self.azione = key in AZIONI
        self.angolo = 0
        self._gira()
        threading.Thread(target=self._lavora, args=(key,), daemon=True).start()

    def _gira(self):
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
        def avanz(i, n, nome):
            if n > 1:
                def aggiorna():
                    self.cv.itemconfigure(self.c3, text=f"{i + 1} di {n}\n{accorcia(nome, 24)}")
                    self._impila()
                self.root.after(0, aggiorna)
        try:
            outs, errori = converti(self.files, self.cat, key, avanz)
        except Exception as ex:  # noqa: BLE001
            outs, errori = [], [str(ex)]
        self.root.after(0, lambda: self._fine(outs, errori))

    def _fine(self, outs, errori):
        self.stato = "fatto"
        self.risultati = outs
        self.cv.configure(cursor="")
        self._ruota(spenta=True)
        if outs and not errori:
            n = len(outs)
            self._testi("✓  Fatto", (f"{n} file pronti" if self.azione else f"{n} file {self.etichetta}") if n > 1
                        else accorcia(os.path.basename(outs[0]), 24),
                        "clicca qui per\naprire la cartella",
                        piede="Trascina altri file o clicca fuori per ricominciare")
            self.cv.itemconfigure(self.c1, fill="#4ade80")
            self._presenta()
            if POPUP:
                self.root.after(2500, self._chiudi_dopo)
        else:
            msg = errori[0] if errori else "nessun file creato"
            self._testi("⚠  Errore" if not outs else f"⚠  {len(errori)} errori", accorcia(msg, 90),
                        "clicca qui per la cartella" if outs else "",
                        piede="Clicca fuori o premi Esc per ricominciare")
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
