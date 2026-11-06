"""Finestre con trasparenza vera (pixel per pixel) su Windows.

Tkinter da solo conosce solo la trasparenza "tutto o niente" (-transparentcolor),
che lascia i bordi sgranati. Qui la finestra diventa "a strati" (WS_EX_LAYERED)
e la disegna direttamente Windows a partire da un'immagine RGBA di Pillow:
ogni pixel puo' essere semitrasparente, quindi i bordi restano morbidi.
"""
import ctypes
import ctypes.wintypes as wt

from PIL import Image, ImageChops


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


def rendi_a_strati(root):
    """Trasforma la finestra Tk in finestra a strati e ne restituisce l'handle."""
    root.update_idletasks()
    hwnd = _u32.GetParent(root.winfo_id())
    _u32.SetWindowLongW(hwnd, -20, _u32.GetWindowLongW(hwnd, -20) | 0x80000)  # WS_EX_LAYERED
    return hwnd


def premoltiplica(img):
    """Formato richiesto da Windows: BGRA con alpha premoltiplicato."""
    r, g, b, a = img.convert("RGBA").split()
    r, g, b = (ImageChops.multiply(ch, a) for ch in (r, g, b))
    return Image.merge("RGBA", (b, g, r, a)).tobytes()


def disegna(hwnd, img, opacita=1.0, dati=None):
    """Mostra `img` (RGBA) nella finestra a strati, con opacita' complessiva 0..1."""
    w, h = img.size
    dati = dati if dati is not None else premoltiplica(img)
    schermo = _u32.GetDC(None)
    mem = _gdi.CreateCompatibleDC(schermo)
    info = _BMIH(ctypes.sizeof(_BMIH), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    bmp = _gdi.CreateDIBSection(mem, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, dati, len(dati))
    vecchio = _gdi.SelectObject(mem, bmp)
    blend = _BLEND(0, 0, max(0, min(255, int(255 * opacita))), 1)  # AC_SRC_OVER, AC_SRC_ALPHA
    _u32.UpdateLayeredWindow(hwnd, schermo, None, ctypes.byref(wt.SIZE(w, h)), mem,
                             ctypes.byref(wt.POINT(0, 0)), 0, ctypes.byref(blend), 2)  # ULW_ALPHA
    _gdi.SelectObject(mem, vecchio)
    _gdi.DeleteObject(bmp)
    _gdi.DeleteDC(mem)
    _u32.ReleaseDC(None, schermo)
