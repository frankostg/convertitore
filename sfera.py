"""Sfera del Convertitore: un piccolo cerchio sempre in primo piano sul bordo dello schermo.

Trascini uno o piu' file sopra la sfera -> si apre subito la ruota delle conversioni.
- trascina la sfera col mouse per spostarla (la posizione viene ricordata)
- clic semplice: ruota per i file selezionati in Esplora file o sul Desktop
  (se non c'e' niente di selezionato apre la ruota con tutte le conversioni possibili)
- Ctrl+Alt+C ovunque: come il clic, senza toccare la sfera
- tasto destro: menu (apri, nascondi 30 minuti, esci)
- dopo un aggiornamento mostra per qualche secondo cosa c'e' di nuovo
Parte da sola all'avvio di Windows (collegamento in Esecuzione automatica).
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageFont
from tkinterdnd2 import DND_FILES, TkinterDnD

QUI = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)  # True quando gira come Convertitore.exe
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(QUI, "convertitore.py")
# comando per aprire la ruota: l'exe installato, oppure Python + script
COMANDO = [sys.executable] if FROZEN else [PYW, SCRIPT]
sys.path.insert(0, QUI)
from versione import NOVITA, VERSIONE  # noqa: E402
from convertitore import CATEGORIE  # noqa: E402

ESTENSIONI = {e for exts in CATEGORIE.values() for e in exts}
CONFIG = os.path.join(os.environ.get("APPDATA", QUI), "Convertitore", "sfera.json")

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
    Z = ctypes.windll.user32.GetDpiForSystem() / 96
except Exception:
    Z = 1.0

LATO = 72          # finestra (logica), la sfera sta al centro
R_RIPOSO = 14      # raggio a riposo: piccola e discreta
R_ATTIVA = 30      # raggio quando ci passa sopra un file
FOTOGRAMMI = 16    # passi dell'animazione di ingrandimento
DURATA = 0.18      # secondi per ingrandirsi / tornare piccola
ALPHA_RIPOSO = 0.6
KEYHEX = "#010203"  # sfondo della finestra Tk (non si vede: la disegna Windows)
ACC = (89, 220, 255)
COLORI = [(89, 220, 255), (183, 156, 255), (109, 255, 176), (255, 181, 71), (96, 150, 255), (255, 110, 120)]


def disegna(t=0.0):
    """t = 0 a riposo (piccola, discreta) -> 1 quando ci passa sopra un file.
    Stile sala comandi: nucleo scuro, anello sottile azzurro, tacche, frecce di conversione."""
    S = 4
    n = int(LATO * Z) * S
    c = n / 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    u = Z * S
    r = (R_RIPOSO + (R_ATTIVA - R_RIPOSO) * t) * u
    # alone azzurro che cresce da attiva
    if t > 0:
        from PIL import ImageFilter
        alone = Image.new("RGBA", (n, n), (0, 0, 0, 0))
        ImageDraw.Draw(alone).ellipse([c - r, c - r, c + r, c + r], fill=ACC + (int(120 * t),))
        img.alpha_composite(alone.filter(ImageFilter.GaussianBlur(5 * u)))
    d = ImageDraw.Draw(img)
    d.ellipse([c - r, c - r, c + r, c + r], fill=(3, 16, 28, 255))
    d.ellipse([c - r, c - r, c + r, c + r], outline=ACC + (int(150 + 105 * t),), width=max(1, int(1.2 * u)))
    # tacche interne (4 a riposo, 24 da attiva)
    tacche = 4 if t < 0.5 else 24
    for k in range(tacche):
        a = math.radians(k * 360 / tacche - 90)
        r1, r2 = r - (2.2 + 1.2 * t) * u, r - (4.0 + 1.8 * t) * u
        d.line([c + r1 * math.cos(a), c + r1 * math.sin(a), c + r2 * math.cos(a), c + r2 * math.sin(a)],
               fill=ACC + (int(110 + 80 * t),), width=max(1, int(1.0 * u)))
    # anello di colori dei tipi di file, solo da attiva
    if t > 0:
        r1, r2 = r - 7.5 * u, r - 6.0 * u
        for i, col in enumerate(COLORI):
            a0 = -90 + i * 60 + 6
            a1 = a0 + 48
            pts = [(c + r2 * math.cos(math.radians(a0 + (a1 - a0) * k / 20)), c + r2 * math.sin(math.radians(a0 + (a1 - a0) * k / 20))) for k in range(21)]
            pts += [(c + r1 * math.cos(math.radians(a0 + (a1 - a0) * k / 20)), c + r1 * math.sin(math.radians(a0 + (a1 - a0) * k / 20))) for k in range(20, -1, -1)]
            d.polygon(pts, fill=col + (int(255 * t),))
    # frecce di conversione
    chiaro = tuple(int(v + (255 - v) * t * 0.6) for v in (150, 225, 250))
    ra = r * (0.40 - 0.06 * t)
    w = max(2, int((1.5 + 0.6 * t) * u))
    d.arc([c - ra, c - ra, c + ra, c + ra], 205, 335, fill=chiaro + (255,), width=w)
    d.arc([c - ra, c - ra, c + ra, c + ra], 25, 155, fill=chiaro + (255,), width=w)
    for ang in (335, 155):
        a = math.radians(ang)
        x, y = c + ra * math.cos(a), c + ra * math.sin(a)
        tg = a + math.pi / 2
        p = ra * 0.4
        d.polygon([(x + p * 1.1 * math.cos(tg), y + p * 1.1 * math.sin(tg)),
                   (x + p * 0.75 * math.cos(a), y + p * 0.75 * math.sin(a)),
                   (x - p * 0.75 * math.cos(a), y - p * 0.75 * math.sin(a))], fill=chiaro + (255,))
    return img.resize((n // S, n // S), Image.LANCZOS)


class _BMIH(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                ("biClrImportant", wt.DWORD)]


class _BLEND(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


_u32, _gdi = ctypes.windll.user32, ctypes.windll.gdi32
_gdi.CreateCompatibleDC.restype = wt.HDC
_gdi.CreateCompatibleDC.argtypes = [wt.HDC]
_gdi.CreateDIBSection.restype = wt.HBITMAP
_gdi.CreateDIBSection.argtypes = [wt.HDC, ctypes.c_void_p, wt.UINT, ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD]
_gdi.SelectObject.restype = wt.HGDIOBJ
_gdi.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
_gdi.DeleteObject.argtypes = [wt.HGDIOBJ]
_gdi.DeleteDC.argtypes = [wt.HDC]
_u32.GetDC.restype = wt.HDC
_u32.GetDC.argtypes = [wt.HWND]
_u32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
_u32.GetParent.restype = wt.HWND
_u32.GetParent.argtypes = [wt.HWND]
_u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
_u32.SetWindowLongW.argtypes = [wt.HWND, ctypes.c_int, wt.LONG]
_u32.UpdateLayeredWindow.argtypes = [wt.HWND, wt.HDC, ctypes.c_void_p, ctypes.POINTER(wt.SIZE), wt.HDC,
                                     ctypes.POINTER(wt.POINT), wt.COLORREF, ctypes.POINTER(_BLEND), wt.DWORD]


def premoltiplica(img):
    """Prepara l'immagine nel formato che Windows vuole (BGRA con alpha premoltiplicato)."""
    r, g, b, a = img.split()
    r, g, b = (ImageChops.multiply(ch, a) for ch in (r, g, b))
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


