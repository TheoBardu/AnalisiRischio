#! /usr/bin/env python3
"""
Costruzione del contesto per la relazione Word.

I nomi dei campi ricalcano quelli gia' usati da VRR/utility/write_docx.py, che
compila il modello con docxtpl: cosi' i modelli esistenti continuano a valere.

Le due tabelle che il vecchio script lasciava da compilare a mano - un commento
nel file suggeriva di prenderle dai fogli excel - qui vengono precompilate dai
risultati dell'analisi: tabella_HEG dal riepilogo del rumore e tabella_dpi dal
foglio Scheda_DPI.
"""

# I campi del modulo: sono il riflesso dei segnaposto del modello .docx, e i
# nomi delle chiavi devono restare quelli che il modello si aspetta.
#   mono      - campo da mostrare in monospazio, perche' contiene numeri o date
#   larghezza - larghezza fissa, per i campi molto corti
CAMPI_GENERALI = [
    {'chiave': 'nome_azienda', 'etichetta': 'nome_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'indirizzo_azienda', 'etichetta': 'indirizzo_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'attivita_azienda', 'etichetta': 'attivita_azienda', 'gruppo': 'Azienda'},
    {'chiave': 'datore_di_lavoro', 'etichetta': 'datore_di_lavoro', 'gruppo': 'Figure responsabili'},
    {'chiave': 'RSPP', 'etichetta': 'RSPP', 'gruppo': 'Figure responsabili'},
    {'chiave': 'medico_competente', 'etichetta': 'medico_competente', 'gruppo': 'Figure responsabili'},
    {'chiave': 'RLS', 'etichetta': 'RLS', 'gruppo': 'Figure responsabili'},
    {'chiave': 'revisione', 'etichetta': 'revisione', 'gruppo': 'Documento', 'mono': True},
    {'chiave': 'data_revisione', 'etichetta': 'data_revisione', 'gruppo': 'Documento', 'mono': True},
    {'chiave': 'data_scadenza', 'etichetta': 'data_scadenza', 'gruppo': 'Documento', 'mono': True},
    {'chiave': 'motivo_revisione', 'etichetta': 'motivo_revisione', 'gruppo': 'Documento'},
    {'chiave': 'giornate', 'etichetta': 'giornate', 'gruppo': 'Misurazioni',
     'mono': True, 'larghezza': '90px'},
    {'chiave': 'date_misurazione', 'etichetta': 'date_misurazione', 'gruppo': 'Misurazioni'},
    {'chiave': 'strumentazione', 'etichetta': 'strumentazione', 'gruppo': 'Misurazioni'},
]

# Disposizione del modulo, ricalcata dal mockup: due colonne, i gruppi uno
# sotto l'altro, e dentro ogni gruppo le righe di campi affiancati. Sta
# separata da CAMPI_GENERALI perche' e' impaginazione, non contenuto del
# documento: i campi che non compaiono qui vengono comunque disegnati in fondo.
LAYOUT_GENERALI = [
    [   # colonna di sinistra
        {'nome': 'Azienda',
         'righe': [['nome_azienda'], ['indirizzo_azienda'], ['attivita_azienda']]},
        {'nome': 'Figure responsabili',
         'righe': [['datore_di_lavoro', 'RSPP'], ['medico_competente', 'RLS']]},
    ],
    [   # colonna di destra
        {'nome': 'Documento',
         'righe': [['revisione', 'data_revisione', 'data_scadenza'],
                   ['motivo_revisione']]},
        {'nome': 'Misurazioni',
         'righe': [['giornate', 'date_misurazione'], ['strumentazione']]},
    ],
]

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


def campi_vuoti():
    """Dizionario dei campi generali, tutti vuoti."""
    return {campo['chiave']: '' for campo in CAMPI_GENERALI}


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
               righe_dpi=None, colonne_dpi=None):
    """
    Contesto completo da passare al generatore.

    INPUT:  campi            - valori del modulo 'Dati generali'
            gruppi_rumore    - gruppi dalla sintesi del rumore
            gruppi_vibrazioni- gruppi dalla sintesi delle vibrazioni
            righe_dpi        - righe del foglio Scheda_DPI
    OUTPUT: dizionario pronto per docxtpl
    """
    gruppi_rumore = gruppi_rumore or []
    gruppi_vibrazioni = gruppi_vibrazioni or []

    contesto = dict(campi_vuoti())
    contesto.update({k: v for k, v in (campi or {}).items()})

    # date_misurazione nel modello e' una lista: si accetta anche il testo
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
