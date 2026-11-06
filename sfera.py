"""Sfera del Convertitore: un piccolo cerchio sempre in primo piano sul bordo dello schermo.

Trascini uno o piu' file sopra la sfera -> si apre subito la ruota delle conversioni.
- trascina la sfera col mouse per spostarla (la posizione viene ricordata)
- clic semplice: ruota per i file selezionati in Esplora file o sul Desktop
  (se non c'e' niente di selezionato apre la ruota con tutte le conversioni possibili)
- tasto destro: menu (apri, nascondi 30 minuti, esci)
Parte da sola all'avvio di Windows (collegamento in Esecuzione automatica).
"""
import ctypes
import ctypes.wintypes as wt
import json
import math
import os
import subprocess
import sys
import threading
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw
from tkinterdnd2 import DND_FILES, TkinterDnD

QUI = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)  # True quando gira come Convertitore.exe
PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(QUI, "convertitore.py")
# comando per aprire la ruota: l'exe installato, oppure Python + script
COMANDO = [sys.executable] if FROZEN else [PYW, SCRIPT]
sys.path.insert(0, QUI)
from versione import VERSIONE  # noqa: E402
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
FOTOGRAMMI = 8     # passi dell'animazione di ingrandimento
ALPHA_RIPOSO = 0.55
KEYHEX = "#010203"  # sfondo della finestra Tk (non si vede: la disegna Windows)
COLORI = [(34, 211, 238), (232, 121, 249), (163, 230, 53), (251, 146, 60), (96, 165, 250), (52, 211, 153)]


def disegna(t=0.0):
    """t = 0 a riposo (piccola, grigia, discreta) -> 1 quando ci passa sopra un file."""
    S = 4
    n = int(LATO * Z) * S
    c = n / 2
    img = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    u = Z * S
    r = (R_RIPOSO + (R_ATTIVA - R_RIPOSO) * t) * u
    # disco scuro con bordo sottile
    d.ellipse([c - r, c - r, c + r, c + r], fill=(16, 18, 26, 255))
    grigio = (96, 104, 124)
    d.ellipse([c - r, c - r, c + r, c + r], outline=grigio + (255,), width=max(1, int(1.2 * u)))
    # anello sottile di colori che compare solo da attiva
    if t > 0:
        r1, r2 = r - 4.5 * u, r - 2 * u
        for i, col in enumerate(COLORI):
            a0 = -90 + i * 60 + 5
            a1 = a0 + 50
            pts = [(c + r2 * math.cos(math.radians(a0 + (a1 - a0) * k / 20)), c + r2 * math.sin(math.radians(a0 + (a1 - a0) * k / 20))) for k in range(21)]
            pts += [(c + r1 * math.cos(math.radians(a0 + (a1 - a0) * k / 20)), c + r1 * math.sin(math.radians(a0 + (a1 - a0) * k / 20))) for k in range(20, -1, -1)]
            mix = tuple(int(16 + (v - 16) * t) for v in col)
            d.polygon(pts, fill=mix + (255,))
    # simbolo: due frecce circolari sottili
    chiaro = tuple(int(150 + (235 - 150) * t) for v in range(3))
    ra = r * (0.42 if t == 0 else 0.42 - 0.08 * t)
    w = max(2, int((1.6 + 0.8 * t) * u))
    d.arc([c - ra, c - ra, c + ra, c + ra], 205, 335, fill=chiaro + (255,), width=w)
    d.arc([c - ra, c - ra, c + ra, c + ra], 25, 155, fill=chiaro + (255,), width=w)
    for ang in (335, 155):
        a = math.radians(ang)
        x, y = c + ra * math.cos(a), c + ra * math.sin(a)
        tg = a + math.pi / 2
        p = ra * 0.38
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
            with open(CONFIG, encoding="utf-8") as fh:
                p = json.load(fh)
            x, y = int(p["x"]), int(p["y"])
            if 0 <= x <= sw - 20 and 0 <= y <= sh - 20:
                return x, y
        except Exception:
            pass
        # predefinita: bordo destro, poco sopra la meta'
        return sw - self.lato - int(2 * Z), int(sh * 0.42)

    def _salva(self):
        try:
            os.makedirs(os.path.dirname(CONFIG), exist_ok=True)
            with open(CONFIG, "w", encoding="utf-8") as fh:
                json.dump({"x": self.root.winfo_x(), "y": self.root.winfo_y()}, fh)
        except OSError:
            pass

    # -- aspetto
    def _attiva(self):
        self._vai(FOTOGRAMMI)

    def _riposo(self):
        self._vai(0)

    def _vai(self, meta):
        """Anima dolcemente tra riposo e attiva."""
        self.meta = meta
        if self._anim is None:
            self._passo()

    def _passo(self):
        if self.f == self.meta:
            self._anim = None
            return
        self.f += 1 if self.meta > self.f else -1
        self._ridisegna()
        self._anim = self.root.after(16, self._passo)

    def _ridisegna(self):
        t = self.f / FOTOGRAMMI
        disegna_su_schermo(self.hwnd, self.frames[self.f], self.lato, ALPHA_RIPOSO + (1 - ALPHA_RIPOSO) * t)

    def _mostra(self):
        self.root.deiconify()
        self.root.attributes("-topmost", True)
        self.f = self.meta = 0
        self._ridisegna()

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
            self.root.after(700, self.root.withdraw)
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
