#! /usr/bin/env python3
"""
Configurazione dell'applicazione, raccolta in un'unica directory.

Tutti i file di configurazione vivono in ~/.analisirischio (sovrascrivibile con
la variabile d'ambiente ANALISIRISCHIO_HOME):

    config.json                 percorsi dei backend, modelli, ultima root aperta
    parametri_rumore.json       costanti di calcolo VRR
    parametri_vibrazioni.json   costanti di calcolo VRV
    progetti_recenti.json       elenco delle ultime root aperte

I dati della relazione Word non stanno qui: sono dati dell'azienda, non
dell'installazione, e vivono in <root>/relazione_dati.json (vedi core/progetto.py).

I parameters.py di VRR_analisiDati e VRV_analisiDati non vengono mai riscritti:
da li' si leggono soltanto i valori di default al primo avvio.
"""

import json
import os

NOME_CARTELLA = '.analisirischio'

CONFIG = 'config.json'
PARAMETRI_RUMORE = 'parametri_rumore.json'
PARAMETRI_VIBRAZIONI = 'parametri_vibrazioni.json'
PROGETTI_RECENTI = 'progetti_recenti.json'

MAX_PROGETTI_RECENTI = 12

# sottocartella dei frontespizi per ramo
SOTTOCARTELLA_FRONTESPIZI = {'rumore': 'RUM', 'vibrazioni': 'VIB'}

# Valori di riferimento presi dai due backend. Servono come default al primo
# avvio: da quel momento in poi fa fede il contenuto della directory di config.
DEFAULT_RUMORE = {
    'T0': 480.0,            # minuti della giornata lavorativa di riferimento
    'u2m': 0.7,             # incertezza del metodo di misura
    'u_pos': 1.0,           # incertezza di posizionamento del microfono
    'VERSIONE_FIRMWARE': '2',   # firmware del fonometro VR: '1' oppure '2'
    'LIMITE_LEX8H': 87.0,   # valore limite di esposizione, dBA
    'SOGLIA_MEDIA': 80.0,   # Lex max: sotto questo valore la classe e' BASSA
    'SOGLIA_ALTA': 85.0,    # Lex max: da questo valore la classe e' ALTA
    # rileggere i file di misura ricalcola averaged_data.csv da zero,
    # perdendo le misure corrette o aggiunte a mano: non e' il default
    'rileggi_misure': False,
    'esporta_pdf': True,
}

DEFAULT_VIBRAZIONI = {
    'T0': 480.0,
    'C_P_HAV': 0.10,        # incertezza di posizionamento dello strumento, HAV
    'C_P_WBV': 0.05,        # incertezza di posizionamento dello strumento, WBV
    'C_S': 0.01,            # incertezza strumentale: US = C_S * Aw
    'FATTORE_XY_WBV': 1.4,  # fattore di pesatura degli assi X e Y
    'MAX_LIMIT_HAV': 5.0,
    'MAX_ACTION_HAV': 2.5,
    'MAX_LIMIT_WBV': 1.0,
    'MAX_ACTION_WBV': 0.5,
    'LIMITE_BREVI_HAV': 20.0,
    'LIMITE_BREVI_WBV': 1.5,
    'SOGLIA_FC_IMPULSIVO': 9.0,
    'SOGLIA_MEDIA_HAV': 2.5,
    'SOGLIA_ALTA_HAV': 5.0,
    'SOGLIA_MEDIA_WBV': 0.5,
    'SOGLIA_ALTA_WBV': 1.0,
    'DECIMALI': 2,
    'DECIMALI_INCERTEZZE': 3,
    'ESPORTA_PDF': True,
}

# Percorsi ricostruiti rispetto a questo progetto: AnalisiRischio, VRR e VRV
# sono cartelle sorelle dentro Codici/.
_CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CODICI = os.path.dirname(_CARTELLA_PROGETTO)

DEFAULT_CONFIG = {
    'percorso_vrr': os.path.join(_CODICI, 'VRR_analisiDati', 'VRR_analisiDati'),
    'percorso_vrv': os.path.join(_CODICI, 'VRV_analisiDati', 'VRV_analisiDati'),
    'cartella_modelli': os.path.join(
        os.path.dirname(os.path.dirname(_CODICI)), 'Ermes', 'Modelli'),
    'cartella_lavori': os.path.join(
        os.path.dirname(os.path.dirname(_CODICI)), 'Ermes', 'Lavori'),
    # modelli gia' corretti dalle utility fix_template_*.py dei due backend:
    # sono quelli che i write_docx si aspettano, con i tag Jinja al posto giusto
    'modello_relazione_rumore': 'docx/strutture/Modello_RUM.docx',
    'modello_relazione_vibrazioni': 'docx/strutture/Modello_VIB.docx',
    # frontespizi: una sottocartella per ramo, il nome del file si sceglie
    # dalla schermata della relazione
    'cartella_frontespizi': 'docx/frontespizi',
    # cartelle scelte dall'interfaccia, per ramo: vuoto significa la
    # sottocartella RUM/VIB di 'cartella_frontespizi'
    'cartella_frontespizi_rumore': '',
    'cartella_frontespizi_vibrazioni': '',
    'frontespizio_rumore': 'RUM/frontespizio_Relyon_RUM.docx',
    'frontespizio_vibrazioni': 'VIB/frontespizio_Relyon_VIB.docx',
    # logo aziendale: vuoto significa campo lasciato vuoto nel documento
    'logo_azienda': '',
    'ultima_root': '',
    'modalita': 'rumore',
    'tema': 'scuro',
    # posizione e dimensione dell'ultima finestra: [x, y, larghezza, altezza]
    'geometria_finestra': [],
    'finestra_massimizzata': False,
}