def disegna_su_schermo(hwnd, dati, lato, opacita):
    """Mostra la sfera con bordi morbidi: ogni pixel puo' essere semitrasparente."""
    schermo = _u32.GetDC(None)
    mem = _gdi.CreateCompatibleDC(schermo)
    info = _BMIH(ctypes.sizeof(_BMIH), lato, -lato, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    bmp = _gdi.CreateDIBSection(mem, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, dati, len(dati))
    vecchio = _gdi.SelectObject(mem, bmp)
    blend = _BLEND(0, 0, int(255 * opacita), 1)  # AC_SRC_OVER, AC_SRC_ALPHA
    _u32.UpdateLayeredWindow(hwnd, schermo, None, ctypes.byref(wt.SIZE(lato, lato)), mem,
                             ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
    _gdi.SelectObject(mem, vecchio)
    _gdi.DeleteObject(bmp)
    _gdi.DeleteDC(mem)
    _u32.ReleaseDC(None, schermo)


_u32.GetForegroundWindow.restype = wt.HWND
_u32.RegisterHotKey.argtypes = [wt.HWND, ctypes.c_int, wt.UINT, wt.UINT]
_u32.GetMessageW.argtypes = [ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT]


def file_selezionati(hwnd):
    """File selezionati nella finestra di Esplora file `hwnd`, o sul Desktop."""
    if not hwnd:
        return []
    try:
        import win32com.client
        import win32gui
        classe = win32gui.GetClassName(hwnd)
        shell = win32com.client.Dispatch("Shell.Application")
        if classe in ("CabinetWClass", "ExploreWClass"):
            titolo = win32gui.GetWindowText(hwnd)
            finestre = [w for w in shell.Windows() if int(w.HWND) == int(hwnd)]
            if not finestre:
                return []
            # con le schede di Windows 11 piu' schede hanno la stessa finestra:
            # quella attiva e' la cui cartella compare nel titolo
            attiva = next((w for w in finestre if titolo.startswith(w.LocationName)), finestre[0])
            items = attiva.Document.SelectedItems()
        elif classe in ("Progman", "WorkerW"):
            desktop = shell.Windows().FindWindowSW(0, 0, 8, 0, 1)  # SWC_DESKTOP
            items = desktop.Document.SelectedItems()
        else:
            return []
        return [it.Path for it in items if os.path.isfile(it.Path)]
    except Exception:
        return []


def leggi_config():
    try:
        with open(CONFIG, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def scrivi_config(**valori):
    dati = leggi_config()
    dati.update(valori)
    try:
        os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
        with open(CONFIG, "w", encoding="utf-8") as fh:
            json.dump(dati, fh)
    except OSError:
        pass


def ascolta_scorciatoia(coda):
    """Thread: registra Ctrl+Alt+C per tutto Windows e avvisa la sfera quando viene premuto."""
    msg = wt.MSG()
    if not _u32.RegisterHotKey(None, 1, 0x0002 | 0x0001 | 0x4000, ord("C")):  # CTRL | ALT | NOREPEAT
        return  # gia' usata da un altro programma: pazienza, resta il clic sulla sfera
    while _u32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
        if msg.message == 0x0312:  # WM_HOTKEY
            coda.put(_u32.GetForegroundWindow())


def disegna_avviso(titolo, righe):
    """Pannello con le novita' dopo un aggiornamento (angoli smussati, linee azzurre)."""
    S = 2
    f_t = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(15 * Z * S))
    f_r = ImageFont.truetype(r"C:\Windows\Fonts\bahnschrift.ttf", int(12.5 * Z * S))
    f_m = ImageFont.truetype(r"C:\Windows\Fonts\consola.ttf", int(10 * Z * S))
    try:
        f_t.set_variation_by_name("SemiBold")
        f_r.set_variation_by_name("Regular")
    except Exception:
        pass
    larg = int(320 * Z * S)
    pad = int(18 * Z * S)
    misura = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    linee = []  # (testo, prima riga della voce?)
    for r in righe:
        riga, prima = "", True
        for p in r.split(" "):
            prova = (riga + " " + p).strip()
            if riga and misura.textlength(prova, font=f_r) > larg - 2 * pad - 14 * Z * S:
                linee.append((riga, prima))
                riga, prima = p, False
            else:
                riga = prova
        linee.append((riga, prima))
    alt_r = int(19 * Z * S)
    alt = pad + int(44 * Z * S) + alt_r * len(linee) + int(30 * Z * S)
    img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    t = int(12 * Z * S)  # angoli smussati
    forma = [(t, 0), (larg - 1, 0), (larg - 1, alt - 1 - t), (larg - 1 - t, alt - 1), (0, alt - 1), (0, t)]
    d.polygon(forma, fill=(4, 18, 31, 246))
    d.line(forma + [forma[0]], fill=(89, 220, 255, 90), width=S)
    # staffa luminosa nell'angolo in alto
    d.line([(t, 0), (t + 40 * S, 0)], fill=(89, 220, 255, 255), width=2 * S)
    d.line([(0, t), (0, t + 30 * S)], fill=(89, 220, 255, 255), width=2 * S)
    x, y = pad, pad
    d.text((x, y), "AGGIORNAMENTO", font=f_m, fill=(89, 220, 255, 255))
    y += int(16 * Z * S)
    d.text((x, y), titolo, font=f_t, fill=(230, 247, 255, 255))
    y += int(28 * Z * S)
    for testo, prima in linee:
        if prima:
            d.rectangle([x, y + 7 * Z * S, x + 5 * Z * S, y + 12 * Z * S], fill=(89, 220, 255, 255))
        d.text((x + 14 * Z * S, y), testo, font=f_r, fill=(214, 232, 243, 255))
        y += alt_r
    d.text((x, alt - pad + 4 * S), "CLIC PER CHIUDERE", font=f_m, fill=(115, 151, 171, 255), anchor="ls")
    return img.resize((larg // S, alt // S), Image.LANCZOS)


def una_sola_istanza():
    ctypes.windll.kernel32.CreateMutexW(None, False, "Convertitore_Sfera")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


class Sfera:
    def __init__(self, root):
        self.root = root
        root.title("Convertitore")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.configure(bg=KEYHEX)
        self.lato = int(LATO * Z)
        x, y = self._posizione()
        root.geometry(f"{self.lato}x{self.lato}+{x}+{y}")

        self.cv = tk.Canvas(root, width=self.lato, height=self.lato, bg=KEYHEX, highlightthickness=0)
        self.cv.pack()
        self.frames = [premoltiplica(disegna(k / FOTOGRAMMI)) for k in range(FOTOGRAMMI + 1)]
        self.f, self.meta, self._anim = 0, 0, None
        self.visibile = 1.0
        # finestra "a strati": Windows la disegna con l'immagine, con bordi sfumati veri
        root.update_idletasks()
        self.hwnd = _u32.GetParent(root.winfo_id())
        _u32.SetWindowLongW(self.hwnd, -20, _u32.GetWindowLongW(self.hwnd, -20) | 0x80000)  # WS_EX_LAYERED
        self._ridisegna()

        self.cv.drop_target_register(DND_FILES)
        self.cv.dnd_bind("<<DropEnter>>", self._entra)
        self.cv.dnd_bind("<<DropPosition>>", lambda e: e.action)
        self.cv.dnd_bind("<<DropLeave>>", lambda e: self._riposo())
        self.cv.dnd_bind("<<Drop>>", self._drop)
        self.ultima_finestra = None
        self.cv.bind("<Enter>", lambda e: (self._ricorda_finestra(), self._attiva()))
        self.cv.bind("<Leave>", lambda e: self._riposo())
        self.cv.bind("<ButtonPress-1>", self._premi)
        self.cv.bind("<B1-Motion>", self._trascina)
        self.cv.bind("<ButtonRelease-1>", self._rilascia)
        self.cv.bind("<Button-3>", self._menu)

        self.menu = tk.Menu(root, tearoff=0)
        self.menu.add_command(label="Apri il Convertitore", command=lambda: self._lancia([]))
        self.menu.add_command(label="Nascondi per 30 minuti", command=self._nascondi)
        self.menu.add_separator()
        self.menu.add_command(label="Chiudi la sfera", command=root.destroy)
        self.menu.add_separator()
        self.menu.add_command(label=f"Versione {VERSIONE}", state="disabled")
        # resta sopra anche se un'altra finestra "topmost" la copre
        self._tieni_sopra()
        # aggiornamenti online: primo controllo dopo 20 secondi, poi ogni 6 ore
        self.occupata = False
        self.pronto = None
        self.root.after(20_000, self._cerca_aggiornamenti)
        # scorciatoia Ctrl+Alt+C
        self.coda = queue.Queue()
        threading.Thread(target=ascolta_scorciatoia, args=(self.coda,), daemon=True).start()
        self._controlla_scorciatoia()
        # appena aggiornata: mostra le novita'
        if leggi_config().get("vista") != VERSIONE:
            scrivi_config(vista=VERSIONE)
            if FROZEN or os.environ.get("CONVERTITORE_AVVISO"):
                self.root.after(2500, self._avviso)

    # -- scorciatoia
    def _controlla_scorciatoia(self):
        try:
            while True:
                finestra = self.coda.get_nowait()
                if not self.occupata:
                    files = [f for f in file_selezionati(finestra)
                             if os.path.splitext(f)[1].lower().lstrip(".") in ESTENSIONI]
                    self._lancia(files or ["--ruota"])
        except queue.Empty:
            pass
        self.root.after(150, self._controlla_scorciatoia)

    # -- avviso novita'
    def _avviso(self):
        import strati
        img = disegna_avviso(f"Convertitore aggiornato a {VERSIONE}", NOVITA)
        w, h = img.size
        top = tk.Toplevel(self.root)
        top.overrideredirect(True)
        top.attributes("-topmost", True)
        # accanto alla sfera, verso il centro dello schermo
        sx, sy = self.root.winfo_x(), self.root.winfo_y()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        x = sx - w - int(6 * Z) if sx > sw / 2 else sx + self.lato + int(6 * Z)
        y = min(max(sy, int(8 * Z)), sh - h - int(56 * Z))
        top.geometry(f"{w}x{h}+{x}+{y}")
        hwnd = strati.rendi_a_strati(top)
        dati = strati.premoltiplica(img)

        def dissolvi(a, passo):
            try:
                a = max(0.0, min(1.0, a + passo))
                strati.disegna(hwnd, img, a, dati)
                if (passo > 0 and a < 1) or (passo < 0 and a > 0):
                    top.after(16, lambda: dissolvi(a, passo))
                elif passo < 0:
                    top.destroy()
            except tk.TclError:
                pass

        def chiudi(_e=None):
            if getattr(top, "_chiusura", False):
                return
            top._chiusura = True
            dissolvi(1.0, -0.12)

        def dopo():
            # resta finche' il mouse ci sta sopra
            try:
                px, py = top.winfo_pointerxy()
                if x <= px <= x + w and y <= py <= y + h:
                    top.after(1000, dopo)
                else:
                    chiudi()
            except tk.TclError:
                pass

        top.bind("<Button-1>", chiudi)
        dissolvi(0.0, 0.12)
        top.after(14_000, dopo)

    # -- aggiornamenti online
    def _cerca_aggiornamenti(self):
        def lavoro():
            try:
                import aggiornamento
                self.pronto = aggiornamento.controlla()
            except Exception:
                self.pronto = None  # niente internet o GitHub non raggiungibile: si riprova piu' tardi
        self._ricerca = threading.Thread(target=lavoro, daemon=True)
        self._ricerca.start()
        self.root.after(5_000, self._installa_se_pronto)
        self.root.after(6 * 3600 * 1000, self._cerca_aggiornamenti)

    def _installa_se_pronto(self):
        if self._ricerca.is_alive():  # sta ancora scaricando
            self.root.after(5_000, self._installa_se_pronto)
            return
        if not self.pronto:
            return
        if self.occupata:  # c'e' una ruota aperta: aspetta che finisca
            self.root.after(10_000, self._installa_se_pronto)
            return
        import aggiornamento
        _, percorso = self.pronto
        aggiornamento.installa(percorso)  # l'installatore chiude e riavvia la sfera

    # -- posizione
    def _posizione(self):
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        try:
            p = leggi_config()
            x, y = int(p["x"]), int(p["y"])
            if 0 <= x <= sw - 20 and 0 <= y <= sh - 20:
                return x, y
        except Exception:
            pass
        # predefinita: bordo destro, poco sopra la meta'
        return sw - self.lato - int(2 * Z), int(sh * 0.42)

    def _salva(self):
        scrivi_config(x=self.root.winfo_x(), y=self.root.winfo_y())

    # -- aspetto
    def _attiva(self):
        self._vai(FOTOGRAMMI)

    def _riposo(self):
        self._vai(0)

    def _vai(self, meta):
        """Anima dolcemente tra riposo e attiva (a tempo: sempre fluida)."""
        self.meta = meta
        self._t_ultimo = time.perf_counter()
        if self._anim is None:
            self._passo()

    def _passo(self):
        ora = time.perf_counter()
        avanzo = (ora - self._t_ultimo) / DURATA * FOTOGRAMMI
        self._t_ultimo = ora
        self.pos = getattr(self, "pos", float(self.f))
        if self.meta > self.pos:
            self.pos = min(self.meta, self.pos + max(avanzo, 0.5))
        else:
            self.pos = max(self.meta, self.pos - max(avanzo, 0.5))
        # curva morbida: veloce all'inizio, si posa piano
        x = self.pos / FOTOGRAMMI
        self.f = round(FOTOGRAMMI * (1 - (1 - x) ** 2) if self.meta else FOTOGRAMMI * x * x)
        self._ridisegna()
        if self.pos == self.meta:
            self._anim = None
            return
        self._anim = self.root.after(8, self._passo)

    def _ridisegna(self):
        t = self.f / FOTOGRAMMI
        alfa = (ALPHA_RIPOSO + (1 - ALPHA_RIPOSO) * t) * self.visibile
        disegna_su_schermo(self.hwnd, self.frames[self.f], self.lato, alfa)

    def _sfuma(self, verso, poi=None):
        """Fa comparire (+1) o sparire (-1) la sfera con una dissolvenza."""
        t0 = time.perf_counter()

        def passo():
            t = min(1.0, (time.perf_counter() - t0) / 0.2)
            self.visibile = t if verso > 0 else 1 - t
            self._ridisegna()
            if t < 1:
                self.root.after(8, passo)
            elif poi:
                poi()
        passo()

    def _mostra(self):
        self.visibile = 0.0
        self.f = self.meta = 0
        self.pos = 0.0
        self._ridisegna()
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self._sfuma(+1)

    def _tieni_sopra(self):
        try:
            self.root.attributes("-topmost", True)
            self.root.lift()
        except tk.TclError:
            return
        self.root.after(4000, self._tieni_sopra)

    # -- trascinamento file
    def _entra(self, e):
        self._attiva()
        return e.action

    def _drop(self, e):
        self._riposo()
        files = [f for f in self.root.tk.splitlist(e.data) if os.path.isfile(f)]
        if files:
            self._lancia(files)
        return e.action

    def _lancia(self, files):
        try:
            ctypes.windll.user32.AllowSetForegroundWindow(-1)
        except Exception:
            pass
        proc = subprocess.Popen([*COMANDO, *files], cwd=QUI)
        if files:
            self.occupata = True
            # mentre la ruota e' aperta la sfera si fa da parte, poi ricompare
            self.root.after(250, lambda: self._sfuma(-1, self.root.withdraw))
            self._aspetta(proc)

    def _aspetta(self, proc):
        if proc.poll() is None:
            self.root.after(300, lambda: self._aspetta(proc))
        else:
            self.occupata = False
            self._mostra()

    # -- spostare la sfera / clic
    def _premi(self, e):
        self._start = (e.x_root, e.y_root, self.root.winfo_x(), self.root.winfo_y())
        self._mosso = False

    def _trascina(self, e):
        x0, y0, wx, wy = self._start
        dx, dy = e.x_root - x0, e.y_root - y0
        if abs(dx) + abs(dy) > 4:
            self._mosso = True
        if self._mosso:
            self.root.geometry(f"+{wx + dx}+{wy + dy}")

    def _rilascia(self, e):
        if self._mosso:
            self._salva()
            return
        # clic: ruota per i file selezionati in Esplora file / sul Desktop
        files = [f for f in file_selezionati(self.ultima_finestra)
                 if os.path.splitext(f)[1].lower().lstrip(".") in ESTENSIONI]
        # niente di convertibile selezionato: ruota con tutte le conversioni possibili
        self._lancia(files or ["--ruota"])

    def _ricorda_finestra(self):
        """Prima del clic la finestra attiva e' ancora Esplora file (o il Desktop): ricordala."""
        fg = _u32.GetForegroundWindow()
        if fg and fg != self.hwnd:
            self.ultima_finestra = fg

    def _menu(self, e):
        self.menu.tk_popup(e.x_root, e.y_root)

    def _nascondi(self):
        self.root.withdraw()
        self.root.after(30 * 60 * 1000, self._mostra)


def main():
    if not una_sola_istanza():
        return
    root = TkinterDnD.Tk()
    Sfera(root)
    root.mainloop()


if __name__ == "__main__":
    main()
