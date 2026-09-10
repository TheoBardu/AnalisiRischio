#! /usr/bin/env python3
"""
Esecuzione della pipeline del rumore usando VRR_analisiDati come backend.

Non si chiama main.main(): quella funzione legge i percorsi dal proprio
parameters.py, entra nella cartella delle misure senza uscirne e lancia due
utility con os.system e percorsi assoluti scritti nel codice. Qui si ripete la
stessa sequenza chiamando le funzioni pubbliche con percorsi espliciti, cosi'
i parametri arrivano dall'interfaccia e VRR resta intatto.

USO: python runner_rumore.py <configurazione.json>
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runner import passi as elenco_passi
from runner import protocollo
from runner.protocollo import Sequenza, carica_modulo, emetti, log

NOME_RILIEVI = 'Rilievi_Fonometrici.xlsx'
NOME_TOTALE = 'VR8h_totale.xlsx'
NOME_RIEPILOGO = 'VR8h_riepilogo.xlsx'
NOME_AGGIORNATO = 'VR8h_totale_aggiornato.xlsx'
NOME_SCHEDA = 'scheda_gruppi_dpi.xlsx'
NOME_ALLEGATI = 'allegati'

# fogli di calcolo esportati in PDF nella cartella allegati/, nell'ordine
ALLEGATI_PDF = (NOME_AGGIORNATO, NOME_RILIEVI)


def _nome_pdf(nome_xlsx):
    """VR8h_totale_aggiornato.xlsx -> VR8h_totale_aggiornato.pdf"""
    return os.path.splitext(nome_xlsx)[0] + '.pdf'


def _leggi_scheda_rilievi(crea, scheda):
    """
    Foglio delle mansioni per Rilievi_Fonometrici.xlsx.

    load_scheda() vuole una cartella e ricompone da se' il nome canonico: va
    bene finche' la scheda si chiama scheda_gruppi_dpi.xlsx, ma dall'interfaccia
    se ne puo' indicare una con un altro nome. In quel caso si legge il file
    scelto nello stesso modo, senza passare da load_scheda.
    """
    if os.path.basename(scheda).lower() == NOME_SCHEDA:
        return crea.load_scheda(os.path.dirname(scheda))
    import pandas as pd
    return pd.read_excel(scheda, sheet_name=crea.SCHEDA_MANSIONI, header=1)


def costruisci_passi(cfg, stato):
    """
    Prepara i passi della pipeline del rumore.

    INPUT:  cfg   - configurazione dell'esecuzione
            stato - dizionario condiviso fra i passi (dataframe intermedi)
    OUTPUT: lista di (chiave, nome, funzione)
    """
    cartella_vrr = cfg['percorso_vrr']
    main_directory = cfg['main']
    cartella_misure = cfg['misure']
    cartella_output = cfg['output']
    cartella_dati = os.path.join(cartella_misure, 'data')
    cartella_allegati = os.path.join(cartella_output, NOME_ALLEGATI)
    scheda = cfg.get('scheda', '')
    par = cfg.get('parametri', {})

    sys.path.insert(0, cartella_vrr)
    analisi_datiVR = carica_modulo(cartella_vrr, 'analisi_datiVR')

    def pulizia():
        """
        Rimuove i risultati dell'esecuzione precedente.

        I VR8h_* vanno tolti sempre: analisi_8h aggiunge i fogli a un
        VR8h_totale.xlsx esistente, e applica_DPI_HML associa poi le righe del
        riepilogo ai fogli per posizione, cosi' un residuo di un'esecuzione
        precedente falserebbe i risultati.

        averaged_data.csv invece si conserva. average_values() lo rilegge
        apposta invece di ricalcolarlo, ed e' li' che finiscono le misure
        corrette o aggiunte a mano dalla schermata Misure singole: cancellarlo
        significa perderle. Lo si rimuove solo se l'utente chiede
        esplicitamente di rileggere i file di misura.
        """
        rimossi = []
        da_rimuovere = [os.path.join(cartella_output, NOME_TOTALE),
                        os.path.join(cartella_output, NOME_RIEPILOGO),
                        os.path.join(cartella_output, NOME_AGGIORNATO)]
        # i PDF in allegati/, piu' quello che le versioni precedenti
        # lasciavano accanto all'xlsx in output/
        da_rimuovere += [os.path.join(cartella_allegati, _nome_pdf(nome))
                         for nome in ALLEGATI_PDF]
        da_rimuovere.append(os.path.join(cartella_output, _nome_pdf(NOME_AGGIORNATO)))
        if cfg.get('rileggi_misure', False):
            da_rimuovere += [os.path.join(cartella_dati, 'averaged_data.csv'),
                             os.path.join(cartella_dati, 'averaged_data.xlsx')]
            log('Rilettura delle misure richiesta: le medie verranno ricalcolate '
                'dai file di misura e le modifiche manuali andranno perse.',
                'warning')
        for percorso in da_rimuovere:
            if os.path.exists(percorso):
                os.remove(percorso)
                rimossi.append(os.path.basename(percorso))
        log(f'Rimossi {len(rimossi)} file dell\'esecuzione precedente'
            + (f': {", ".join(rimossi)}' if rimossi else '.'))
        os.makedirs(cartella_output, exist_ok=True)
        return True

    def lettura_misure():
        """
        manager() legge la cartella corrente nel costruttore e iterate_directory
        si sposta di cartella in cartella senza tornare indietro: la posizione
        va salvata e rimessa a posto.
        """
        precedente = os.getcwd()
        try:
            os.chdir(cartella_misure)
            gestore = analisi_datiVR.manager()
            gestore.iterate_directory(
                file_name='dati.txt', format='csv',
                versione_lettura=str(par.get('VERSIONE_FIRMWARE', '2')))
        finally:
            os.chdir(precedente)
        return True

    def medie():
        stato['analisi'] = analisi_datiVR.analisi(cartella_dati)
        stato['df_avg'] = stato['analisi'].average_values()
        log(f'Misure mediate: {len(stato["df_avg"])} righe')
        return True

    def scheda_info():
        if not scheda or not os.path.exists(scheda):
            raise FileNotFoundError(
                'scheda_gruppi_dpi.xlsx non trovata: indicala dalla schermata '
                'Cartella di lavoro.')
        stato['df_HEG'] = stato['analisi'].get_scheda_info(
            stato['df_avg'],
            excel_info_dir=os.path.dirname(scheda),
            name_exel_info=os.path.basename(scheda))
        log(f'Scheda mansioni letta: {len(stato["df_HEG"])} righe')
        return True

    def analisi_8h():
        os.makedirs(cartella_output, exist_ok=True)
        stato['analisi'].analisi_8h(
            cartella_output, stato['df_HEG'],
            T0=float(par.get('T0', 480.0)),
            u2m=float(par.get('u2m', 0.7)),
            u_pos=float(par.get('u_pos', 1.0)))
        return True

    def dpi():
        totale = os.path.join(cartella_output, NOME_TOTALE)
        if not os.path.exists(totale):
            raise FileNotFoundError(f'{NOME_TOTALE} non prodotto dal passo precedente.')
        stato['analisi'].applica_DPI_HML(
            excel_info_scheda_dpi=scheda,
            excel_total=totale,
            excel_output=os.path.join(cartella_output, NOME_RIEPILOGO),
            excel_aggiornato=os.path.join(cartella_output, NOME_AGGIORNATO))
        return True

    def rilievi():
        crea = carica_modulo(os.path.join(cartella_vrr, 'utility'), 'crea_excel_dati')
        df_avg = crea.load_averaged_data(cartella_dati)
        df_mis = crea.load_mis_files(cartella_dati)
        df_scheda = _leggi_scheda_rilievi(crea, scheda or
                                          os.path.join(main_directory, NOME_SCHEDA))
        destinazione = os.path.join(cartella_output, NOME_RILIEVI)
        crea.write_excel(df_avg, df_mis, df_scheda, destinazione)
        log(f'{NOME_RILIEVI} creato in {cartella_output}')
        return True

    def pdf():
        """
        Esporta in allegati/ i PDF di VR8h_totale_aggiornato.xlsx e di
        Rilievi_Fonometrici.xlsx. Ogni export ha il proprio try: LibreOffice
        puo' non essere installato o fallire su un solo file, e non e' un
        motivo per invalidare un'analisi gia' completa.
        """
        if not par.get('esporta_pdf', True):
            return 'saltato'
        esporta = carica_modulo(os.path.join(cartella_vrr, 'utility'), 'export_excel2pdf')
        os.makedirs(cartella_allegati, exist_ok=True)
        qualcosa = False
        for nome in ALLEGATI_PDF:
            documento = os.path.join(cartella_output, nome)
            if not os.path.exists(documento):
                log(f'{nome} assente: export PDF saltato.', 'warning')
                continue
            try:
                esporta.esporta_pdf(
                    documento,
                    pdf_output=os.path.join(cartella_allegati, _nome_pdf(nome)))
                qualcosa = True
            except Exception as errore:
                log(f'Export PDF di {nome} non riuscito: {errore}', 'error')
        if qualcosa:
            log(f'PDF salvati in {cartella_allegati}')
        return True if qualcosa else 'saltato'

    funzioni = {
        'pulizia': pulizia,
        'lettura_misure': lettura_misure,
        'medie': medie,
        'scheda_info': scheda_info,
        'analisi_8h': analisi_8h,
        'dpi': dpi,
        'rilievi': rilievi,
        'pdf': pdf,
    }
    return [(chiave, nome, funzioni[chiave])
            for chiave, nome in elenco_passi.PASSI_RUMORE]


def esegui(cfg, offset=0, totale=None):
    """Esegue la pipeline. OUTPUT: True se conclusa senza errori."""
    stato = {}
    passi = costruisci_passi(cfg, stato)
    sequenza = Sequenza('rumore', passi, offset=offset,
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
