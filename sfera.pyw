"""Avvio della sfera con Python (versione di sviluppo). Il codice e' in sfera.py."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sfera import main  # noqa: E402

main()
