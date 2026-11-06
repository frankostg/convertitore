"""Punto di ingresso di Convertitore.exe (versione installata).

    Convertitore.exe                 -> finestra classica
    Convertitore.exe file...         -> ruota delle conversioni sopra il mouse
    Convertitore.exe --ruota         -> ruota con tutte le conversioni possibili
    Convertitore.exe --sfera         -> la sfera sempre in primo piano
    Convertitore.exe --registra      -> aggiunge "Converti..." al tasto destro
    Convertitore.exe --rimuovi       -> lo toglie (usato dalla disinstallazione)
"""
import sys


def main():
    primo = sys.argv[1] if len(sys.argv) > 1 else ""
    if primo == "--sfera":
        import sfera
        sfera.main()
    elif primo == "--prova":
        # diagnosi: Convertitore.exe --prova <formato> <file...>  -> scrive prova.log accanto al primo file
        import os
        import convertitore
        key, files = sys.argv[2], sys.argv[3:]
        cat, opz = convertitore.opzioni_per(files)
        outs, errori = convertitore.converti(files, cat, key, lambda *a: None)
        with open(os.path.join(os.path.dirname(files[0]), "prova.log"), "a", encoding="utf-8") as fh:
            fh.write(f"{key}: creati={[os.path.basename(o) for o in outs]} errori={errori} ffmpeg={convertitore.trova_ffmpeg()}\n")
    elif primo in ("--registra", "--rimuovi"):
        import installa_menu
        installa_menu.main(rimuovi=(primo == "--rimuovi"))
    else:
        import convertitore
        convertitore.main()


if __name__ == "__main__":
    main()
