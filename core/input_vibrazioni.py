#! /usr/bin/env python3
"""
Lettura e scrittura dei dati di ingresso delle vibrazioni.

    datiCostr.xlsx    foglio 'DatCostr', colonne a posizione fissa
    misureHAV.xlsx    intestazioni su celle unite, colonne a posizione variabile
    misureWBV.xlsx    idem, con in piu' i tre VDV per misura

Per i due file di misura si replica la stessa individuazione delle colonne che
fa VRV (l'etichetta 'foto' insieme a tre etichette 'Sec.' sulla stessa riga),
cosi' la griglia dell'interfaccia e l'analisi vedono le stesse celle. La
scrittura riscrive esattamente quelle celle: intestazioni, celle unite e stile
del file restano intatti.
"""

import os
import shutil
from copy import copy

import openpyxl

FOGLIO_DATI_COSTR = 'DatCostr'
RIGA_INIZIO_DATI_COSTR = 5      # 1-based: VRV usa l'indice 4 su base 0

# colonne di datiCostr.xlsx, 1-based
COLONNE_COSTR = ['ID', 'Categoria', 'Marca', 'Modello', 'HAV', 'WBV', 'K',
                 'Valore di calcolo', 'Tmax Limite', 'Tmax Azione', 'Fonte']
# calcolate dal backend: si mostrano ma non si scrivono
COSTR_SOLA_LETTURA = {'Valore di calcolo', 'Tmax Limite', 'Tmax Azione'}

TESTO_INTESTAZIONE = 'foto'
TESTO_SEC = 'sec'

CAMPI_HAV = ('Tm', 'X', 'Y', 'Z')
CAMPI_WBV = ('Tm', 'X', 'Y', 'Z', 'VDVx', 'VDVy', 'VDVz')

ANAGRAFICA = ['foto', 'ID', 'Categoria', 'Marca', 'Modello']


def _testo(valore):
    if valore is None:
        return ''
    if isinstance(valore, float) and valore.is_integer():
        return str(int(valore))
    return str(valore).strip()


def _numero(testo):
    testo = (testo or '').strip()
    if testo == '':
        return None
    try:
        valore = float(testo.replace(',', '.'))
    except ValueError:
        return testo
    return int(valore) if valore.is_integer() else valore


def _backup(percorso):
    copia = percorso + '.bak'
    if not os.path.exists(copia):
        shutil.copy2(percorso, copia)
    return copia


# --------------------------------------------------------------------------
# datiCostr.xlsx
# --------------------------------------------------------------------------

def leggi_dati_costruttori(percorso):
    """
    OUTPUT: {'percorso', 'colonne', 'sola_lettura', 'righe': [[...]], 'errore'}
    """
    esito = {'percorso': percorso or '', 'colonne': COLONNE_COSTR,
             'sola_lettura': sorted(COSTR_SOLA_LETTURA), 'righe': [], 'errore': ''}
    if not percorso or not os.path.exists(percorso):
        esito['errore'] = 'datiCostr.xlsx non trovato.'
        return esito
    try:
        wb = openpyxl.load_workbook(percorso, data_only=True)
    except Exception as errore:
        esito['errore'] = f'Impossibile aprire il file: {errore}'
        return esito

    ws = wb[FOGLIO_DATI_COSTR] if FOGLIO_DATI_COSTR in wb.sheetnames else wb[wb.sheetnames[0]]
    for riga in range(RIGA_INIZIO_DATI_COSTR, ws.max_row + 1):
        valori = [_testo(ws.cell(row=riga, column=c).value)
                  for c in range(1, len(COLONNE_COSTR) + 1)]
        if valori[0] == '':
            continue
        esito['righe'].append(valori)
    wb.close()
    return esito


