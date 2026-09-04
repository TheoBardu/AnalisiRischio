#! /usr/bin/env python3
"""
Profili temporali del LeqA delle misure fonometriche ("spettri").

VRR legge i file grezzi del fonometro ma ne restituisce solo l'aggregato per
traccia: il profilo secondo per secondo non esce mai da
files.read_measure_file, e i file scritti in misure/data/ contengono lo stesso
aggregato. Qui si rileggono gli stessi file, con la stessa logica di
individuazione e di numerazione delle misure (primo csv di misD -> D1, poi D2,
...), per tenerne in memoria il profilo e disegnarlo.

Niente di quello che si legge viene scritto su disco: l'unica uscita su file e'
il PDF che l'utente chiede esplicitamente.
"""

import base64
import glob
import io
import os
import re

from core import progetto, risultati_rumore

# scarti della scansione delle cartelle di misura, come in VRR (manager.__init__)
SCARTI = {'.ds_store', 'data', 'vr_8h.csv', 'vr_8h.xlsx', 'vr_rumore.out'}

FOGLIO_MANSIONI = 'Scheda_mansioni'
FOGLIO_XLSX_RIPIEGO = 'Profilo storico'

NOME_PDF = 'Spettri.pdf'


# --------------------------------------------------------------------------
# Individuazione dei file, identica a quella di VRR
# --------------------------------------------------------------------------

def _foglio_xlsx():
    """Nome del foglio del profilo storico, letto da VRR/config.py."""
    from core import backend, configurazione
    cfg = backend.carica_modulo(configurazione.config().get('percorso_vrr', ''), 'config')
    return getattr(cfg, 'SHEET_NAME_XLSX', FOGLIO_XLSX_RIPIEGO) if cfg else FOGLIO_XLSX_RIPIEGO


def _file_csv(cartella, versione):
    """
    File csv di una cartella di misura, nell'ordine con cui VRR li numera.

    Firmware '1': i csv stanno tutti nella cartella. Firmware '2': stanno in
    sottocartelle con suffisso _0001, _0002, ... da percorrere in ordine.
    """
    if str(versione) == '1':
        elenco = glob.glob(os.path.join(cartella, '*.csv'))
    else:
        sottocartelle = [d for d in glob.glob(os.path.join(cartella, '*'))
                         if os.path.isdir(d) and re.search(r'_(\d+)$', d)]
        sottocartelle.sort(key=lambda d: int(re.search(r'_(\d+)$', d).group(1)))
        elenco = []
        for sottocartella in sottocartelle:
            elenco.extend(sorted(glob.glob(os.path.join(sottocartella, '*.csv'))))
    elenco.sort()
    return elenco


def _file_xlsx(cartella):
    elenco = sorted(glob.glob(os.path.join(cartella, '*.xlsx')))
    return [f for f in elenco if not os.path.basename(f).startswith('~$')]


# --------------------------------------------------------------------------
# Lettura dei profili
# --------------------------------------------------------------------------

def _profilo_csv(percorso):
    """(tempi in secondi, LeqA) da un csv del fonometro."""
    import pandas as pd
    df = pd.read_csv(percorso, encoding='latin', skiprows=1, sep=';', engine='python')
    tempo = pd.to_datetime(df.iloc[:, 0], format='%H:%M:%S', errors='coerce')
    leq = pd.to_numeric(df['LAeq'], errors='coerce')
    tenute = tempo.notna() & leq.notna()
    tempo, leq = tempo[tenute], leq[tenute]
    if tempo.empty:
        return [], []
    tempi = (tempo - tempo.iloc[0]).dt.total_seconds()
    return [float(t) for t in tempi], [float(v) for v in leq]


def _profilo_xlsx(percorso, foglio):
    """(tempi in secondi, LeqA) da un xlsx 'Profilo storico'."""
    import pandas as pd
    df = pd.read_excel(percorso, sheet_name=foglio)
    # colonne per posizione come in VRR: 1 = data/ora, 2 = LAeq
    tempo = pd.to_datetime(df.iloc[:, 1], format='%Y-%m-%d  %H:%M:%S', errors='coerce')
    leq = pd.to_numeric(df.iloc[:, 2], errors='coerce')
    tenute = tempo.notna() & leq.notna()
    tempo, leq = tempo[tenute], leq[tenute]
    if tempo.empty:
        return [], []
    tempi = (tempo - tempo.iloc[0]).dt.total_seconds()
    return [float(t) for t in tempi], [float(v) for v in leq]


