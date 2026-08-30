#! /usr/bin/env python3
"""
Esecuzione della pipeline delle vibrazioni usando VRV_analisiDati come backend.

Non si chiama main.main() per due motivi. Il primo e' che percorsi() pretende
scheda_gruppi_dpi.xlsx una cartella sopra la main directory, mentre nei lavori
reali il file sta nel ramo Rumore: qui il percorso arriva gia' risolto
dall'interfaccia. Il secondo e' che i parametri di calcolo devono poter venire
dalla configurazione dell'applicazione invece che da parameters.py.

Al termine si scrive output/riepilogo_vibrazioni.json con i valori di
analisi.riepilogo(): e' la fonte che l'interfaccia usa per la schermata delle
esposizioni, piu' fedele della rilettura del foglio di calcolo.

USO: python runner_vibrazioni.py <configurazione.json>
"""

import json
import logging
import os
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import passi as elenco_passi
from runner import protocollo
from runner.protocollo import GestoreLog, Sequenza, carica_modulo, emetti, log

NOME_MISURE_VIB = 'misureVIB.xlsx'
NOME_VR_VIB = 'VR_VIB.xlsx'
NOME_RIEPILOGO_JSON = 'riepilogo_vibrazioni.json'

COLORI_CLASSE = {'BASSA': '#32cd32', 'MEDIA': '#00bfff', 'ALTA': '#b22222'}


def _parametri(modulo_parametri, sovrascritture):
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


def _classe_breve(testo):
    basso = (testo or '').strip().lower()
    for chiave in ('bassa', 'media', 'alta'):
        if basso.endswith(chiave):
            return chiave.upper()
    return ''


def _fmt(valore, decimali=2):
    if valore is None or valore == '':
        return '—'
    try:
        return f'{float(valore):.{decimali}f}'
    except (TypeError, ValueError):
        return str(valore)


def _scrivi_riepilogo_json(analisi_oggetto, cartella_output):
    """
    Serializza schede e riepilogo in una struttura pronta per l'interfaccia.

    Si usano le schede (analisi.schede) perche' contengono anche l'elenco delle
    attrezzature per gruppo, che il riepilogo tabellare non riporta.
    """
    gruppi = []
    for scheda in getattr(analisi_oggetto, 'schede', []) or []:
        voce = {
            'code': str(scheda.get('ID_GrOm', '')),
            'nome': scheda.get('Descrizione_GrOm', ''),
            'reparto': scheda.get('Descrizione_reparto', ''),
        }
        for tipo in ('HAV', 'WBV'):
            lato = scheda.get(tipo) or {}
            classe = _classe_breve(lato.get('Classe', ''))
            voce[tipo] = {
                'righe': [{
                    'id': r.get('ID', ''),
                    'categoria': r.get('Categoria', ''),
                    'marca': r.get('Marca', ''),
                    'modello': r.get('Modello', ''),
                    'aw': _fmt(r.get('Aw')),
                    'u': _fmt(r.get('U'), 3),
                    'te': _fmt(r.get('Te'), 0),
                    'fonte': r.get('Fonte', ''),
                    'compito': r.get('Compito', ''),
                } for r in lato.get('righe', [])],
                'non_trovate': lato.get('non_trovate', []),
                'te_totale': _fmt(lato.get('Te_totale'), 0),
                'a8': _fmt(lato.get('A8')),
                'ua8': _fmt(lato.get('UA8'), 3),
                'a8max': _fmt(lato.get('A8max')),
                'dy': _fmt(lato.get('Dy'), 1) if tipo == 'HAV' else '',
                'classe': classe or '—',
                'colore': COLORI_CLASSE.get(classe, '#9397ab'),
                'errore': lato.get('Errore') or '',
                'presente': bool(lato.get('righe')) or lato.get('A8') is not None,
            }
        gruppi.append(voce)

    os.makedirs(cartella_output, exist_ok=True)
    percorso = os.path.join(cartella_output, NOME_RIEPILOGO_JSON)
    with open(percorso, 'w', encoding='utf-8') as f:
        json.dump({'gruppi': gruppi}, f, indent=2, ensure_ascii=False)
    return percorso


