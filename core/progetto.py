#! /usr/bin/env python3
"""
Riconoscimento della cartella di lavoro.

Nelle cartelle reali il layout non e' uniforme: ci sono aziende organizzate
come <Azienda>/rev/rev<N>/{Rumore,Vibrazioni}, altre con Rumore/ e Vibrazioni/
direttamente sotto la root, altre ancora con la sola cartella misure/. Qui si
parte dalla root scelta dall'utente e si cerca cosa c'e', invece di pretendere
una struttura fissa.
"""

import json
import os

from core import backend, configurazione

# Nomi dei rami, cercati senza distinzione fra maiuscole e minuscole.
NOMI_RUMORE = ('rumore',)
NOMI_VIBRAZIONI = ('vibrazioni', 'vibrazione', 'vib')

NOME_MISURE = 'misure'
NOME_OUTPUT = 'output'
NOME_SCHEDA = 'scheda_gruppi_dpi.xlsx'
NOME_DATI_RELAZIONE = 'relazione_dati.json'

PROFONDITA_MASSIMA = 2

# Prefissi con cui riconoscere i file delle vibrazioni: i nomi reali variano
# (misureWBV_2026_AL7-MEIPA_SRL.xlsx), quindi non si puo' pretendere il nome
# esatto previsto da VRV/parameters.py.
PREFISSI_VIBRAZIONI = {
    'misureHAV': ('misurehav', 'hav'),
    'misureWBV': ('misurewbv', 'wbv'),
    'datiCostr': ('daticostr', 'dati_costr', 'costruttori'),
}

# Classificazione delle cartelle di misura del rumore. I valori di riferimento
# stanno in VRR/config.py: qui restano solo come ripiego se il backend non e'
# raggiungibile.
FORMATI_RIPIEGO = {
    'xlsx': ['misA', 'misB', 'misC', 'misG', 'misH'],
    'csv': ['misD', 'misE', 'misF'],
    'txt': ['misW'],
}

ESTENSIONI_FORMATO = {'xlsx': '.xlsx', 'csv': '.csv', 'txt': '.txt'}


def _formati_rumore():
    """
    Elenco delle cartelle di misura per formato, letto da VRR/config.py.

    OUTPUT: dizionario formato -> lista di nomi cartella
    """
    cfg = backend.carica_modulo(configurazione.config().get('percorso_vrr', ''), 'config')
    if cfg is None:
        return dict(FORMATI_RIPIEGO)
    return {
        'xlsx': list(getattr(cfg, 'READING_EXEL_DATA_FOLDER_NAME', FORMATI_RIPIEGO['xlsx'])),
        'csv': list(getattr(cfg, 'READING_CSV_DATA_FOLDER_NAME', FORMATI_RIPIEGO['csv'])),
        'txt': list(getattr(cfg, 'READING_TXT_DATA_FOLDER_NAME', FORMATI_RIPIEGO['txt'])),
    }


def _sottocartelle(percorso):
    if not os.path.isdir(percorso):
        return []
    return sorted(n for n in os.listdir(percorso)
                  if not n.startswith('.') and os.path.isdir(os.path.join(percorso, n)))


def _cerca_ramo(root, nomi, profondita=PROFONDITA_MASSIMA):
    """
    Cerca in profondita' limitata una cartella il cui nome sia in 'nomi'.

    Si scende solo lungo cartelle 'di transito' (rev, rev0, rev1, ...), cosi'
    da trovare <Azienda>/rev/rev2/Rumore senza esplorare tutto l'albero.
    """
    for nome in _sottocartelle(root):
        if nome.lower() in nomi:
            return os.path.join(root, nome)
    if profondita <= 0:
        return None
    for nome in _sottocartelle(root):
        trovato = _cerca_ramo(os.path.join(root, nome), nomi, profondita - 1)
        if trovato:
            return trovato
    return None


