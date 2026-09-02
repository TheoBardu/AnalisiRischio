#! /usr/bin/env python3
"""
Costruzione del contesto per la relazione Word.

I nomi dei campi ricalcano quelli dei due write_docx dei backend
(VRR/utility/write_docx_Rumore.py e VRV/utility/write_docx_vib.py), che
compilano i modelli con docxtpl: cosi' i modelli esistenti continuano a valere.

I campi sono divisi in tre blocchi, come la SEZIONE 1 dei due script:
    comuni      - anagrafica e testi che compaiono identici in entrambi i modelli
    rumore      - metodo adottato, orari, colonne del quadro sinottico
    vibrazioni  - orario di lavoro e frontespizio del ramo

Le tabelle che i vecchi script lasciavano da compilare a mano qui vengono
precompilate dai risultati dell'analisi: tabella_HEG dal riepilogo del rumore,
tabella_dpi dal foglio Scheda_DPI e tabella_vibrazioni dalle schede A(8).
"""

# Testi predefiniti: sono esattamente quelli della SEZIONE 1 dei due backend,
# cosi' un progetto nuovo parte compilato come partiva prima a mano.
TESTO_OTOTOSSICHE = ('Si faccia riferimento al documento di valutazione del '
                     'rischio chimico.')
TESTO_VIB_RUM = ('Certamente si considerato l’utilizzo di attrezzature '
                 'elettriche portatili. Vi è dunque trasmissione ossea delle '
                 'vibrazioni e del rumore all’orecchio medio. Si faccia '
                 'riferimento alla valutazione del rischio chimico.')
TESTO_EFFETTI = ('Nelle zone/postazioni di lavoro è possibile che gli addetti '
                 'possano incorrere in tali situazioni. Si consiglia pertanto di '
                 'utilizzare D.P.I. con grado di protezione SNR come prescritto '
                 'dalla presente relazione e l’adozione di sistemi '
                 'alternativi quali segnali oto-acustici.')
ORARIO_RUMORE = 'Lunedì – Venerdì \n 8:00÷12:00 13:00÷17:00'
ORARIO_VIBRAZIONI = 'Lunedì – Venerdì  8:00÷12:00  13:00÷17:00'