def cartella_config():
    """Percorso della directory di configurazione, creata se assente."""
    base = os.environ.get('ANALISIRISCHIO_HOME')
    if not base:
        base = os.path.join(os.path.expanduser('~'), NOME_CARTELLA)
    os.makedirs(base, exist_ok=True)
    return base


def _percorso(nome):
    return os.path.join(cartella_config(), nome)


def leggi(nome, default=None):
    """
    Legge un file JSON della directory di configurazione.

    Se il file non esiste, o e' illeggibile, restituisce una copia del default
    (e in quel caso lo riscrive, cosi' la directory e' sempre ispezionabile).
    """
    default = {} if default is None else default
    percorso = _percorso(nome)
    if os.path.exists(percorso):
        try:
            with open(percorso, encoding='utf-8') as f:
                dati = json.load(f)
            if isinstance(dati, dict):
                # le chiavi nuove introdotte da una versione successiva
                # dell'applicazione vengono aggiunte con il loro default
                completo = dict(default)
                completo.update(dati)
                return completo
            return dati
        except (json.JSONDecodeError, OSError):
            pass
    scrivi(nome, default)
    return dict(default) if isinstance(default, dict) else default


def scrivi(nome, dati):
    """Salva un file JSON nella directory di configurazione."""
    percorso = _percorso(nome)
    os.makedirs(os.path.dirname(percorso), exist_ok=True)
    with open(percorso, 'w', encoding='utf-8') as f:
        json.dump(dati, f, indent=2, ensure_ascii=False)
    return percorso


# Valori di 'modello_relazione_*' scritti dalle versioni precedenti: puntavano
# a modelli senza i tag Jinja, che i write_docx dei backend non sanno compilare.
# Vanno sostituiti una volta sola, senza toccare le scelte fatte dall'utente.
MODELLI_SUPERATI = {
    'modello_relazione_rumore': ('docx/Modello_Relazione_RUM_v2.docx',),
    'modello_relazione_vibrazioni': ('docx/Modello_Relazione_VIB.docx',),
}


def config():
    """Configurazione corrente, con i modelli superati gia' aggiornati."""
    cfg = leggi(CONFIG, DEFAULT_CONFIG)
    cambiata = False
    for chiave, superati in MODELLI_SUPERATI.items():
        if cfg.get(chiave) in superati:
            cfg[chiave] = DEFAULT_CONFIG[chiave]
            cambiata = True
    if cambiata:
        scrivi(CONFIG, cfg)
    return cfg


def parametri_rumore():
    return leggi(PARAMETRI_RUMORE, DEFAULT_RUMORE)


def parametri_vibrazioni():
    return leggi(PARAMETRI_VIBRAZIONI, DEFAULT_VIBRAZIONI)


def progetti_recenti():
    dati = leggi(PROGETTI_RECENTI, [])
    return dati if isinstance(dati, list) else []


def aggiungi_progetto_recente(root):
    """Sposta 'root' in cima all'elenco dei progetti recenti."""
    if not root:
        return progetti_recenti()
    elenco = [p for p in progetti_recenti() if p != root]
    elenco.insert(0, root)
    elenco = elenco[:MAX_PROGETTI_RECENTI]
    scrivi(PROGETTI_RECENTI, elenco)
    return elenco


def percorso_modello(chiave):
    """
    Percorso assoluto di un modello .docx a partire dalla chiave di config.

    Il percorso salvato in config puo' essere relativo alla cartella dei
    modelli oppure gia' assoluto.
    """
    cfg = config()
    relativo = cfg.get(chiave, '')
    if not relativo:
        return ''
    if os.path.isabs(relativo):
        return relativo
    return os.path.join(cfg.get('cartella_modelli', ''), relativo)


def cartella_frontespizi(ramo=''):
    """
    Percorso assoluto della cartella dei frontespizi, per ramo.

    INPUT:  ramo - 'rumore', 'vibrazioni' oppure '' per la cartella radice
    OUTPUT: percorso assoluto (anche se la cartella non esiste)

    Per un ramo vale prima la cartella scelta dall'interfaccia
    ('cartella_frontespizi_<ramo>'); se e' vuota, la sottocartella RUM/VIB
    della cartella radice.
    """
    cfg = config()
    if ramo:
        scelta = cfg.get(f'cartella_frontespizi_{ramo}', '')
        if scelta:
            return os.path.expanduser(scelta)
    base = cfg.get('cartella_frontespizi', '')
    if not os.path.isabs(base):
        base = os.path.join(cfg.get('cartella_modelli', ''), base)
    return os.path.join(base, SOTTOCARTELLA_FRONTESPIZI.get(ramo, '')) if ramo else base


def frontespizi_disponibili(ramo):
    """Elenco dei file .docx presenti nella cartella dei frontespizi del ramo."""
    cartella = cartella_frontespizi(ramo)
    if not os.path.isdir(cartella):
        return []
    return sorted(n for n in os.listdir(cartella)
                  if n.lower().endswith('.docx') and not n.startswith('~$'))


def percorso_frontespizio(nome):
    """
    Percorso assoluto di un frontespizio a partire dal nome salvato in config.

    Il nome puo' essere gia' assoluto, oppure relativo alla cartella dei
    frontespizi ('RUM/frontespizio_Relyon_RUM.docx' o il solo nome del file
    quando il ramo lo si sceglie dall'interfaccia).
    """
    if not nome:
        return ''
    if os.path.isabs(nome):
        return nome
    return os.path.join(cartella_frontespizi(), nome)
