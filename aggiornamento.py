"""Aggiornamento online del Convertitore installato.

La sfera chiama `controlla()` all'avvio e poi ogni 6 ore. Se su GitHub c'e' una
versione piu' nuova scarica il pacchetto di aggiornamento (pochi MB), ne controlla
l'impronta SHA-256 e lo installa in silenzio: l'installatore chiude la sfera,
sostituisce il programma e la riavvia. Funziona solo nella versione installata
(Convertitore.exe), non quando si lancia lo script Python di sviluppo.

Il file versione.json pubblicato con ogni release e' cosi':
    {"versione": "1.1", "file": "Convertitore-Aggiornamento.exe",
     "sha256": "...", "note": "cosa cambia"}
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

from versione import MANIFESTO, VERSIONE

INTESTAZIONI = {"User-Agent": f"Convertitore/{VERSIONE}"}


def numeri(v):
    return tuple(int(p) for p in str(v).split(".") if p.isdigit())


def leggi_manifesto(url=None):
    url = url or os.environ.get("CONVERTITORE_MANIFESTO") or MANIFESTO
    req = urllib.request.Request(url, headers=INTESTAZIONI)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8")), url


def scarica(manifesto, url_manifesto):
    """Scarica il pacchetto nella cartella temporanea e ne verifica l'impronta."""
    base = url_manifesto.rsplit("/", 1)[0]
    url = manifesto.get("url") or f"{base}/{manifesto['file']}"
    dest = os.path.join(tempfile.gettempdir(), f"Convertitore-{manifesto['versione']}.exe")
    req = urllib.request.Request(url, headers=INTESTAZIONI)
    h = hashlib.sha256()
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as fh:
        while True:
            pezzo = r.read(1 << 16)
            if not pezzo:
                break
            h.update(pezzo)
            fh.write(pezzo)
    if h.hexdigest().lower() != manifesto["sha256"].lower():
        os.remove(dest)
        raise RuntimeError("aggiornamento danneggiato (impronta diversa)")
    return dest


def controlla():
    """Restituisce (versione_nuova, percorso_scaricato) se c'e' un aggiornamento, altrimenti None."""
    if not getattr(sys, "frozen", False) and not os.environ.get("CONVERTITORE_MANIFESTO"):
        return None  # versione di sviluppo: niente aggiornamenti
    manifesto, url = leggi_manifesto()
    if numeri(manifesto["versione"]) <= numeri(VERSIONE):
        return None
    return manifesto["versione"], scarica(manifesto, url)


def installa(percorso):
    """Avvia l'installazione silenziosa; chiude e riavvia lei la sfera."""
    subprocess.Popen([percorso, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                     creationflags=0x00000008 | 0x00000200)  # DETACHED_PROCESS | NEW_PROCESS_GROUP
