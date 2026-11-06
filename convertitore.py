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
    "immagine": ["png", "jpg", "webp", "pdf", "gif", "bmp", "tiff", "ico"],
    "video": ["mp4", "mkv", "mov", "avi", "webm", "gif", "mp3", "wav"],
    "audio": ["mp3", "wav", "flac", "ogg", "m4a", "aac"],
    "pdf": ["png", "jpg", "txt"],
    "word": ["pdf", "docx", "txt", "rtf"],
    "excel": ["pdf", "xlsx", "csv"],
    "powerpoint": ["pdf", "pptx"],
}

SOTTOTITOLI = {
    "png": "immagine", "jpg": "immagine", "webp": "leggera", "bmp": "immagine",
    "tiff": "alta qualità", "ico": "icona", "gif": "animazione", "pdf": "documento",
    "mp4": "video", "mkv": "video", "mov": "video", "avi": "video", "webm": "web",
    "mp3": "solo audio", "wav": "audio", "flac": "senza perdita", "ogg": "audio",
    "m4a": "audio", "aac": "audio", "txt": "solo testo", "docx": "Word", "rtf": "testo",
    "xlsx": "Excel", "csv": "tabella", "pptx": "PowerPoint",
    "pdfunico": "tutti insieme", "unisci": "un solo PDF",
}

ETICHETTE = {"pdfunico": "1 PDF", "unisci": "UNISCI"}

COLORI = {
    "immagine": (34, 211, 238),
    "video": (232, 121, 249),
    "audio": (163, 230, 53),
    "pdf": (251, 146, 60),
    "word": (96, 165, 250),
    "excel": (52, 211, 153),
    "powerpoint": (251, 113, 133),
}

# ruota senza file: una fetta per ogni tipo di file
PANORAMICA = ["cat:immagine", "cat:video", "cat:audio", "cat:pdf", "cat:word", "cat:excel", "cat:powerpoint"]
ETICHETTE.update({"cat:immagine": "IMMAGINI", "cat:video": "VIDEO", "cat:audio": "AUDIO", "cat:pdf": "PDF",
                  "cat:word": "WORD", "cat:excel": "EXCEL", "cat:powerpoint": "PPT"})
SOTTOTITOLI.update({k: " · ".join(DESTINAZIONI[k[4:]][:3]) + " …" for k in PANORAMICA})
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


def opzioni_per(files):
    """Restituisce (categoria, lista di chiavi) valide per tutti i file."""
    cats = {categoria(f) for f in files}
    if None in cats:
        return None, []
    if len(cats) != 1:
        return "misto", []
    cat = cats.pop()
    exts = {ALIAS.get(estensione(f), estensione(f)) for f in files}
    opz = [d for d in DESTINAZIONI[cat] if not (len(exts) == 1 and d in exts)]
    if cat == "immagine" and len(files) > 1:
        opz.insert(0, "pdfunico")
    if cat == "pdf" and len(files) > 1:
        opz.insert(0, "unisci")
    return cat, opz


# ----------------------------------------------------------------- conversioni
def percorso_libero(cartella, nome, ext):
    out = os.path.join(cartella, f"{nome}.{ext}")
    n = 1
    while os.path.exists(out):
        out = os.path.join(cartella, f"{nome} ({n}).{ext}")
        n += 1
    return out


def uscita(src, ext, suffisso=""):
    base = os.path.splitext(os.path.basename(src))[0] + suffisso
    return percorso_libero(os.path.dirname(src), base, ext)


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


def converti_immagine(src, key):
    im = Image.open(src)
    animata = getattr(im, "is_animated", False)
    out = uscita(src, key)
    if key in ("jpg", "bmp", "pdf"):
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            sfondo = Image.new("RGB", im.size, (255, 255, 255))
            sfondo.paste(im, mask=im.getchannel("A"))
            im = sfondo
        else:
            im = im.convert("RGB")
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


def immagini_in_pdf(files):
    pagine = []
    for f in files:
        im = Image.open(f)
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA")
            sfondo = Image.new("RGB", im.size, (255, 255, 255))
            sfondo.paste(im, mask=im.getchannel("A"))
            im = sfondo
        pagine.append(im.convert("RGB"))
    out = percorso_libero(os.path.dirname(files[0]), "Immagini unite", "pdf")
    pagine[0].save(out, save_all=True, append_images=pagine[1:])
    return [out]


