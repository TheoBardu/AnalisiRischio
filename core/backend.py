#! /usr/bin/env python3
"""
Accesso ai due backend VRR_analisiDati e VRV_analisiDati.

I due progetti non sono pacchetti installabili (non hanno __init__.py) e
funzionano perche' Python aggiunge da solo la cartella dello script a sys.path.
Qui si fa la stessa cosa in modo esplicito, senza modificarli.

Nel processo della GUI si carica soltanto config.py, per leggere costanti di
layout come i nomi delle cartelle di misura. L'analisi vera gira nei runner,
in un processo separato: vedi core/esecuzione.py.
"""

import importlib.util
import os
import sys


def carica_modulo(cartella, nome):
    """
    Importa <cartella>/<nome>.py come modulo isolato.

    INPUT:  cartella - radice del progetto backend
            nome     - nome del modulo senza estensione
    OUTPUT: il modulo, oppure None se non caricabile
    """
    percorso = os.path.join(cartella, f'{nome}.py')
    if not os.path.exists(percorso):
        return None
    # nome univoco per non collidere con gli omonimi dell'altro backend
    chiave = f'_backend_{os.path.basename(cartella)}_{nome}'
    if chiave in sys.modules:
        return sys.modules[chiave]
    spec = importlib.util.spec_from_file_location(chiave, percorso)
    if spec is None or spec.loader is None:
        return None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[chiave] = modulo
    try:
        spec.loader.exec_module(modulo)
    except Exception:
        del sys.modules[chiave]
        return None
    return modulo


def prepara_sys_path(cartella):
    """Mette 'cartella' in testa a sys.path, come fa l'esecuzione diretta."""
    cartella = os.path.abspath(cartella)
    if cartella not in sys.path:
        sys.path.insert(0, cartella)
    return cartella