# --------------------------------------------------------------------------
# Anagrafica delle misure (scheda_gruppi_dpi.xlsx)
# --------------------------------------------------------------------------

def _testo(valore):
    testo = '' if valore is None else str(valore).strip()
    return '' if testo.lower() == 'nan' else testo


def _anagrafica(percorso_scheda):
    """
    ID_misura -> {descrizione, grom, grom_nome}, dal foglio 'Scheda_mansioni'.

    E' la stessa lettura di analisi.get_scheda_info: si usa questa e non i
    fogli 'Scheda N' perche' gli spettri si guardano anche prima di lanciare
    l'analisi, quando VR8h_totale.xlsx non esiste ancora.
    """
    if not percorso_scheda or not os.path.exists(percorso_scheda):
        return {}, ['scheda_gruppi_dpi.xlsx non trovata: gli spettri restano senza descrizione.']
    try:
        import pandas as pd
        df = pd.read_excel(percorso_scheda, sheet_name=FOGLIO_MANSIONI, header=1, dtype=str)
    except Exception as errore:
        return {}, [f'scheda_gruppi_dpi.xlsx non leggibile: {errore}']

    mappa = {}
    for _, riga in df.iterrows():
        identificativo = _testo(riga.get('ID_misura'))
        if not identificativo:
            continue
        mappa[identificativo.upper()] = {
            'descrizione': _testo(riga.get('Descrizione_compito')),
            'grom': _testo(riga.get('ID_GrOm')),
            'grom_nome': _testo(riga.get('Descrizione_GrOm')),
        }
    return mappa, []


# --------------------------------------------------------------------------
# Caricamento
# --------------------------------------------------------------------------

def carica(cartella_misure, percorso_scheda='', versione_firmware='2'):
    """
    Legge in memoria i profili temporali di tutte le misure.

    INPUT:  cartella_misure   - <Rumore>/misure
            percorso_scheda   - scheda_gruppi_dpi.xlsx (compito e GrOm)
            versione_firmware - '1' o '2', come in VRR
    OUTPUT: {'cartella', 'misure': [{id, descrizione, grom, grom_nome,
             cartella, file, t, leq, errore}], 'avvisi': [...]}
    """
    esito = {'cartella': cartella_misure or '', 'misure': [], 'avvisi': []}
    if not cartella_misure or not os.path.isdir(cartella_misure):
        esito['avvisi'].append('Cartella delle misure non trovata.')
        return esito

    formati = progetto._formati_rumore()
    per_nome = {nome.lower(): formato
                for formato, nomi in formati.items() for nome in nomi}
    anagrafica, avvisi = _anagrafica(percorso_scheda)
    esito['avvisi'].extend(avvisi)
    foglio = _foglio_xlsx()

    senza_scheda = []
    for nome in sorted(os.listdir(cartella_misure)):
        percorso = os.path.join(cartella_misure, nome)
        if nome.lower() in SCARTI or not os.path.isdir(percorso):
            continue
        formato = per_nome.get(nome.lower())
        if formato is None:
            esito['avvisi'].append(f'{nome}: cartella non riconosciuta, saltata.')
            continue
        if formato == 'txt':
            esito['avvisi'].append(
                f'{nome}: i file txt non contengono il profilo nel tempo, spettro non disponibile.')
            continue

        lettera = nome[-1].upper()
        elenco = (_file_csv(percorso, versione_firmware) if formato == 'csv'
                  else _file_xlsx(percorso))
        if not elenco:
            esito['avvisi'].append(f'{nome}: nessun file {formato} trovato.')
            continue

        for indice, file_misura in enumerate(elenco, start=1):
            identificativo = f'{lettera}{indice}'
            voce = {'id': identificativo, 'cartella': nome, 'errore': '',
                    'file': os.path.relpath(file_misura, cartella_misure),
                    't': [], 'leq': []}
            voce.update(anagrafica.get(identificativo.upper(),
                                       {'descrizione': '', 'grom': '', 'grom_nome': ''}))
            if identificativo.upper() not in anagrafica:
                senza_scheda.append(identificativo)
            try:
                if formato == 'csv':
                    voce['t'], voce['leq'] = _profilo_csv(file_misura)
                else:
                    voce['t'], voce['leq'] = _profilo_xlsx(file_misura, foglio)
            except Exception as errore:
                voce['errore'] = f'{type(errore).__name__}: {errore}'
            if not voce['errore'] and not voce['leq']:
                voce['errore'] = 'file senza dati leggibili'
            esito['misure'].append(voce)

    if senza_scheda:
        esito['avvisi'].append(
            'Misure non presenti nella scheda mansioni: ' + ', '.join(senza_scheda))
    return esito