def converti_pdf(src, key):
    import pymupdf
    doc = pymupdf.open(src)
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
    import pymupdf
    out_doc = pymupdf.open()
    for f in files:
        with pymupdf.open(f) as d:
            out_doc.insert_pdf(d)
    out = percorso_libero(os.path.dirname(files[0]), "PDF unito", "pdf")
    out_doc.save(out)
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


def converti_ffmpeg(src, key):
    ff = trova_ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg non trovato: installalo con  winget install Gyan.FFmpeg")
    out = uscita(src, key)
    cmd = [ff, "-hide_banner", "-loglevel", "error", "-y", "-i", src, *FFMPEG_ARGS[key], out]
    r = subprocess.run(cmd, capture_output=True, text=True, creationflags=NO_WINDOW)
    if r.returncode != 0:
        if os.path.exists(out):
            os.remove(out)
        raise RuntimeError((r.stderr or "errore ffmpeg").strip().splitlines()[-1])
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
    if key == "pdfunico":
        return immagini_in_pdf(files), []
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
BG = (6, 8, 16)
FONTS = r"C:\Windows\Fonts"


def font(size, bold=True):
    nome = "segoeuib.ttf" if bold else "segoeui.ttf"
    try:
        return ImageFont.truetype(os.path.join(FONTS, nome), size)
    except OSError:
        return ImageFont.load_default()


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


def sfondo():
    if POPUP:
        img = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        r = R_PIATTO * S
        d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], fill=BG + (255,))
    else:
        img = Image.new("RGBA", (W * S, H * S), BG + (255,))
    glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    r = 300 * S
    d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], fill=(40, 60, 140, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(90 * S))
    bagliore(img, glow)
    if POPUP:
        d = ImageDraw.Draw(img)
        r = (R_PIATTO - 2) * S
        d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], outline=(70, 90, 150, 255), width=2 * S)
    d = ImageDraw.Draw(img)
    # tacche decorative attorno alla ruota
    for k in range(120):
        a = math.radians(k * 3)
        lung = 9 if k % 10 == 0 else 4
        r1, r2 = (R_OUT + 22) * S, (R_OUT + 22 + lung) * S
        col = (120, 140, 200, 110) if k % 10 == 0 else (80, 95, 150, 70)
        d.line([CX * S + r1 * math.cos(a), CY * S + r1 * math.sin(a),
                CX * S + r2 * math.cos(a), CY * S + r2 * math.sin(a)], fill=col, width=S)
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


def disegna_ruota(base, opzioni, colore, hover, spenta=False):
    """`colore` e' un colore unico oppure una lista (un colore per fetta)."""
    colori = colore if isinstance(colore, list) else [colore] * len(opzioni)
    colore = (34, 211, 238) if isinstance(colore, list) else colore
    img = base.copy()
    n = len(opzioni)
    passo = 360 / n
    gap = 1.6 if n > 1 else 0
    if hover is not None and not spenta:
        a0 = -90 + hover * passo - passo / 2 + gap
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(glow).polygon(settore(a0, a0 + passo - 2 * gap, R_IN, R_OUT + 14), fill=colori[hover] + (200,))
        bagliore(img, glow.filter(ImageFilter.GaussianBlur(16 * S)))
    strato = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(strato)
    f_big = font(int((24 if n <= 8 else 20) * S))
    f_small = font(11 * S, bold=False)
    for i, key in enumerate(opzioni):
        a0 = -90 + i * passo - passo / 2 + gap
        a1 = a0 + passo - 2 * gap
        attivo = (i == hover) and not spenta
        colore = colori[i]
        r2 = R_OUT + (12 if attivo else 0)
        if attivo:
            fill, line, testo, sub = colore + (235,), colore + (255,), (8, 10, 20, 255), (8, 10, 20, 200)
        else:
            alpha = 25 if spenta else 38
            fill = colore + (alpha,)
            line = colore + (60 if spenta else 150,)
            testo = (230, 236, 255, 110 if spenta else 255)
            sub = colore + (90 if spenta else 210,)
        poly = settore(a0, a1, R_IN + 6, r2)
        d.polygon(poly, fill=fill)
        d.line(poly + [poly[0]], fill=line, width=S + 1, joint="curve")
        am = math.radians((a0 + a1) / 2)
        rm = (R_IN + 6 + r2) / 2 * S
        tx, ty = CX * S + rm * math.cos(am), CY * S + rm * math.sin(am)
        d.text((tx, ty - 7 * S), ETICHETTE.get(key, key.upper()), font=f_big, fill=testo, anchor="mm")
        d.text((tx, ty + 15 * S), SOTTOTITOLI.get(key, ""), font=f_small, fill=sub, anchor="mm")
    # cerchio centrale
    colore = (34, 211, 238) if len(set(colori)) > 1 else colori[0]
    r = (R_IN - 6) * S
    d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], fill=(10, 14, 28, 255), outline=colore + (170,), width=2 * S)
    r = (R_IN - 16) * S
    d.ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], outline=colore + (50,), width=S)
    img.alpha_composite(strato)
    return img.resize((ZW, ZH), Image.LANCZOS)