def salva_dati_costruttori(percorso, righe):
    """
    Riscrive le righe di datiCostr.xlsx conservandone stile e intestazioni.

    Le colonne calcolate dal backend non vengono toccate: le ricalcola
    leggi_dati_costruttori di VRV a ogni esecuzione.
    """
    if not percorso or not os.path.exists(percorso):
        return {'ok': False, 'errore': 'datiCostr.xlsx non trovato.'}
    try:
        copia = _backup(percorso)
        wb = openpyxl.load_workbook(percorso)
        ws = wb[FOGLIO_DATI_COSTR] if FOGLIO_DATI_COSTR in wb.sheetnames else wb[wb.sheetnames[0]]

        ultima = RIGA_INIZIO_DATI_COSTR - 1
        for riga in range(RIGA_INIZIO_DATI_COSTR, ws.max_row + 1):
            if _testo(ws.cell(row=riga, column=1).value) != '':
                ultima = riga
        modello = ultima if ultima >= RIGA_INIZIO_DATI_COSTR else None

        for indice, valori in enumerate(righe):
            riga = RIGA_INIZIO_DATI_COSTR + indice
            if modello is not None and riga > ultima:
                for colonna in range(1, len(COLONNE_COSTR) + 1):
                    destinazione = ws.cell(row=riga, column=colonna)
                    destinazione._style = copy(ws.cell(row=modello, column=colonna)._style)
            for colonna, nome in enumerate(COLONNE_COSTR, start=1):
                if nome in COSTR_SOLA_LETTURA:
                    continue
                testo = valori[colonna - 1] if colonna - 1 < len(valori) else ''
                cella = ws.cell(row=riga, column=colonna)
                cella.value = testo or None if nome in ('ID', 'Categoria', 'Marca',
                                                        'Modello', 'Fonte') else _numero(testo)

        for riga in range(RIGA_INIZIO_DATI_COSTR + len(righe), ultima + 1):
            for colonna in range(1, len(COLONNE_COSTR) + 1):
                ws.cell(row=riga, column=colonna).value = None

        wb.save(percorso)
        wb.close()
    except Exception as errore:
        return {'ok': False, 'errore': str(errore)}
    return {'ok': True, 'errore': '', 'backup': copia}


# --------------------------------------------------------------------------
# misureHAV.xlsx / misureWBV.xlsx
# --------------------------------------------------------------------------

def individua_colonne(ws):
    """
    Individua intestazione e colonne di un file di misura (indici 1-based).

    Replica la logica di VRV: si cerca la riga che contiene l'etichetta 'foto'
    insieme ad almeno tre etichette che iniziano per 'Sec.'; da 'foto' partono
    ID, Categoria, Marca e Modello, e ogni 'Sec.' ancora un blocco di misura.

    OUTPUT: dizionario con 'riga_intestazione', le colonne di anagrafica e
            'misure' (le tre colonne ancora), oppure None
    """
    for riga in range(1, min(ws.max_row, 40) + 1):
        valori = [_testo(ws.cell(row=riga, column=c).value).lower()
                  for c in range(1, ws.max_column + 1)]
        if TESTO_INTESTAZIONE not in valori:
            continue
        colonne_sec = [i + 1 for i, v in enumerate(valori) if v.startswith(TESTO_SEC)]
        if len(colonne_sec) < 3:
            continue
        colonna_foto = valori.index(TESTO_INTESTAZIONE) + 1
        return {
            'riga_intestazione': riga,
            'foto': colonna_foto, 'ID': colonna_foto + 1,
            'Categoria': colonna_foto + 2, 'Marca': colonna_foto + 3,
            'Modello': colonna_foto + 4,
            'misure': colonne_sec[:3],
        }
    return None


def _colonne_griglia(tipo):
    """Nomi delle colonne della griglia: anagrafica + tre blocchi di misura."""
    campi = CAMPI_HAV if tipo == 'HAV' else CAMPI_WBV
    colonne = list(ANAGRAFICA)
    for k in range(1, 4):
        colonne.extend(f'{nome}{k}' for nome in campi)
    return colonne, campi