# --------------------------------------------------------------------------
# Grafici
# --------------------------------------------------------------------------

def _chiave_id(identificativo):
    trovato = re.match(r'([A-Za-z]*)(\d*)', str(identificativo))
    return (trovato.group(1), int(trovato.group(2) or 0))


def ordina(misure, per_gruppo=False):
    """Misure nell'ordine della vista: per GrOm, oppure per ID."""
    if per_gruppo:
        return sorted(misure, key=lambda m: (
            risultati_rumore._chiave_ordinamento(m.get('grom') or ''),
            _chiave_id(m['id'])))
    return sorted(misure, key=lambda m: _chiave_id(m['id']))


def titolo(misura, per_gruppo=False):
    """Titolo del grafico: ID, compito e, nella vista per gruppo, il GrOm."""
    parti = [misura['id']]
    if misura.get('descrizione'):
        parti.append(misura['descrizione'])
    testo = ' - '.join(parti)
    if per_gruppo and misura.get('grom'):
        testo = f'GrOm {misura["grom"]} · {testo}'
    return testo


def _disegna(asse, misura):
    asse.plot(misura['t'], misura['leq'], linewidth=1.8, color='#2a7fd4')
    asse.set_xlabel('tempo (s)')
    asse.set_ylabel('LeqA (dBA)')
    asse.grid(True, linewidth=0.4, alpha=0.4)
    asse.margins(x=0.01)


def png(misura, per_gruppo=False, larghezza=9.0, altezza=2.6, dpi=110):
    """Grafico di una misura come data URI PNG, per la pagina."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    figura, asse = plt.subplots(figsize=(larghezza, altezza), dpi=dpi)
    try:
        _disegna(asse, misura)
        asse.set_title(titolo(misura, per_gruppo), fontsize=10, loc='left')
        figura.tight_layout()
        buffer = io.BytesIO()
        figura.savefig(buffer, format='png')
    finally:
        plt.close(figura)
    return 'data:image/png;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def esporta_pdf(misure, percorso, per_gruppo=False):
    """
    Scrive tutti gli spettri in un unico PDF, uno sotto l'altro.

    OUTPUT: {'percorso'} oppure {'errore'}
    """
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    disegnabili = [m for m in ordina(misure, per_gruppo) if m.get('leq')]
    if not disegnabili:
        return {'errore': 'Nessuno spettro da stampare.'}

    cartella = os.path.dirname(percorso)
    if cartella and not os.path.isdir(cartella):
        os.makedirs(cartella, exist_ok=True)

    per_pagina = 3
    with PdfPages(percorso) as pdf:
        for inizio in range(0, len(disegnabili), per_pagina):
            blocco = disegnabili[inizio:inizio + per_pagina]
            figura, assi = plt.subplots(per_pagina, 1, figsize=(8.27, 11.69), dpi=150)
            try:
                for asse, misura in zip(assi, blocco):
                    _disegna(asse, misura)
                    asse.set_title(titolo(misura, per_gruppo), fontsize=9, loc='left')
                for asse in assi[len(blocco):]:
                    asse.axis('off')
                figura.tight_layout(pad=2.0)
                pdf.savefig(figura)
            finally:
                plt.close(figura)
    return {'percorso': percorso, 'numero': len(disegnabili)}
