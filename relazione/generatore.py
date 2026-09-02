#! /usr/bin/env python3
"""
Generazione della relazione .docx.

La scrittura vera sta in runner/runner_relazione.py, che gira in un processo
separato e usa i write_docx dei due backend: i due progetti importano entrambi
un modulo chiamato 'config', con contenuti diversi, quindi non possono
convivere nello stesso interprete. Qui si lancia quel processo, si traducono le
righe JSON che scrive in eventi per l'interfaccia e si raccoglie l'esito.

A differenza di core/esecuzione.py la chiamata e' sincrona: la scrittura di un
documento dura pochi secondi e il ponte con la pagina e' gia' sincrono.
"""

import json
import os
import subprocess
import sys

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(CARTELLA_PROGETTO, 'runner', 'runner_relazione.py')

DISPONIBILE = True

NOME_DOCUMENTO = {'rumore': 'Relazione_RUM.docx', 'vibrazioni': 'Relazione_VIB.docx'}


def genera(cfg, su_evento=None):
    """
    Scrive la relazione di un ramo lanciando il runner.

    INPUT:  cfg       - configurazione del runner (vedi runner_relazione.py)
            su_evento - callback opzionale per gli eventi di avanzamento
    OUTPUT: {'ok', 'documento', 'messaggio', 'log': [...]}
    """
    ramo = cfg.get('ramo', 'rumore')
    ambiente = dict(os.environ)
    ambiente['PYTHONUNBUFFERED'] = '1'
    # senza questo i backend che stampano caratteri accentati possono fallire
    # quando stdout non e' un terminale
    ambiente['PYTHONIOENCODING'] = 'utf-8'

    percorso_cfg = _scrivi_configurazione(cfg)
    try:
        processo = subprocess.run(
            [sys.executable, '-u', RUNNER, percorso_cfg],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=CARTELLA_PROGETTO, env=ambiente,
            text=True, encoding='utf-8', errors='replace')
    except OSError as errore:
        return {'ok': False, 'documento': '', 'log': [],
                'messaggio': f'Avvio del generatore non riuscito: {errore}'}
    finally:
        try:
            os.remove(percorso_cfg)
        except OSError:
            pass

    return _raccogli(processo, ramo, su_evento)


def _raccogli(processo, ramo, su_evento):
    """
    Righe di stdout del runner -> esito e registro.

    Gli eventi 'avvio' e 'passo' non vengono inoltrati come sono: la schermata
    del log li userebbe per ridisegnare l'elenco dei passi dell'analisi, che qui
    non c'entra. L'avanzamento diventa quindi una riga di registro.
    """
    ok = None
    documento = ''
    registro = []
    ultimo_errore = ''

    def inoltra(evento):
        registro.append(evento)
        if su_evento is not None:
            su_evento(evento)

    for riga in processo.stdout.splitlines():
        riga = riga.strip()
        if not riga:
            continue
        evento = _interpreta(riga, ramo)
        tipo = evento.get('tipo')

        if tipo == 'fine':
            ok = bool(evento.get('ok'))
            documento = evento.get('documento', '')
        elif tipo == 'avvio':
            continue
        elif tipo == 'passo':
            if evento.get('stato') == 'corso':
                inoltra({'tipo': 'log', 'livello': 'info', 'pipeline': ramo,
                         'msg': f'▸ relazione {ramo}: {evento.get("nome", "")}'})
            elif evento.get('stato') == 'errore':
                ultimo_errore = evento.get('msg', '') or ultimo_errore
                inoltra({'tipo': 'log', 'livello': 'error', 'pipeline': ramo,
                         'msg': f'✕ relazione {ramo}: {evento.get("nome", "")} '
                                f'{evento.get("msg", "")}'.rstrip()})
        elif tipo == 'log':
            if evento.get('livello') == 'error':
                ultimo_errore = evento.get('msg', '')
            inoltra(evento)

    if ok is None:
        ok = processo.returncode == 0
    if ok:
        messaggio = f'documento scritto in {documento}' if documento else 'documento scritto'
    else:
        messaggio = ultimo_errore or 'scrittura non riuscita'
    return {'ok': ok, 'documento': documento, 'messaggio': messaggio,
            'log': registro}


def _interpreta(riga, ramo):
    """Tutto cio' che non e' JSON valido e' comunque output del backend."""
    try:
        evento = json.loads(riga)
        if isinstance(evento, dict) and 'tipo' in evento:
            evento.setdefault('pipeline', ramo)
            return evento
    except json.JSONDecodeError:
        pass
    return {'tipo': 'log', 'livello': 'info', 'msg': riga, 'pipeline': ramo}


def _scrivi_configurazione(cfg):
    import tempfile
    descrittore, percorso = tempfile.mkstemp(prefix='relazione_', suffix='.json')
    with os.fdopen(descrittore, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=1, default=str)
    return percorso


def stato(template, frontespizio='', output=''):
    """
    Descrive se e cosa si puo' generare, per il messaggio dell'interfaccia.

    OUTPUT: {'disponibile', 'messaggio', 'template_presente', 'frontespizio_presente'}
    """
    template_presente = bool(template) and os.path.exists(template)
    frontespizio_presente = bool(frontespizio) and os.path.exists(frontespizio)

    if not template_presente:
        messaggio = f'Modello non trovato: {template or "(non impostato)"}'
    elif not frontespizio_presente:
        messaggio = f'Frontespizio non trovato: {frontespizio or "(non impostato)"}'
    else:
        messaggio = f'Pronto a scrivere {os.path.basename(output or "")}'
    return {'disponibile': template_presente and frontespizio_presente,
            'messaggio': messaggio,
            'template_presente': template_presente,
            'frontespizio_presente': frontespizio_presente}
