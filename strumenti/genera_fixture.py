#! /usr/bin/env python3
"""
Registra le risposte del ponte per una cartella reale.

Serve all'anteprima nel browser (strumenti/anteprima.html): l'interfaccia
viene disegnata con gli stessi dati che riceverebbe dall'applicazione, senza
dover avviare Qt.

USO: python strumenti/genera_fixture.py <cartella> [destinazione.json]
"""

import json
import os
import sys

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CARTELLA_PROGETTO)

from core import (configurazione, input_vibrazioni, progetto,  # noqa: E402
                  risultati_rumore, risultati_vibrazioni, schede)
from relazione import contesto as contesto_relazione           # noqa: E402
from relazione import generatore                               # noqa: E402
from runner import passi as elenco_passi                       # noqa: E402


def main():
    radice = sys.argv[1] if len(sys.argv) > 1 else ''
    destinazione = (sys.argv[2] if len(sys.argv) > 2
                    else os.path.join(CARTELLA_PROGETTO, 'strumenti', 'fixture.json'))

    scansione = progetto.scansiona(radice)
    rumore = scansione.get('rumore', {})
    vibrazioni = scansione.get('vibrazioni', {})
    par_rumore = configurazione.parametri_rumore()
    par_vib = configurazione.parametri_vibrazioni()

    lettura = schede.leggi(scansione.get('scheda', ''))
    lettura['tempi'] = schede.verifica_tempi(
        lettura['mansioni']['righe'], lettura['mansioni']['colonne'],
        float(par_rumore.get('T0', 480)))

    sintesi_rumore = risultati_rumore.sintesi(
        rumore.get('vr8h_riepilogo', ''), rumore.get('vr8h_totale', ''),
        t0=float(par_rumore.get('T0', 480)),
        limite=float(par_rumore.get('LIMITE_LEX8H', 87)))
    sintesi_vib = risultati_vibrazioni.sintesi(
        vibrazioni.get('log', ''), vibrazioni.get('vr_vib', ''), par_vib)

    misure = risultati_rumore.misure_singole(rumore.get('vr8h_totale', ''))
    misure['medie'] = risultati_rumore.leggi_medie(
        os.path.join(rumore.get('misure', ''), 'data'))

    file_vib = vibrazioni.get('file', {})
    contesto = contesto_relazione.costruisci(
        {}, sintesi_rumore['gruppi'], sintesi_vib['gruppi'],
        lettura['dpi']['righe'], lettura['dpi']['colonne'])

    # stato della relazione per ramo: nell'applicazione lo costruisce il ponte
    # dai percorsi della scansione, qui basta il modello e il frontespizio
    chiave_modello = {'rumore': 'modello_relazione_rumore',
                      'vibrazioni': 'modello_relazione_vibrazioni'}
    stato_relazione = {}
    for ramo in ('rumore', 'vibrazioni'):
        frontespizio = configurazione.percorso_frontespizio(
            configurazione.config().get(f'frontespizio_{ramo}', ''))
        uscita = os.path.join(scansione.get(ramo, {}).get('output', ''),
                              generatore.NOME_DOCUMENTO[ramo])
        stato = generatore.stato(
            configurazione.percorso_modello(chiave_modello[ramo]),
            frontespizio, uscita)
        stato['presente'] = bool(scansione.get(ramo, {}).get('presente'))
        stato['uscita'] = uscita
        stato_relazione[ramo] = stato

    frontespizi = {ramo: configurazione.frontespizi_disponibili(ramo)
                   for ramo in ('rumore', 'vibrazioni')}

    fixture = {
        'stato_iniziale': {
            'config': configurazione.config(),
            'parametri_rumore': par_rumore,
            'parametri_vibrazioni': par_vib,
            'recenti': configurazione.progetti_recenti(),
            'campi_relazione': {blocco: contesto_relazione.elenco_campi([blocco])
                                for blocco in ('comuni', 'rumore', 'vibrazioni')},
            'layout_relazione': contesto_relazione.LAYOUT,
            'frontespizi': frontespizi,
            'relazione': stato_relazione,
            'passi': {m: elenco_passi.passi_di(m)
                      for m in ('rumore', 'vibrazioni', 'combinato')},
            # misure tipiche della barra del titolo di macOS: nell'applicazione
            # vera le misura app.py sulla finestra, qui servono solo perche'
            # l'anteprima si veda come si vedra' davvero
            'finestra': {'altezza_barra': 28, 'spazio_pallini': 75},
        },
        'scansiona': scansione,
        'leggi_schede': lettura,
        'risultati_rumore': sintesi_rumore,
        'risultati_vibrazioni': sintesi_vib,
        'misure_singole': misure,
        'leggi_attrezzature': {
            'costruttori': input_vibrazioni.leggi_dati_costruttori(
                file_vib.get('datiCostr', '')),
            'HAV': input_vibrazioni.leggi_misure(file_vib.get('misureHAV', ''), 'HAV'),
            'WBV': input_vibrazioni.leggi_misure(file_vib.get('misureWBV', ''), 'WBV'),
        },
        'relazione_dati': {
            'tabella_dpi': contesto['tabella_dpi'],
            'tabella_HEG': contesto['tabella_HEG'],
            'tabella_vibrazioni': contesto['tabella_vibrazioni'],
            'frase_presenza': contesto['frase_presenza'],
            'colonne_dpi': contesto_relazione.COLONNE_TABELLA_DPI,
            'colonne_heg': contesto_relazione.COLONNE_TABELLA_HEG,
            'colonne_vib': contesto_relazione.COLONNE_TABELLA_VIB,
            'stato': stato_relazione,
            'frontespizi': frontespizi,
        },
        'salva_parametri': {'ok': True},
        # nell'anteprima il ponte e' finto: la scrittura non parte davvero
        'relazione_genera': {'ok': False,
                             'messaggio': 'anteprima: la scrittura non e\' attiva'},
    }

    with open(destinazione, 'w', encoding='utf-8') as f:
        json.dump(fixture, f, ensure_ascii=False, default=str)
    print(f'{destinazione}  ({os.path.getsize(destinazione) // 1024} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