# I campi del modulo: sono il riflesso dei segnaposto dei modelli .docx, e i
# nomi delle chiavi devono restare quelli che i modelli si aspettano.
#   tipo      - 'testo' (default), 'testolungo', 'sino', 'flag', 'scelta', 'file'
#   valore    - valore predefinito
#   mono      - campo da mostrare in monospazio, perche' contiene numeri o date
#   larghezza - larghezza fissa, per i campi molto corti
CAMPI_COMUNI = [
    {'chiave': 'nome_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'indirizzo_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'attivita_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'sede_legale', 'gruppo': 'Azienda'},
    {'chiave': 'sede_operativa', 'gruppo': 'Azienda'},
    {'chiave': 'processo_produttivo', 'gruppo': 'Azienda', 'tipo': 'testolungo'},

    {'chiave': 'datore_di_lavoro', 'gruppo': 'Figure responsabili'},
    {'chiave': 'RSPP', 'gruppo': 'Figure responsabili'},
    {'chiave': 'medico_competente', 'gruppo': 'Figure responsabili'},
    {'chiave': 'RLS', 'gruppo': 'Figure responsabili'},
    {'chiave': 'delegato_sicurezza', 'gruppo': 'Figure responsabili'},

    {'chiave': 'revisione', 'gruppo': 'Documento', 'mono': True, 'valore': 'rev.01'},
    {'chiave': 'data_emissione', 'gruppo': 'Documento', 'mono': True},
    {'chiave': 'data_scadenza', 'gruppo': 'Documento', 'mono': True},
    {'chiave': 'motivo_revisione', 'gruppo': 'Documento'},

    {'chiave': 'giornate', 'gruppo': 'Misurazioni', 'mono': True, 'larghezza': '90px'},
    {'chiave': 'date_misurazione', 'gruppo': 'Misurazioni'},
    {'chiave': 'strumentazione', 'gruppo': 'Misurazioni'},

    {'chiave': 'sostanze_ototossiche', 'gruppo': 'Ototossici e interazioni',
     'tipo': 'sino', 'valore': 'Si'},
    {'chiave': 'misure_attuative_ototossiche', 'gruppo': 'Ototossici e interazioni',
     'tipo': 'testolungo', 'valore': TESTO_OTOTOSSICHE},
    {'chiave': 'interazione_vib_rum', 'gruppo': 'Ototossici e interazioni',
     'tipo': 'sino', 'valore': 'Si'},
    {'chiave': 'misure_attuative_vib_rum', 'gruppo': 'Ototossici e interazioni',
     'tipo': 'testolungo', 'valore': TESTO_VIB_RUM},
    {'chiave': 'effetti_indesiderati', 'gruppo': 'Ototossici e interazioni',
     'tipo': 'sino', 'valore': 'Si'},
    {'chiave': 'misure_attuative_effetti_indesiderati',
     'gruppo': 'Ototossici e interazioni', 'tipo': 'testolungo', 'valore': TESTO_EFFETTI},

    {'chiave': 'logo_azienda', 'gruppo': 'Logo', 'tipo': 'file',
     'etichetta': 'logo_azienda (vuoto = nessun logo)'},
]

CAMPI_RUMORE = [
    {'chiave': 'base_giornaliera', 'gruppo': 'Metodo adottato', 'tipo': 'testolungo'},
    {'chiave': 'base_settimanale', 'gruppo': 'Metodo adottato', 'tipo': 'testolungo'},
    {'chiave': 'esposizioni_variabili', 'gruppo': 'Metodo adottato', 'tipo': 'testolungo'},

    {'chiave': 'orari_uguali_per_tutti', 'gruppo': 'Orario di lavoro', 'tipo': 'flag',
     'valore': True, 'etichetta': 'orari uguali per tutte le mansioni'},
    {'chiave': 'orario_lavoro_default', 'gruppo': 'Orario di lavoro',
     'tipo': 'testolungo', 'valore': ORARIO_RUMORE},

    {'chiave': 'ototossici_default', 'gruppo': 'Colonne del quadro sinottico',
     'tipo': 'sino', 'valore': 'NO',
     'etichetta': 'ototossici (colonna non presente negli excel)'},
    {'chiave': 'impulsivi_default', 'gruppo': 'Colonne del quadro sinottico',
     'tipo': 'sino', 'valore': 'NO',
     'etichetta': 'rumori impulsivi (colonna non presente negli excel)'},

    {'chiave': 'frontespizio_rumore', 'gruppo': 'Documento', 'tipo': 'scelta',
     'etichetta': 'frontespizio'},
]

CAMPI_VIBRAZIONI = [
    {'chiave': 'orario_lavoro', 'gruppo': 'Orario di lavoro',
     'tipo': 'testolungo', 'valore': ORARIO_VIBRAZIONI},
    {'chiave': 'frontespizio_vibrazioni', 'gruppo': 'Documento', 'tipo': 'scelta',
     'etichetta': 'frontespizio'},
]

CAMPI = {'comuni': CAMPI_COMUNI, 'rumore': CAMPI_RUMORE,
         'vibrazioni': CAMPI_VIBRAZIONI}

# Disposizione dei moduli, ricalcata dal mockup: due colonne, i gruppi uno
# sotto l'altro, e dentro ogni gruppo le righe di campi affiancati. Sta
# separata dai campi perche' e' impaginazione, non contenuto del documento: i
# campi che non compaiono qui vengono comunque disegnati in fondo.
LAYOUT_COMUNI = [
    [   # colonna di sinistra
        {'nome': 'Azienda',
         'righe': [['nome_azienda'], ['indirizzo_azienda'], ['attivita_azienda'],
                   ['sede_legale'], ['sede_operativa'], ['processo_produttivo']]},
        {'nome': 'Figure responsabili',
         'righe': [['datore_di_lavoro', 'RSPP'], ['medico_competente', 'RLS'],
                   ['delegato_sicurezza']]},
        {'nome': 'Logo', 'righe': [['logo_azienda']]},
    ],
    [   # colonna di destra
        {'nome': 'Documento',
         'righe': [['revisione', 'data_emissione', 'data_scadenza'],
                   ['motivo_revisione']]},
        {'nome': 'Misurazioni',
         'righe': [['giornate', 'date_misurazione'], ['strumentazione']]},
        {'nome': 'Ototossici e interazioni',
         'righe': [['sostanze_ototossiche'], ['misure_attuative_ototossiche'],
                   ['interazione_vib_rum'], ['misure_attuative_vib_rum'],
                   ['effetti_indesiderati'],
                   ['misure_attuative_effetti_indesiderati']]},
    ],
]

LAYOUT_RUMORE = [
    [
        {'nome': 'Metodo adottato',
         'righe': [['base_giornaliera'], ['base_settimanale'],
                   ['esposizioni_variabili']]},
    ],
    [
        {'nome': 'Orario di lavoro',
         'righe': [['orari_uguali_per_tutti'], ['orario_lavoro_default']]},
        {'nome': 'Colonne del quadro sinottico',
         'righe': [['ototossici_default'], ['impulsivi_default']]},
        {'nome': 'Documento', 'righe': [['frontespizio_rumore']]},
    ],
]

LAYOUT_VIBRAZIONI = [
    [
        {'nome': 'Orario di lavoro', 'righe': [['orario_lavoro']]},
    ],
    [
        {'nome': 'Documento', 'righe': [['frontespizio_vibrazioni']]},
    ],
]

LAYOUT = {'comuni': LAYOUT_COMUNI, 'rumore': LAYOUT_RUMORE,
          'vibrazioni': LAYOUT_VIBRAZIONI}

# Chiavi che pilotano la scrittura invece di finire nel documento: il runner le
# legge a parte, e docxtpl le ignorerebbe comunque.
CHIAVI_CONTROLLO = ('orari_uguali_per_tutti', 'orario_lavoro_default',
                    'ototossici_default', 'impulsivi_default',
                    'frontespizio_rumore', 'frontespizio_vibrazioni',
                    'logo_azienda')

COLONNE_TABELLA_DPI = ['codice_DPI', 'descrizione', 'marca', 'modello',
                       'snr', 'H', 'L', 'M']
COLONNE_TABELLA_HEG = ['codice_HEG', 'gruppo_HEG', 'lex8h', 'incertezza',
                       'lexmax', 'peakmax', 'classe_rischio']
COLONNE_TABELLA_VIB = ['codice_HEG', 'gruppo_HEG', 'a8_HAV', 'classe_HAV',
                       'a8_WBV', 'classe_WBV']

FRASE_PRESENZA = {
    True: 'sono presenti gruppi omogenei in classe di rischio ALTA',
    False: 'nessun gruppo omogeneo ricade in classe di rischio ALTA',
}


def elenco_campi(blocchi=('comuni', 'rumore', 'vibrazioni')):
    """Campi di piu' blocchi in un'unica lista, con l'etichetta sempre valorizzata."""
    elenco = []
    for blocco in blocchi:
        for campo in CAMPI.get(blocco, []):
            voce = dict(campo)
            voce.setdefault('etichetta', voce['chiave'])
            voce.setdefault('tipo', 'testo')
            voce['blocco'] = blocco
            elenco.append(voce)
    return elenco


def campi_vuoti(blocchi=('comuni', 'rumore', 'vibrazioni')):
    """Dizionario dei campi con i valori predefiniti."""
    return {campo['chiave']: campo.get('valore', '')
            for campo in elenco_campi(blocchi)}


def blocchi_di(ramo):
    """Blocchi di campi che servono a un ramo. OUTPUT: tupla di nomi."""
    if ramo in ('rumore', 'vibrazioni'):
        return ('comuni', ramo)
    return ('comuni', 'rumore', 'vibrazioni')


def tabella_dpi(righe_dpi, colonne_dpi):
    """
    Scheda_DPI -> righe della tabella della relazione.

    Le chiavi sono minuscole come le attende il modello docx, mentre il foglio
    excel usa nomi con le maiuscole.
    """
    mappa = {nome: indice for indice, nome in enumerate(colonne_dpi)}

    def prendi(riga, nome):
        indice = mappa.get(nome)
        return riga[indice] if indice is not None and indice < len(riga) else ''

    return [{
        'codice_DPI': prendi(riga, 'codice_DPI'),
        'descrizione': prendi(riga, 'Descrizione'),
        'marca': prendi(riga, 'Marca'),
        'modello': prendi(riga, 'Modello'),
        'snr': prendi(riga, 'SNR'),
        'H': prendi(riga, 'H'),
        'L': prendi(riga, 'L'),
        'M': prendi(riga, 'M'),
    } for riga in righe_dpi]


def tabella_heg(gruppi_rumore):
    """Riepilogo del rumore -> tabella dei gruppi omogenei della relazione."""
    return [{
        'codice_HEG': gruppo.get('code', ''),
        'gruppo_HEG': gruppo.get('nome', ''),
        'numero_scheda': gruppo.get('code', ''),
        'parametro_riferimento': 'Lex,8h',
        'lex8h': gruppo.get('lex', ''),
        'incertezza': gruppo.get('u', ''),
        'lexmax': gruppo.get('lexmax', ''),
        'peakmax': gruppo.get('picco', ''),
        'classe_rischio': gruppo.get('classe', ''),
    } for gruppo in gruppi_rumore]


def tabella_vibrazioni(gruppi_vibrazioni):
    """Riepilogo delle vibrazioni -> tabella A(8) della relazione."""
    return [{
        'codice_HEG': gruppo.get('code', ''),
        'gruppo_HEG': gruppo.get('nome', ''),
        'a8_HAV': (gruppo.get('HAV') or {}).get('a8', ''),
        'classe_HAV': (gruppo.get('HAV') or {}).get('classe', ''),
        'a8_WBV': (gruppo.get('WBV') or {}).get('a8', ''),
        'classe_WBV': (gruppo.get('WBV') or {}).get('classe', ''),
    } for gruppo in gruppi_vibrazioni]


def costruisci(campi, gruppi_rumore=None, gruppi_vibrazioni=None,
               righe_dpi=None, colonne_dpi=None, ramo=''):
    """
    Contesto delle anteprime e base del contesto docxtpl.

    Le tabelle vere del documento le ricostruiscono i backend dentro
    runner/runner_relazione.py, leggendo gli excel con openpyxl per riprendersi
    anche i colori delle celle: queste servono all'interfaccia, che le mostra in
    sola lettura, e restano comunque nel contesto come ripiego.

    INPUT:  campi            - valori dei moduli 'Dati generali'
            gruppi_rumore    - gruppi dalla sintesi del rumore
            gruppi_vibrazioni- gruppi dalla sintesi delle vibrazioni
            righe_dpi        - righe del foglio Scheda_DPI
            ramo             - 'rumore', 'vibrazioni' o '' per tutti i campi
    OUTPUT: dizionario pronto per docxtpl
    """
    gruppi_rumore = gruppi_rumore or []
    gruppi_vibrazioni = gruppi_vibrazioni or []

    contesto = dict(campi_vuoti(blocchi_di(ramo)))
    contesto.update({k: v for k, v in (campi or {}).items()})

    # date_misurazione nei modelli e' una lista: si accetta anche il testo
    # separato da virgole scritto nel modulo
    grezzo = contesto.get('date_misurazione', '')
    if isinstance(grezzo, str):
        contesto['date_misurazione'] = [p.strip() for p in grezzo.split(',') if p.strip()]

    presenza_alta = any(g.get('classe') == 'ALTA' for g in gruppi_rumore)
    contesto.update({
        'tabella_dpi': tabella_dpi(righe_dpi or [], colonne_dpi or []),
        'tabella_HEG': tabella_heg(gruppi_rumore),
        'tabella_vibrazioni': tabella_vibrazioni(gruppi_vibrazioni),
        'presenza_classe_alta': presenza_alta,
        'frase_presenza': FRASE_PRESENZA[presenza_alta],
        'n_gruppi': len(gruppi_rumore),
        'n_gruppi_alta': sum(1 for g in gruppi_rumore if g.get('classe') == 'ALTA'),
    })
    return contesto