def _conta_file(cartella, estensione=None):
    """Conta i file (ricorsivamente) di una cartella, per estensione."""
    totale = 0
    for _, _, files in os.walk(cartella):
        for f in files:
            if f.startswith('.'):
                continue
            if estensione is None or f.lower().endswith(estensione):
                totale += 1
    return totale


def analizza_misure_rumore(cartella_misure):
    """
    Classifica le sottocartelle di misura del rumore.

    OUTPUT: (elenco, avvisi)
        elenco - lista di dict {path, fmt, n, valida}
        avvisi - messaggi sulle cartelle che verranno saltate
    """
    formati = _formati_rumore()
    per_nome = {}
    for formato, nomi in formati.items():
        for nome in nomi:
            per_nome[nome.lower()] = formato

    elenco, avvisi = [], []
    if not os.path.isdir(cartella_misure):
        return elenco, avvisi

    for nome in _sottocartelle(cartella_misure):
        if nome.lower() == 'data':
            continue
        completo = os.path.join(cartella_misure, nome)
        formato = per_nome.get(nome.lower())
        if formato is None:
            avvisi.append(f'{NOME_MISURE}/{nome} non e\' fra le cartelle note '
                          f'di VRR/config.py — la cartella verra\' saltata.')
            elenco.append({'path': f'{NOME_MISURE}/{nome}', 'fmt': '—',
                           'n': _conta_file(completo), 'valida': False})
            continue

        if formato == 'txt':
            # il formato txt vuole un dati.txt: senza, iterate_directory salta
            valida = os.path.exists(os.path.join(completo, 'dati.txt'))
            n = _conta_file(completo, '.txt')
            if not valida:
                avvisi.append(f'{NOME_MISURE}/{nome} non contiene dati.txt — '
                              f'la cartella verra\' saltata.')
        else:
            n = _conta_file(completo, ESTENSIONI_FORMATO[formato])
            valida = n > 0
            if not valida:
                avvisi.append(f'{NOME_MISURE}/{nome} non contiene file '
                              f'{ESTENSIONI_FORMATO[formato]} — la cartella verra\' saltata.')

        elenco.append({'path': f'{NOME_MISURE}/{nome}', 'fmt': formato,
                       'n': n, 'valida': valida})
    return elenco, avvisi


def _trova_file_vibrazioni(cartella_misure):
    """
    Associa i tre file di input delle vibrazioni ai file realmente presenti.

    OUTPUT: dizionario chiave -> percorso assoluto ('' se non trovato)
    """
    trovati = {chiave: '' for chiave in PREFISSI_VIBRAZIONI}
    if not os.path.isdir(cartella_misure):
        return trovati

    candidati = [n for n in os.listdir(cartella_misure)
                 if n.lower().endswith(('.xlsx', '.xls')) and not n.startswith('~$')]

    for chiave, prefissi in PREFISSI_VIBRAZIONI.items():
        # prima il nome esatto previsto da VRV, poi il match per prefisso
        esatto = f'{chiave}.xlsx'
        for nome in candidati:
            if nome.lower() == esatto.lower():
                trovati[chiave] = os.path.join(cartella_misure, nome)
                break
        else:
            for nome in candidati:
                base = nome.lower()
                if any(base.startswith(p) for p in prefissi):
                    trovati[chiave] = os.path.join(cartella_misure, nome)
                    break
    return trovati


def _primo_esistente(*percorsi):
    """Primo percorso che esiste davvero, altrimenti il primo dell'elenco."""
    for percorso in percorsi:
        if percorso and os.path.exists(percorso):
            return percorso
    return percorsi[0] if percorsi else ''