def disegna_attesa(base, evidenzia=False):
    img = base.copy()
    d = ImageDraw.Draw(img)
    col = (34, 211, 238)
    for r, a, w in ((R_OUT, 150 if evidenzia else 70, 2), (R_OUT - 40, 60 if evidenzia else 30, 1), (R_IN - 6, 200 if evidenzia else 120, 2)):
        d.ellipse([(CX - r) * S, (CY - r) * S, (CX + r) * S, (CY + r) * S], outline=col + (a,), width=w * S)
    # archi tratteggiati
    r = (R_OUT - 20) * S
    for k in range(36):
        a0 = k * 10
        d.arc([CX * S - r, CY * S - r, CX * S + r, CY * S + r], a0, a0 + 5, fill=col + (130 if evidenzia else 60,), width=3 * S)
    if evidenzia:
        glow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        r = R_OUT * S
        ImageDraw.Draw(glow).ellipse([CX * S - r, CY * S - r, CX * S + r, CY * S + r], outline=col + (220,), width=10 * S)
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
        root.configure(bg="#060810")
        ico = os.path.join(os.path.dirname(os.path.abspath(__file__)), "convertitore.ico")
        if os.path.exists(ico):
            root.iconbitmap(ico)
        if not POPUP:
            barra_scura(root)

        self.cv = tk.Canvas(root, width=ZW, height=ZH, bg=KEYHEX if POPUP else "#060810", highlightthickness=0)
        self.cv.pack()
        self.base = sfondo()
        self.img_id = self.cv.create_image(0, 0, anchor="nw")
        self.titolo = self.cv.create_text((W / 2) * Z, (40) * Z, text="C O N V E R T I T O R E", fill="#e6ecff", font=("Segoe UI Semibold", -int(20 * Z)))
        self.sotto = self.cv.create_text((W / 2) * Z, (66) * Z, text="", fill="#7c8bb8", font=("Segoe UI", -int(13 * Z)))
        self.c1 = self.cv.create_text((CX) * Z, (CY - 22) * Z, text="", fill="#e6ecff", font=("Segoe UI Semibold", -int(17 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.c2 = self.cv.create_text((CX) * Z, (CY + 8) * Z, text="", fill="#7c8bb8", font=("Segoe UI", -int(13 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.c3 = self.cv.create_text((CX) * Z, (CY + 32) * Z, text="", fill="#7c8bb8", font=("Segoe UI", -int(12 * Z)), width=int(180 * Z), justify="center", anchor="n")
        self.piede = self.cv.create_text((W / 2) * Z, (H - 22) * Z, text="", fill="#56638f", font=("Segoe UI", -int(12 * Z)))

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
        self.risultati = []
        self.spin = None
        self.angolo = 0
        if POPUP:
            # finestra a strati: la disegna Windows con bordi morbidi veri
            import strati
            self.strati = strati
            self.opacita = 0.0
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
            self._dissolvenza(0.0)
        else:
            self.reset()
            if iniziali:
                root.after(100, lambda: self.carica(iniziali))

    # -- modalità popup
    def _dissolvenza(self, a):
        a = min(1.0, a + 0.2)
        self.opacita = a
        self._presenta()
        if a < 1.0:
            self.root.after(15, lambda: self._dissolvenza(a))
        else:
            self.root.focus_force()

    def _perso_fuoco(self):
        try:
            if POPUP and self.stato not in ("lavoro", "panoramica", "categoria") and self.root.focus_get() is None:
                self.chiudi()
        except (tk.TclError, KeyError):
            pass

    def chiudi(self):
        try:
            self.root.destroy()
        except tk.TclError:
            pass

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
            self.corrente = pil
            self._presenta()
            return
        self.tkimg = ImageTk.PhotoImage(pil)
        self.cv.itemconfigure(self.img_id, image=self.tkimg)

    def _presenta(self):
        """Popup: compone ruota + scritte centrali + rotellina e la passa a Windows."""
        if not POPUP or self.corrente is None:
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
        try:
            self.strati.disegna(self.hwnd, img, self.opacita)
        except Exception:
            pass

    def _testi(self, a="", b="", c="", sotto="", piede=""):
        self.cv.itemconfigure(self.c1, text=a, fill="#e6ecff")
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
        colore = COLORI[self.cat] if self.cat else [COLORI[k[4:]] for k in self.opz]
        if key not in self.cache:
            if len(self.cache) > 60:
                self.cache = {k: v for k, v in self.cache.items() if k[0] == "attesa"}
            self.cache[key] = disegna_ruota(self.base, self.opz, colore, self.hover, spenta)
        self._mostra(self.cache[key])

    def carica(self, files):
        if self.stato == "lavoro":
            return
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
        self.files, self.cat, self.opz = files, cat, opz
        self.stato, self.hover = "ruota", None
        self._ruota()
        if len(files) == 1:
            nome = os.path.basename(files[0])
            a, b = accorcia(nome, 22), f"{cat}  ·  {self._peso(files[0])}"
        else:
            a, b = f"{len(files)} file", cat
        self._testi(a, b, "scegli il formato", sotto=f"{len(opz)} conversioni possibili",
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
            if i is not None:
                self._categoria(self.opz[i][4:])
            elif not centro and math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "categoria":
            if centro:
                self._panoramica()
            elif self._indice(e.x, e.y) is not None:
                self._testi(self.etichetta_cat(), f"prima trascina qui\n{NOMI_TIPO[self.cat]}", "clic qui per tornare")
                self.cv.itemconfigure(self.c1, fill="#fcd34d")
                self._presenta() if POPUP else None
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "ruota":
            i = self._indice(e.x, e.y)
            if i is not None:
                self._avvia(self.opz[i])
            elif math.hypot(e.x - CX, e.y - CY) > R_OUT + 30:
                self.reset()
        elif self.stato == "fatto":
            if math.hypot(e.x - CX, e.y - CY) < R_IN and self.risultati:
                subprocess.Popen(["explorer", "/select,", os.path.normpath(self.risultati[0])])
                if POPUP:
                    self.chiudi()
            else:
                self.reset()

    def etichetta_cat(self):
        return ETICHETTE["cat:" + self.cat].capitalize()

    # -- conversione
    def _avvia(self, key):
        self.stato = "lavoro"
        self.hover = None
        self.cv.configure(cursor="watch")
        self._ruota(spenta=True)
        self.etichetta = ETICHETTE.get(key, key.upper())
        self._testi("Converto…", f"in {self.etichetta}", "", piede="Attendi, non chiudere la finestra")
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
            self._testi("✓  Fatto", f"{n} file {self.etichetta}" if n > 1 else accorcia(os.path.basename(outs[0]), 24),
                        "clicca qui per\naprire la cartella",
                        piede="Trascina altri file o clicca fuori per ricominciare")
            self.cv.itemconfigure(self.c1, fill="#86efac")
            self._presenta()
            if POPUP:
                self.root.after(2500, self._chiudi_dopo)
        else:
            msg = errori[0] if errori else "nessun file creato"
            self._testi("⚠  Errore" if not outs else f"⚠  {len(errori)} errori", accorcia(msg, 90),
                        "clicca qui per la cartella" if outs else "",
                        piede="Clicca fuori o premi Esc per ricominciare")
            self.cv.itemconfigure(self.c1, fill="#fca5a5")
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
