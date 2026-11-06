"""Impostazioni del Convertitore (finestra + salvataggio).

Si apre dal menu della sfera ("Impostazioni..."). Ogni scelta si salva subito in
%APPDATA%\\Convertitore\\impostazioni.json; la ruota le rilegge a ogni conversione.
"""
import json
import os
import sys

CARTELLA_DATI = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "Convertitore")
PERCORSO = os.path.join(CARTELLA_DATI, "impostazioni.json")
PREDEFINITE = {
    "cartella": "",          # "" = accanto all'originale, altrimenti una cartella fissa
    "esistente": "copia",    # "copia" = foto (1).jpg, "sostituisci" = sovrascrive il file convertito
    "leggero": "medio",      # "poco" | "medio" | "molto"
    "lingua": "auto",        # "auto" | "it" | "en"
}
QUI = os.path.dirname(os.path.abspath(__file__))
FROZEN = getattr(sys, "frozen", False)


def leggi():
    dati = dict(PREDEFINITE)
    try:
        with open(PERCORSO, encoding="utf-8") as fh:
            salvate = json.load(fh)
        dati.update({k: v for k, v in salvate.items() if k in PREDEFINITE})
    except (OSError, ValueError):
        pass
    return dati


def scrivi(**valori):
    dati = leggi()
    dati.update({k: v for k, v in valori.items() if k in PREDEFINITE})
    try:
        os.makedirs(CARTELLA_DATI, exist_ok=True)
        with open(PERCORSO, "w", encoding="utf-8") as fh:
            json.dump(dati, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return dati


# ---------------------------------------------------------------- avvio con Windows
def _collegamento_avvio():
    return os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs\Startup",
                        "Convertitore sfera.lnk")


def avvio_con_windows():
    return os.path.exists(_collegamento_avvio())


def imposta_avvio(attivo):
    lnk = _collegamento_avvio()
    if not attivo:
        try:
            os.remove(lnk)
        except OSError:
            pass
        return
    import win32com.client
    sc = win32com.client.Dispatch("WScript.Shell").CreateShortcut(lnk)
    if FROZEN:
        sc.TargetPath, sc.Arguments = sys.executable, "--sfera"
        sc.IconLocation = sys.executable + ",0"
    else:
        sc.TargetPath = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        sc.Arguments = f'"{os.path.join(QUI, "sfera.pyw")}"'
    sc.WorkingDirectory = os.path.dirname(sys.executable) if FROZEN else QUI
    sc.Save()