def _trova_scheda(root):
    """
    Cerca scheda_gruppi_dpi.xlsx nella root dell'azienda.

    Il file e' condiviso fra rumore e vibrazioni (e fra le valutazioni che si
    aggiungeranno), quindi il suo posto e' la root e non il ramo Rumore: chi ha
    ancora la vecchia disposizione lo indica a mano dalla schermata Schede HEG.
    """
    if not root or not os.path.isdir(root):
        return ''
    diretto = os.path.join(root, NOME_SCHEDA)
    if os.path.exists(diretto):
        return diretto
    # ripiego: un qualunque file che finisca con scheda_gruppi_dpi.xlsx
    for nome in sorted(os.listdir(root)):
        basso = nome.lower()
        if basso.endswith('scheda_gruppi_dpi.xlsx') and not basso.startswith('~$'):
            return os.path.join(root, nome)
    return ''


def scansiona(root):
    """
    Ispeziona la root di un'azienda e descrive cosa e' utilizzabile.

    OUTPUT: dizionario con le chiavi
        root, valida, errore
        rumore      {presente, main, misure, output, cartelle, avvisi, scheda,
                     vr8h_totale, vr8h_riepilogo, vr8h_aggiornato}
        vibrazioni  {presente, main, misure, output, file, scheda,
                     misureVIB, vr_vib}
        scheda      percorso di scheda_gruppi_dpi.xlsx, cercato nella root
        scheda_mancante  True se nella root non c'e'
        modalita_suggerita
    """
    root = os.path.abspath(os.path.expanduser(root or ''))
    esito = {'root': root, 'valida': False, 'errore': '',
             'rumore': {'presente': False}, 'vibrazioni': {'presente': False},
             'scheda': '', 'modalita_suggerita': 'rumore'}

    if not os.path.isdir(root):
        esito['errore'] = 'La cartella indicata non esiste.'
        return esito

    ramo_rumore = _cerca_ramo(root, NOMI_RUMORE)
    ramo_vibrazioni = _cerca_ramo(root, NOMI_VIBRAZIONI)

    # se non c'e' nessun ramo, la root stessa e' la cartella di lavoro:
    # si decide in base alla presenza di misure/
    if ramo_rumore is None and ramo_vibrazioni is None:
        if os.path.isdir(os.path.join(root, NOME_MISURE)):
            file_vib = _trova_file_vibrazioni(os.path.join(root, NOME_MISURE))
            if any(file_vib.values()):
                ramo_vibrazioni = root
            else:
                ramo_rumore = root
        else:
            esito['errore'] = ('Nella cartella scelta non ci sono ne\' Rumore/ ne\' '
                               'Vibrazioni/ ne\' misure/.')
            return esito

    # ---- ramo rumore ----
    if ramo_rumore:
        misure = os.path.join(ramo_rumore, NOME_MISURE)
        output = os.path.join(ramo_rumore, NOME_OUTPUT)
        cartelle, avvisi = analizza_misure_rumore(misure)
        esito['rumore'] = {
            'presente': True,
            'main': ramo_rumore,
            'misure': misure,
            'output': output,
            'output_pronta': os.path.isdir(output),
            'cartelle': cartelle,
            'avvisi': avvisi,
            'vr8h_totale': os.path.join(output, 'VR8h_totale.xlsx'),
            'vr8h_riepilogo': os.path.join(output, 'VR8h_riepilogo.xlsx'),
            'vr8h_aggiornato': os.path.join(output, 'VR8h_totale_aggiornato.xlsx'),
        }

    # ---- ramo vibrazioni ----
    if ramo_vibrazioni:
        misure = os.path.join(ramo_vibrazioni, NOME_MISURE)
        output = os.path.join(ramo_vibrazioni, NOME_OUTPUT)
        esito['vibrazioni'] = {
            'presente': True,
            'main': ramo_vibrazioni,
            'misure': misure,
            'output': output,
            'output_pronta': os.path.isdir(output),
            'file': _trova_file_vibrazioni(misure),
            'misureVIB': os.path.join(output, 'misureVIB.xlsx'),
            'vr_vib': _primo_esistente(
                os.path.join(output, 'VR_VIB.xlsx'),
                # molti lavori hanno ancora il foglio compilato a mano nella
                # root del ramo: finche' non si rilancia l'analisi e' l'unico
                # risultato disponibile, e vale la pena mostrarlo
                os.path.join(ramo_vibrazioni, 'VRV.xlsx'),
                os.path.join(ramo_vibrazioni, 'VR_VIB.xlsx')),
        }

    # ---- scheda condivisa ----
    # Sta nella root perche' rumore e vibrazioni la usano entrambi: la si
    # risolve qui una volta per tutte e la si passa esplicitamente ai runner,
    # che altrimenti la cercherebbero ognuno per conto proprio.
    esito['scheda'] = _trova_scheda(root)
    esito['scheda_mancante'] = not esito['scheda']
    if esito['rumore']['presente']:
        esito['rumore']['scheda'] = esito['scheda']
    if esito['vibrazioni']['presente']:
        esito['vibrazioni']['scheda'] = esito['scheda']

    ha_rumore = esito['rumore']['presente']
    ha_vibrazioni = esito['vibrazioni']['presente'] and any(
        esito['vibrazioni']['file'].values())
    if ha_rumore and ha_vibrazioni:
        esito['modalita_suggerita'] = 'combinato'
    elif ha_vibrazioni:
        esito['modalita_suggerita'] = 'vibrazioni'
    else:
        esito['modalita_suggerita'] = 'rumore'

    esito['valida'] = ha_rumore or esito['vibrazioni']['presente']
    if not esito['valida']:
        esito['errore'] = 'Nessun dato di misura riconosciuto nella cartella.'
    return esito


