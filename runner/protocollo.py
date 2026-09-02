#! /usr/bin/env python3
"""
Protocollo di dialogo fra i runner e l'interfaccia.

I runner girano in un processo separato e scrivono su stdout una riga JSON per
evento. Il processo separato serve perche' i due backend manipolano stato
globale: VRR fa chdir() senza ripristinarla e importa parameters con
'from parameters import *', VRV azzera gli handler del logger. Isolandoli,
'Interrompi' diventa la semplice terminazione del processo e il calcolo del
rumore non puo' interferire con quello delle vibrazioni.

Eventi:
    {"tipo": "avvio",  "pipeline": ..., "passi": [{"chiave","nome"}, ...]}
    {"tipo": "passo",  "chiave", "nome", "indice", "totale", "stato"}
    {"tipo": "log",    "livello": "info"|"warning"|"error", "msg"}
    {"tipo": "fine",   "ok": bool, "durata": secondi}
"""

import importlib.util
import io
import json
import logging
import os
import sys
import time
from types import SimpleNamespace

# stdout reale, catturato prima di ogni redirezione: e' il canale degli eventi
_CANALE = sys.stdout

STATI = ('attesa', 'corso', 'fatto', 'errore', 'saltato')


def emetti(evento):
    """Scrive un evento sul canale, una riga per volta."""
    try:
        _CANALE.write(json.dumps(evento, ensure_ascii=False, default=str) + '\n')
        _CANALE.flush()
    except (OSError, ValueError):
        pass


def log(messaggio, livello='info'):
    for riga in str(messaggio).splitlines():
        if riga.strip():
            emetti({'tipo': 'log', 'livello': livello, 'msg': riga.rstrip()})


class _StdoutCatturato(io.TextIOBase):
    """
    Sostituisce sys.stdout dei backend trasformando ogni riga in un evento.

    VRR comunica stampando, e alcune utility di VRV pure: senza questa cattura
    quei messaggi finirebbero nel canale degli eventi rompendone il formato.
    """

    def __init__(self, livello='info'):
        self._livello = livello
        self._parziale = ''

    def write(self, testo):
        if not testo:
            return 0
        self._parziale += testo
        while '\n' in self._parziale:
            riga, self._parziale = self._parziale.split('\n', 1)
            if riga.strip():
                emetti({'tipo': 'log', 'livello': self._livello, 'msg': riga.rstrip()})
        return len(testo)

    def flush(self):
        if self._parziale.strip():
            emetti({'tipo': 'log', 'livello': self._livello,
                    'msg': self._parziale.rstrip()})
        self._parziale = ''

    def isatty(self):
        return False


class GestoreLog(logging.Handler):
    """Handler che inoltra i record del logger di VRV come eventi."""

    LIVELLI = {logging.DEBUG: 'info', logging.INFO: 'info',
               logging.WARNING: 'warning', logging.ERROR: 'error',
               logging.CRITICAL: 'error'}

    def emit(self, record):
        emetti({'tipo': 'log',
                'livello': self.LIVELLI.get(record.levelno, 'info'),
                'msg': record.getMessage()})


def cattura_stampe():
    """Redirige stdout e stderr dei backend verso il canale degli eventi."""
    sys.stdout = _StdoutCatturato('info')
    sys.stderr = _StdoutCatturato('warning')


def carica_modulo(cartella, nome):
    """Importa <cartella>/<nome>.py, come farebbe l'esecuzione diretta."""
    percorso = os.path.join(cartella, f'{nome}.py')
    if not os.path.exists(percorso):
        raise FileNotFoundError(f'Modulo non trovato: {percorso}')
    spec = importlib.util.spec_from_file_location(f'_bk_{nome}', percorso)
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def parametri_backend(modulo_parametri, sovrascritture):
    """
    Costruisce l'oggetto dei parametri da passare al backend.

    analisi() e i writer di VRV ricevono il modulo parameters e ne leggono gli
    attributi: va bene qualunque oggetto che li esponga. Si parte dai default
    del backend e si sovrascrive con quanto arriva dall'interfaccia, senza
    toccare il file parameters.py.
    """
    valori = {}
    if modulo_parametri is not None:
        for nome in dir(modulo_parametri):
            if not nome.startswith('_'):
                valori[nome] = getattr(modulo_parametri, nome)
    valori.update({k: v for k, v in (sovrascritture or {}).items()
                   if not k.startswith('_')})
    return SimpleNamespace(**valori)


class Sequenza:
    """
    Esecuzione ordinata dei passi di una pipeline, con eventi di avanzamento.

    Ogni passo e' (chiave, nome, funzione). Se una funzione solleva
    un'eccezione la sequenza si ferma e il passo viene marcato in errore; se
    restituisce la stringa 'saltato' il passo risulta saltato e si prosegue.
    """

    def __init__(self, pipeline, passi, offset=0, totale=None):
        self.pipeline = pipeline
        self.passi = passi
        self.offset = offset
        self.totale = totale if totale is not None else len(passi)
        self.risultati = {}

    def annuncia(self):
        emetti({'tipo': 'avvio', 'pipeline': self.pipeline,
                'passi': [{'chiave': c, 'nome': n} for c, n, _ in self.passi]})

    def _stato(self, chiave, nome, indice, stato, messaggio=''):
        emetti({'tipo': 'passo', 'chiave': chiave, 'nome': nome,
                'indice': indice, 'totale': self.totale,
                'stato': stato, 'msg': messaggio,
                'pipeline': self.pipeline})

    def esegui(self):
        """OUTPUT: True se tutti i passi sono andati a buon fine."""
        for posizione, (chiave, nome, funzione) in enumerate(self.passi):
            indice = self.offset + posizione + 1
            self._stato(chiave, nome, indice, 'corso')
            inizio = time.time()
            try:
                esito = funzione()
            except Exception as errore:
                sys.stdout.flush()
                log(f'{type(errore).__name__}: {errore}', 'error')
                self._stato(chiave, nome, indice, 'errore', str(errore))
                return False
            sys.stdout.flush()
            self.risultati[chiave] = esito
            durata = time.time() - inizio
            if esito == 'saltato':
                self._stato(chiave, nome, indice, 'saltato')
            else:
                self._stato(chiave, nome, indice, 'fatto', f'{durata:.1f}s')
        return True


def leggi_configurazione():
    """Legge il file JSON indicato dal primo argomento della riga di comando."""
    if len(sys.argv) < 2:
        raise SystemExit('uso: runner_*.py <configurazione.json>')
    with open(sys.argv[1], encoding='utf-8') as f:
        return json.load(f)
