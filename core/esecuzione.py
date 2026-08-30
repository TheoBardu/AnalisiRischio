#! /usr/bin/env python3
"""
Avvio e sorveglianza delle pipeline.

Ogni pipeline gira in un processo separato: i due backend manipolano stato
globale (VRR entra nella cartella delle misure, VRV azzera gli handler del
logger) e soprattutto importano entrambi un modulo chiamato 'config', che nello
stesso interprete si sovrapporrebbe. In modalita' combinata si eseguono quindi
due processi in sequenza, non un processo solo.

Gli eventi arrivano come righe JSON su stdout e vengono inoltrati a una
callback. 'Interrompi' termina il processo in corso e annulla quelli in coda.
"""

import json
import os
import subprocess
import sys
import tempfile
import threading
import time

from runner import passi as elenco_passi

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

RUNNER = {
    'rumore': os.path.join(CARTELLA_PROGETTO, 'runner', 'runner_rumore.py'),
    'vibrazioni': os.path.join(CARTELLA_PROGETTO, 'runner', 'runner_vibrazioni.py'),
}

ATTESA_TERMINAZIONE = 5     # secondi concessi prima di forzare la chiusura


class Esecuzione:
    """
    Coda di pipeline da eseguire, con inoltro degli eventi.

    USO:
        esecuzione = Esecuzione(su_evento)
        esecuzione.avvia('combinato', cfg_rumore, cfg_vibrazioni)
        ...
        esecuzione.interrompi()
    """

    def __init__(self, su_evento):
        self._su_evento = su_evento
        self._processo = None
        self._thread = None
        self._interrotta = False
        self._lock = threading.Lock()
        self.in_corso = False
        self.modalita = ''

    # ------------------------------------------------------------------
    def avvia(self, modalita, configurazioni):
        """
        INPUT:  modalita        - 'rumore', 'vibrazioni' oppure 'combinato'
                configurazioni  - dict pipeline -> configurazione del runner
        OUTPUT: {'ok', 'errore', 'passi'}
        """
        if self.in_corso:
            return {'ok': False, 'errore': 'Un\'analisi e\' gia\' in corso.',
                    'passi': []}

        pipeline = (['rumore', 'vibrazioni'] if modalita == 'combinato'
                    else [modalita])
        mancanti = [p for p in pipeline if p not in configurazioni]
        if mancanti:
            return {'ok': False,
                    'errore': f'Configurazione assente per: {", ".join(mancanti)}',
                    'passi': []}

        passi = elenco_passi.passi_di(modalita)
        self._interrotta = False
        self.in_corso = True
        self.modalita = modalita

        self._su_evento({'tipo': 'avvio', 'modalita': modalita, 'passi': passi})
        self._thread = threading.Thread(
            target=self._esegui_coda, args=(pipeline, configurazioni, len(passi)),
            daemon=True)
        self._thread.start()
        return {'ok': True, 'errore': '', 'passi': passi}

    # ------------------------------------------------------------------
    def interrompi(self):
        """Termina il processo in corso e annulla la coda."""
        with self._lock:
            self._interrotta = True
            processo = self._processo
        if processo and processo.poll() is None:
            processo.terminate()
            try:
                processo.wait(timeout=ATTESA_TERMINAZIONE)
            except subprocess.TimeoutExpired:
                processo.kill()
            return True
        return False

    # ------------------------------------------------------------------
    def _esegui_coda(self, pipeline, configurazioni, totale):
        inizio = time.time()
        offset = 0
        ok = True
        for nome_pipeline in pipeline:
            if self._interrotta:
                ok = False
                break
            n_passi = len(elenco_passi.PER_PIPELINE[nome_pipeline])
            cfg = dict(configurazioni[nome_pipeline])
            cfg['offset'] = offset
            cfg['totale'] = totale
            esito = self._esegui_una(nome_pipeline, cfg)
            offset += n_passi
            if not esito:
                ok = False
                break

        self.in_corso = False
        with self._lock:
            self._processo = None
        if self._interrotta:
            self._su_evento({'tipo': 'interrotta'})
        self._su_evento({'tipo': 'fine', 'ok': ok,
                         'durata': round(time.time() - inizio, 1)})

    # ------------------------------------------------------------------
    def _esegui_una(self, nome_pipeline, cfg):
        """Lancia un runner e inoltra i suoi eventi. OUTPUT: True se ok."""
        script = RUNNER[nome_pipeline]
        percorso_cfg = self._scrivi_configurazione(cfg)
        comando = [sys.executable, '-u', script, percorso_cfg]

        ambiente = dict(os.environ)
        ambiente['PYTHONUNBUFFERED'] = '1'
        # senza questo i backend che stampano caratteri accentati possono
        # fallire quando stdout non e' un terminale
        ambiente['PYTHONIOENCODING'] = 'utf-8'

        try:
            processo = subprocess.Popen(
                comando, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=CARTELLA_PROGETTO, env=ambiente,
                text=True, encoding='utf-8', errors='replace', bufsize=1)
        except OSError as errore:
            self._su_evento({'tipo': 'log', 'livello': 'error',
                             'msg': f'Avvio del runner non riuscito: {errore}'})
            return False

        with self._lock:
            self._processo = processo

        ok_runner = True
        try:
            for riga in processo.stdout:
                riga = riga.strip()
                if not riga:
                    continue
                evento = self._interpreta(riga, nome_pipeline)
                if evento.get('tipo') == 'fine':
                    # la fine della singola pipeline non e' la fine della coda
                    ok_runner = bool(evento.get('ok'))
                    continue
                if evento.get('tipo') == 'avvio':
                    # il runner annuncia i propri passi perche' e' usabile anche
                    # da solo; qui l'elenco completo, che in modalita' combinata
                    # comprende entrambe le pipeline, e' gia' stato annunciato
                    continue
                evento.setdefault('pipeline', nome_pipeline)
                self._su_evento(evento)
        finally:
            processo.stdout.close()
            codice = processo.wait()
            try:
                os.remove(percorso_cfg)
            except OSError:
                pass

        if self._interrotta:
            return False
        if codice != 0 and ok_runner:
            self._su_evento({'tipo': 'log', 'livello': 'error',
                             'msg': f'Il runner {nome_pipeline} e\' uscito '
                                    f'con codice {codice}.'})
            return False
        return ok_runner

    # ------------------------------------------------------------------
    @staticmethod
    def _interpreta(riga, nome_pipeline):
        """
        Riga di stdout -> evento.

        Tutto cio' che non e' JSON valido e' comunque output del backend e
        merita di comparire nel log invece di essere buttato via.
        """
        try:
            evento = json.loads(riga)
            if isinstance(evento, dict) and 'tipo' in evento:
                return evento
        except json.JSONDecodeError:
            pass
        return {'tipo': 'log', 'livello': 'info', 'msg': riga,
                'pipeline': nome_pipeline}

    # ------------------------------------------------------------------
    @staticmethod
    def _scrivi_configurazione(cfg):
        descrittore, percorso = tempfile.mkstemp(
            prefix='analisirischio_', suffix='.json')
        with os.fdopen(descrittore, 'w', encoding='utf-8') as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        return percorso