# ---------------------------------------------------------------------------
# Dati della relazione, accanto al lavoro a cui appartengono
# ---------------------------------------------------------------------------
#
# Stanno nella root e non nella configurazione dell'applicazione: sono dati
# dell'azienda, non dell'installazione. Cosi' seguono la cartella se la si
# sposta o la si copia su un'altra macchina, e all'apertura si ricaricano da
# soli invece di doverli richiamare a mano.


def percorso_dati_relazione(root):
    """Percorso di relazione_dati.json nella root indicata."""
    if not root:
        return ''
    return os.path.join(os.path.abspath(os.path.expanduser(root)), NOME_DATI_RELAZIONE)


def leggi_dati_relazione(root):
    """
    Legge i dati della relazione dalla root.

    Un file rovinato non deve impedire di aprire la cartella: in quel caso si
    riporta trovato=False e si riparte da campi vuoti.

    OUTPUT: {'trovato': bool, 'dati': dict, 'percorso': str}
    """
    percorso = percorso_dati_relazione(root)
    esito = {'trovato': False, 'dati': {}, 'percorso': percorso}
    if not percorso or not os.path.exists(percorso):
        return esito
    try:
        with open(percorso, encoding='utf-8') as f:
            dati = json.load(f)
    except (json.JSONDecodeError, OSError):
        return esito
    if not isinstance(dati, dict):
        return esito
    esito['trovato'] = True
    esito['dati'] = dati
    return esito


def scrivi_dati_relazione(root, dati):
    """
    Salva i dati della relazione nella root, sovrascrivendo.

    'esisteva' viene letto prima di scrivere: e' quello che serve
    all'interfaccia per dire se ha sostituito un file gia' presente.

    OUTPUT: {'ok', 'percorso', 'esisteva', 'errore'}
    """
    percorso = percorso_dati_relazione(root)
    if not percorso:
        return {'ok': False, 'percorso': '', 'esisteva': False,
                'errore': 'Nessuna cartella di lavoro aperta.'}
    esisteva = os.path.exists(percorso)
    try:
        with open(percorso, 'w', encoding='utf-8') as f:
            json.dump(dati or {}, f, indent=2, ensure_ascii=False)
    except OSError as errore:
        return {'ok': False, 'percorso': percorso, 'esisteva': esisteva,
                'errore': str(errore)}
    return {'ok': True, 'percorso': percorso, 'esisteva': esisteva, 'errore': ''}
