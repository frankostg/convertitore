"""Aggiunge (o toglie) la voce "Converti..." al menu del tasto destro di Esplora file.

    pythonw installa_menu.py           -> aggiunge la voce
    pythonw installa_menu.py --rimuovi -> la toglie

Scrive solo nel registro dell'utente (HKCU), non servono permessi di amministratore.
La voce compare solo sui formati che il Convertitore sa gestire.
"""
import ctypes
import os
import sys
import winreg

QUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, QUI)
from convertitore import CATEGORIE  # noqa: E402

PYW = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
SCRIPT = os.path.join(QUI, "convertitore.py")
ICONA = os.path.join(QUI, "convertitore.ico")
if getattr(sys, "frozen", False):  # installato come Convertitore.exe
    COMANDO = f'"{sys.executable}" "%1"'
    ICONA = sys.executable + ",0"
else:
    COMANDO = f'"{PYW}" "{SCRIPT}" "%1"'
BASE = r"Software\Classes\SystemFileAssociations\.{ext}\shell\Convertitore"
CARTELLE = r"Software\Classes\Directory\shell\Convertitore"


def elimina_albero(radice, percorso):
    try:
        with winreg.OpenKey(radice, percorso, 0, winreg.KEY_ALL_ACCESS) as k:
            while True:
                try:
                    figlio = winreg.EnumKey(k, 0)
                except OSError:
                    break
                elimina_albero(radice, percorso + "\\" + figlio)
        winreg.DeleteKey(radice, percorso)
    except FileNotFoundError:
        pass


def main(rimuovi=None):
    if rimuovi is None:
        rimuovi = "--rimuovi" in sys.argv
    from testi import t
    estensioni = sorted({e for exts in CATEGORIE.values() for e in exts})
    # ogni formato supportato + le cartelle (converte tutto quello che contengono)
    chiavi = [BASE.format(ext=ext) for ext in estensioni] + [CARTELLE]
    for chiave in chiavi:
        if rimuovi:
            elimina_albero(winreg.HKEY_CURRENT_USER, chiave)
            continue
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chiave) as k:
            winreg.SetValueEx(k, "MUIVerb", 0, winreg.REG_SZ, t("Converti…"))
            winreg.SetValueEx(k, "Icon", 0, winreg.REG_SZ, ICONA)
            winreg.SetValueEx(k, "MultiSelectModel", 0, winreg.REG_SZ, "Player")
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, chiave + r"\command") as k:
            winreg.SetValueEx(k, "", 0, winreg.REG_SZ, COMANDO)
    # avvisa Esplora file che le associazioni sono cambiate
    ctypes.windll.shell32.SHChangeNotify(0x08000000, 0, None, None)
    print(("Rimossa" if rimuovi else "Aggiunta") + f" la voce su {len(estensioni)} formati e sulle cartelle.")


if __name__ == "__main__":
    main()