def leggi_misure(percorso, tipo):
    """
    Legge misureHAV.xlsx o misureWBV.xlsx in una griglia modificabile.

    OUTPUT: {'percorso', 'tipo', 'colonne', 'righe': [[...]], 'errore'}
    """
    colonne, campi = _colonne_griglia(tipo)
    esito = {'percorso': percorso or '', 'tipo': tipo, 'colonne': colonne,
             'righe': [], 'errore': ''}
    if not percorso or not os.path.exists(percorso):
        esito['errore'] = f'File delle misure {tipo} non trovato.'
        return esito
    try:
        wb = openpyxl.load_workbook(percorso, data_only=True)
    except Exception as errore:
        esito['errore'] = f'Impossibile aprire il file: {errore}'
        return esito

    ws = wb[wb.sheetnames[0]]
    mappa = individua_colonne(ws)
    if mappa is None:
        wb.close()
        esito['errore'] = ("Intestazione non riconosciuta: manca l'etichetta 'foto' "
                           "insieme a tre colonne 'Sec.' sulla stessa riga.")
        return esito

    for riga in range(mappa['riga_intestazione'] + 1, ws.max_row + 1):
        if _testo(ws.cell(row=riga, column=mappa['ID']).value) == '':
            continue
        valori = [_testo(ws.cell(row=riga, column=mappa[nome]).value)
                  for nome in ANAGRAFICA]
        for colonna_sec in mappa['misure']:
            for offset in range(len(campi)):
                valori.append(_testo(ws.cell(row=riga,
                                             column=colonna_sec + offset).value))
        esito['righe'].append(valori)
    wb.close()
    return esito


def salva_misure(percorso, tipo, righe):
    """
    Riscrive le stesse celle individuate in lettura.

    Le righe aggiunte copiano lo stile dell'ultima riga di dati esistente, cosi'
    il file resta indistinguibile da quelli compilati a mano.
    """
    if not percorso or not os.path.exists(percorso):
        return {'ok': False, 'errore': f'File delle misure {tipo} non trovato.'}
    _, campi = _colonne_griglia(tipo)
    try:
        copia = _backup(percorso)
        wb = openpyxl.load_workbook(percorso)
        ws = wb[wb.sheetnames[0]]
        mappa = individua_colonne(ws)
        if mappa is None:
            wb.close()
            return {'ok': False, 'errore': 'Intestazione non riconosciuta.'}

        prima = mappa['riga_intestazione'] + 1
        ultima = prima - 1
        for riga in range(prima, ws.max_row + 1):
            if _testo(ws.cell(row=riga, column=mappa['ID']).value) != '':
                ultima = riga
        modello = ultima if ultima >= prima else None

        # colonne effettivamente toccate, per copiare lo stile solo dove serve
        colonne_usate = [mappa[nome] for nome in ANAGRAFICA]
        for colonna_sec in mappa['misure']:
            colonne_usate.extend(range(colonna_sec, colonna_sec + len(campi)))

        for indice, valori in enumerate(righe):
            riga = prima + indice
            if modello is not None and riga > ultima:
                for colonna in colonne_usate:
                    ws.cell(row=riga, column=colonna)._style = copy(
                        ws.cell(row=modello, column=colonna)._style)
            posizione = 0
            for nome in ANAGRAFICA:
                testo = valori[posizione] if posizione < len(valori) else ''
                ws.cell(row=riga, column=mappa[nome]).value = testo or None
                posizione += 1
            for colonna_sec in mappa['misure']:
                for offset in range(len(campi)):
                    testo = valori[posizione] if posizione < len(valori) else ''
                    ws.cell(row=riga, column=colonna_sec + offset).value = _numero(testo)
                    posizione += 1

        for riga in range(prima + len(righe), ultima + 1):
            for colonna in colonne_usate:
                ws.cell(row=riga, column=colonna).value = None

        wb.save(percorso)
        wb.close()
    except Exception as errore:
        return {'ok': False, 'errore': str(errore)}
    return {'ok': True, 'errore': '', 'backup': copia}