# ---------------------------------------------------------------- finestra
def finestra():
    import ctypes
    import tkinter as tk
    from tkinter import filedialog

    from testi import t
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
        z = ctypes.windll.user32.GetDpiForSystem() / 96
    except Exception:
        z = 1.0

    BG, CARTA, CARTA2 = "#0e111b", "#171b28", "#212738"
    INK, INK2, INK3, ACC, ACC_INK = "#f1f5ff", "#a3adc8", "#6b7694", "#38bdf8", "#08111d"
    F = "Bahnschrift"

    def px(v):
        return int(v * z)

    root = tk.Tk()
    root.title(t("Impostazioni") + " · Convertitore")
    root.configure(bg=BG)
    root.resizable(False, False)
    ico = os.path.join(os.path.dirname(sys.executable) if FROZEN else QUI, "convertitore.ico")
    for c in (ico, os.path.join(getattr(sys, "_MEIPASS", QUI), "convertitore.ico")):
        if os.path.exists(c):
            root.iconbitmap(c)
            break
    try:  # barra del titolo scura
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 20, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass

    imp = leggi()
    corpo = tk.Frame(root, bg=BG, padx=px(28), pady=px(22))
    corpo.pack(fill="both", expand=True)
    tk.Label(corpo, text=t("Impostazioni"), bg=BG, fg=INK, font=(F, -px(24), "bold"), anchor="w").pack(fill="x")
    tk.Label(corpo, text=t("Ogni scelta si salva subito."), bg=BG, fg=INK3, font=(F, -px(13)), anchor="w").pack(fill="x", pady=(px(2), px(14)))

    def sezione(titolo, spiegazione=None):
        box = tk.Frame(corpo, bg=CARTA, padx=px(16), pady=px(14), highlightthickness=1, highlightbackground="#262c3d")
        box.pack(fill="x", pady=(0, px(10)))
        tk.Label(box, text=titolo, bg=CARTA, fg=INK, font=(F, -px(15), "bold"), anchor="w").pack(fill="x")
        if spiegazione:
            tk.Label(box, text=spiegazione, bg=CARTA, fg=INK3, font=(F, -px(12)), anchor="w", justify="left",
                     wraplength=px(400)).pack(fill="x", pady=(px(2), 0))
        return box

    def pillole(box, chiave, scelte, al_cambio=None):
        """Selettore a pillole: una sola scelta attiva, evidenziata in azzurro."""
        riga = tk.Frame(box, bg=CARTA)
        riga.pack(fill="x", pady=(px(10), 0))
        etichette = {}

        def ridisegna():
            for valore, lab in etichette.items():
                attiva = imp[chiave] == valore
                lab.configure(bg=ACC if attiva else CARTA2, fg=ACC_INK if attiva else INK2)

        def scegli(valore):
            imp[chiave] = valore
            scrivi(**{chiave: valore})
            ridisegna()
            if al_cambio:
                al_cambio(valore)
        for valore, testo in scelte:
            lab = tk.Label(riga, text=testo, font=(F, -px(13)), padx=px(12), pady=px(6), cursor="hand2")
            lab.pack(side="left", padx=(0, px(6)))
            lab.bind("<Button-1>", lambda e, v=valore: scegli(v))
            lab.bind("<Enter>", lambda e, l=lab, v=valore: l.configure(fg=INK) if imp[chiave] != v else None)
            lab.bind("<Leave>", lambda e: ridisegna())
            etichette[valore] = lab
        ridisegna()
        return ridisegna

    # dove salvare
    box = sezione(t("Dove salvo i file convertiti"))
    percorso = tk.Label(box, bg=CARTA, fg=INK3, font=(F, -px(12)), anchor="w", justify="left", wraplength=px(400))

    def mostra_cartella(_=None):
        if imp["cartella"]:
            percorso.configure(text=imp["cartella"])
            percorso.pack(fill="x", pady=(px(8), 0))
        else:
            percorso.pack_forget()

    def cambio_cartella(valore):
        if valore == "fissa":
            scelta = filedialog.askdirectory(parent=root, title=t("Dove salvo i file convertiti"),
                                             initialdir=imp["cartella"] or os.path.expanduser("~"))
            imp["cartella"] = os.path.normpath(scelta) if scelta else imp["cartella"]
        else:
            imp["cartella"] = ""
        scrivi(cartella=imp["cartella"])
        imp["_dove"] = "fissa" if imp["cartella"] else "accanto"
        ridisegna_dove()
        mostra_cartella()

    imp["_dove"] = "fissa" if imp["cartella"] else "accanto"
    riga = tk.Frame(box, bg=CARTA)
    riga.pack(fill="x", pady=(px(10), 0))
    dove = {}

    def ridisegna_dove():
        for v, lab in dove.items():
            att = imp["_dove"] == v
            lab.configure(bg=ACC if att else CARTA2, fg=ACC_INK if att else INK2)
    for valore, testo in (("accanto", t("Accanto all'originale")), ("fissa", t("In una cartella fissa…"))):
        lab = tk.Label(riga, text=testo, font=(F, -px(13)), padx=px(12), pady=px(6), cursor="hand2")
        lab.pack(side="left", padx=(0, px(6)))
        lab.bind("<Button-1>", lambda e, v=valore: cambio_cartella(v))
        dove[valore] = lab
    ridisegna_dove()
    mostra_cartella()

    box = sezione(t("Se il file esiste già"))
    pillole(box, "esistente", (("copia", t("Crea una copia numerata")), ("sostituisci", t("Sostituiscilo"))))

    box = sezione(t("Quanto alleggerire con LEGGERO"), t("Più alleggerisci, più si perde qualità."))
    pillole(box, "leggero", (("poco", t("Poco")), ("medio", t("Medio")), ("molto", t("Molto"))))

    box = sezione(t("Lingua"), t("Vale dalla prossima ruota che si apre."))
    pillole(box, "lingua", (("auto", t("Come Windows")), ("it", "Italiano"), ("en", "English")))

    box = sezione(t("Sfera"))
    imp["_avvio"] = "si" if avvio_con_windows() else "no"
    pillole(box, "_avvio", (("si", t("Parte con Windows")), ("no", t("Solo quando la apro"))),
            al_cambio=lambda v: imposta_avvio(v == "si"))

    fondo = tk.Frame(corpo, bg=BG)
    fondo.pack(fill="x", pady=(px(6), 0))
    licenze = os.path.join(os.path.dirname(sys.executable) if FROZEN else QUI, "licenze-terze-parti.txt")
    if os.path.exists(licenze):
        link = tk.Label(fondo, text=t("Licenze di terze parti"), bg=BG, fg=INK3, font=(F, -px(12), "underline"),
                        cursor="hand2")
        link.pack(side="left")
        link.bind("<Button-1>", lambda e: os.startfile(licenze))
    chiudi = tk.Label(fondo, text=t("Chiudi"), bg=ACC, fg=ACC_INK, font=(F, -px(14), "bold"), padx=px(22), pady=px(8),
                      cursor="hand2")
    chiudi.pack(side="right")
    chiudi.bind("<Button-1>", lambda e: root.destroy())
    root.bind("<Escape>", lambda e: root.destroy())
    root.update_idletasks()
    w, h = root.winfo_reqwidth(), root.winfo_reqheight()
    root.geometry(f"{w}x{h}+{(root.winfo_screenwidth() - w) // 2}+{(root.winfo_screenheight() - h) // 3}")
    root.lift()
    root.focus_force()
    root.mainloop()


if __name__ == "__main__":
    finestra()