def costruisci_passi(cfg, stato):
    """OUTPUT: lista di (chiave, nome, funzione) per la pipeline vibrazioni."""
    cartella_vrv = cfg['percorso_vrv']
    cartella_output = cfg['output']
    file_input = cfg.get('file', {})
    scheda = cfg.get('scheda', '')

    sys.path.insert(0, cartella_vrv)
    config_vrv = carica_modulo(cartella_vrv, 'config')
    analisi_vib = carica_modulo(cartella_vrv, 'analisi_datiVIB')
    excel_vib = carica_modulo(cartella_vrv, 'excel_vib')
    try:
        parametri_vrv = carica_modulo(cartella_vrv, 'parameters')
    except FileNotFoundError:
        parametri_vrv = carica_modulo(cartella_vrv, 'parameters_example')

    par = _parametri(parametri_vrv, cfg.get('parametri', {}))
    stato['par'] = par

    def preparazione():
        """
        configura_log azzera gli handler del logger: l'handler che inoltra i
        messaggi all'interfaccia va agganciato dopo, non prima.
        """
        os.makedirs(cartella_output, exist_ok=True)
        config_vrv.configura_log(cartella_output)
        logger = logging.getLogger(config_vrv.LOGGER_NAME)
        logger.addHandler(GestoreLog())
        return True

    def lettura():
        percorso_hav = file_input.get('misureHAV', '')
        percorso_wbv = file_input.get('misureWBV', '')
        percorso_costr = file_input.get('datiCostr', '')

        stato['df_hav'] = analisi_vib.files.leggi_misure(percorso_hav, 'HAV')
        stato['df_wbv'] = analisi_vib.files.leggi_misure(percorso_wbv, 'WBV')
        stato['df_costr'] = analisi_vib.files.leggi_dati_costruttori(percorso_costr)

        if not scheda or not os.path.exists(scheda):
            raise FileNotFoundError(
                'scheda_gruppi_dpi.xlsx non trovata: indicala dalla schermata '
                'Cartella di lavoro.')
        stato['df_scheda'] = analisi_vib.files.leggi_scheda_gruppi(scheda)

        colonne = stato['df_scheda'].columns
        ha_id = False
        for nome in (config_vrv.COL_HAV, config_vrv.COL_WBV):
            if nome in colonne:
                ha_id = ha_id or any(str(v).strip() not in ('', 'nan', 'None')
                                     for v in stato['df_scheda'][nome])
        if not ha_id:
            raise ValueError(
                'Nessun ID nelle colonne HAV o WBV della scheda mansioni: '
                'non c\'e\' esposizione a vibrazioni da valutare.')
        return True

    def calcolo_hav():
        stato['analisi'] = analisi_vib.analisi(
            stato['df_hav'], stato['df_wbv'], stato['df_costr'],
            stato['df_scheda'], stato['par'])
        stato['analisi'].calcola_misure_HAV()
        return True

    def calcolo_wbv():
        stato['analisi'].calcola_misure_WBV()
        return True

    def scrittura_misure():
        template = os.path.join(cartella_vrv, 'templates', config_vrv.TEMPLATE_MISURE)
        destinazione = os.path.join(cartella_output, NOME_MISURE_VIB)
        stato['file_misure'] = excel_vib.excel_file.scrivi_misure_VIB(
            stato['analisi'].df_HAV, stato['analisi'].df_WBV,
            template, destinazione, stato['par'])
        log(f'{NOME_MISURE_VIB} scritto in {cartella_output}')
        return True

    def schede():
        stato['analisi'].calcola_schede()
        template = os.path.join(cartella_vrv, 'templates', config_vrv.TEMPLATE_VR)
        destinazione = os.path.join(cartella_output, NOME_VR_VIB)
        stato['file_vr'] = excel_vib.excel_file.scrivi_VR_VIB(
            stato['analisi'].schede, template, destinazione, stato['par'])
        if stato['file_vr'] is None:
            log('Nessun gruppo omogeneo esposto a vibrazioni: VR_VIB.xlsx non scritto.',
                'warning')
            return 'saltato'
        percorso = _scrivi_riepilogo_json(stato['analisi'], cartella_output)
        log(f'Riepilogo salvato in {os.path.basename(percorso)}')
        return True

    def pdf():
        if not getattr(stato['par'], 'ESPORTA_PDF', True):
            return 'saltato'
        esporta = carica_modulo(os.path.join(cartella_vrv, 'utility'),
                                'export_excel2pdf')
        cartella_allegati = os.path.join(cartella_output, 'allegati')
        os.makedirs(cartella_allegati, exist_ok=True)
        qualcosa = False
        for percorso, nome, fogli in (
                (stato.get('file_misure'), 'misureVIB_HAV', ['HAV']),
                (stato.get('file_misure'), 'misureVIB_WBV', ['WBV']),
                (stato.get('file_vr'), 'VR_VIB', None)):
            if not percorso or not os.path.exists(percorso):
                continue
            try:
                esporta.esporta_pdf(
                    percorso,
                    pdf_output=os.path.join(cartella_allegati, f'{nome}.pdf'),
                    fogli=fogli)
                qualcosa = True
            except Exception as errore:
                log(f'Export PDF di {nome} non riuscito: {errore}', 'error')
        return True if qualcosa else 'saltato'

    funzioni = {
        'preparazione': preparazione,
        'lettura': lettura,
        'calcolo_hav': calcolo_hav,
        'calcolo_wbv': calcolo_wbv,
        'scrittura_misure': scrittura_misure,
        'schede': schede,
        'pdf': pdf,
    }
    return [(chiave, nome, funzioni[chiave])
            for chiave, nome in elenco_passi.PASSI_VIBRAZIONI]


def esegui(cfg, offset=0, totale=None):
    stato = {}
    passi = costruisci_passi(cfg, stato)
    sequenza = Sequenza('vibrazioni', passi, offset=offset,
                        totale=totale if totale is not None else len(passi))
    if offset == 0:
        sequenza.annuncia()
    return sequenza.esegui()


def main():
    cfg = protocollo.leggi_configurazione()
    protocollo.cattura_stampe()
    inizio = time.time()
    try:
        # in modalita' combinata i passi sono numerati con continuita' fra le
        # due pipeline: l'interfaccia passa l'offset e il totale complessivo
        ok = esegui(cfg, offset=int(cfg.get('offset', 0) or 0),
                    totale=cfg.get('totale'))
    except Exception as errore:
        log(f'{type(errore).__name__}: {errore}', 'error')
        ok = False
    emetti({'tipo': 'fine', 'ok': ok, 'durata': round(time.time() - inizio, 1)})
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
