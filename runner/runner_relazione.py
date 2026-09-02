#! /usr/bin/env python3
"""
Scrittura della relazione .docx usando i write_docx dei due backend.

Gira in un processo separato per lo stesso motivo delle altre pipeline: i due
backend importano entrambi un modulo chiamato 'config', con contenuti diversi,
e nello stesso interprete uno sovrascriverebbe l'altro. Un processo per ramo.

I due script dei backend non sono richiamabili cosi' come sono:

    write_docx_Rumore.py  non ha un main(): le righe dalla SEZIONE 3 in poi
        girano all'import e scrivono un documento contro percorsi cablati. Qui
        se ne carica soltanto la testa, fino alla sentinella della SEZIONE 3,
        ottenendo tutte le funzioni di caricamento senza eseguirne il corpo.

    write_docx_vib.py  ha un main(), ma legge i percorsi dai propri globali e i
        parametri di calcolo da parameters.py.

In entrambi i casi si sovrascrivono i globali dei percorsi con quelli che
arrivano dall'interfaccia e si ripete la sola SEZIONE 3 - l'unione dei
dizionari - qui dentro, cosi' i passi hanno una granularita' e i backend
restano intatti.

USO: python runner_relazione.py <configurazione.json>
"""

import os
import sys
import time
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from relazione import contesto as modulo_contesto
from runner import passi as elenco_passi
from runner import protocollo
from runner.protocollo import Sequenza, carica_modulo, emetti, log, parametri_backend

NOME_VR8H_RIEPILOGO = 'VR8h_riepilogo.xlsx'
NOME_MISURE_VIB = 'misureVIB.xlsx'
NOME_VR_VIB = 'VR_VIB.xlsx'

# riga oltre la quale write_docx_Rumore.py smette di definire funzioni e comincia
# a scrivere il documento: e' li' che si taglia il sorgente
SENTINELLA_RUMORE = '# SEZIONE 3 - COSTRUZIONE DEI CONTEXT AUTOMATICI'

NOME_DOCUMENTO = {'rumore': 'Relazione_RUM.docx', 'vibrazioni': 'Relazione_VIB.docx'}


# ---------------------------------------------------------------------------
# Caricamento dei due write_docx
# ---------------------------------------------------------------------------

def carica_testa(percorso, sentinella, nome):
    """
    Esegue un sorgente fino a una sentinella, come fosse un modulo.

    Serve per i file che, oltre alle funzioni, contengono anche il codice che
    le usa: si prende la parte di definizioni e si lascia fuori il resto.

    INPUT:  percorso   - file .py da caricare
            sentinella - testo che segna la fine della parte da eseguire
            nome       - nome da dare al modulo
    OUTPUT: il modulo con le sole definizioni
    """
    if not os.path.isfile(percorso):
        raise FileNotFoundError(f'Script del backend non trovato: {percorso}')
    with open(percorso, encoding='utf-8') as f:
        sorgente = f.read()

    taglio = sorgente.find(sentinella)
    if taglio < 0:
        raise RuntimeError(
            f'Sentinella "{sentinella}" non trovata in {percorso}: il file e\' '
            f'cambiato e il caricamento parziale non e\' piu\' sicuro.')

    modulo = types.ModuleType(nome)
    modulo.__file__ = percorso
    sys.modules[nome] = modulo
    exec(compile(sorgente[:taglio], percorso, 'exec'), modulo.__dict__)
    return modulo


def _sovrascrivi(modulo, valori):
    """Sostituisce i globali del backend, saltando quelli non valorizzati."""
    for nome, valore in valori.items():
        if valore is not None:
            setattr(modulo, nome, valore)


def _contesto_utente(cfg, ramo):
    """
    Campi del modulo 'Dati generali' pronti per docxtpl.

    I valori mancanti prendono il default di relazione/contesto.py, cosi' un
    preset vecchio o parziale non lascia buchi nel documento.
    """
    campi = dict(modulo_contesto.campi_vuoti(modulo_contesto.blocchi_di(ramo)))
    campi.update(cfg.get('campi', {}) or {})

    # i modelli inseriscono le date dei rilievi a meta' frase: serve una
    # stringa, non la lista che l'interfaccia raccoglie
    date = campi.get('date_misurazione', '')
    if isinstance(date, (list, tuple)):
        date = ', '.join(str(d) for d in date if str(d).strip())
    campi['date_misurazione'] = date

    # le chiavi di controllo pilotano la scrittura, nel documento non servono
    for chiave in modulo_contesto.CHIAVI_CONTROLLO:
        campi.pop(chiave, None)
    return campi


def _percorsi_documento(cfg, ramo):
    """OUTPUT: (template, frontespizio, logo, uscita), tutti assoluti."""
    template = cfg.get('template', '')
    if not template or not os.path.isfile(template):
        raise FileNotFoundError(f'Modello .docx non trovato: {template or "(non impostato)"}')

    frontespizio = cfg.get('frontespizio', '')
    if not frontespizio or not os.path.isfile(frontespizio):
        raise FileNotFoundError(
            f'Frontespizio non trovato: {frontespizio or "(non impostato)"}')

    uscita = cfg.get('uscita', '')
    if not uscita:
        uscita = os.path.join(cfg.get('output', ''), NOME_DOCUMENTO[ramo])
    os.makedirs(os.path.dirname(uscita), exist_ok=True)
    return template, frontespizio, cfg.get('logo', ''), uscita


# ---------------------------------------------------------------------------
# Ramo rumore
# ---------------------------------------------------------------------------

def passi_rumore(cfg, stato):
    """Passi della scrittura della relazione rumore. OUTPUT: lista (chiave, nome, funzione)."""
    from docxtpl import DocxTemplate

    cartella_vrr = cfg['percorso_vrr']
    sys.path.insert(0, cartella_vrr)
    scheda = cfg.get('scheda', '')
    riepilogo = os.path.join(cfg.get('output', ''), NOME_VR8H_RIEPILOGO)
    campi = cfg.get('campi', {}) or {}
    template, frontespizio, logo, uscita = _percorsi_documento(cfg, 'rumore')

    backend = carica_testa(
        os.path.join(cartella_vrr, 'utility', 'write_docx_Rumore.py'),
        SENTINELLA_RUMORE, '_write_docx_rumore')

    _sovrascrivi(backend, {
        'MAIN_DIRECTORY': cfg.get('main', ''),
        'OUTPUT_DIRECTORY': cfg.get('output', ''),
        'FILE_SCHEDA_GRUPPI_DPI': scheda,
        'FILE_VR8H_RIEPILOGO': riepilogo,
        'DOCUMENTO_WORD_TEMPLATE': template,
        'DIR_FRONTESPIZI': os.path.dirname(frontespizio),
        'FRONTESPIZIO': os.path.basename(frontespizio),
        'LOGO_AZIENDA': logo,
        'OUTPUT_DOCUMENT': uscita,
        'ORARI_UGUALI_PER_TUTTI': bool(campi.get('orari_uguali_per_tutti', True)),
        'ORARIO_LAVORO_DEFAULT': campi.get('orario_lavoro_default')
                                 or backend.ORARIO_LAVORO_DEFAULT,
        'OTOTOSSICI_DEFAULT': campi.get('ototossici_default') or 'NO',
        'IMPULSIVI_DEFAULT': campi.get('impulsivi_default') or 'NO',
    })

    def lettura():
        if not scheda or not os.path.isfile(scheda):
            raise FileNotFoundError(
                'scheda_gruppi_dpi.xlsx non trovata: indicala dalla schermata '
                'Cartella di lavoro.')
        if not os.path.isfile(riepilogo):
            raise FileNotFoundError(
                f'{NOME_VR8H_RIEPILOGO} non trovato in {cfg.get("output", "")}: '
                f'esegui prima l\'analisi del rumore.')

        stato['doc'] = DocxTemplate(template)
        df_mansioni = backend.leggi_scheda_mansioni(scheda)
        stato['mansioni'] = backend.carica_mansioni(df_mansioni)
        stato['righe_heg'] = backend.carica_riepilogo_heg(
            riepilogo, backend.carica_vibrazioni(df_mansioni))
        stato['dpi'] = backend.carica_dpi(scheda)
        log(f'Gruppi omogenei: {len(stato["righe_heg"])}, '
            f'mansioni: {len(stato["mansioni"])}, DPI: {len(stato["dpi"])}')
        return True

    def contesto():
        righe_heg = stato['righe_heg']
        # base_giornaliera, base_settimanale ed esposizioni_variabili - la
        # tabella "Metodo adottato" - sono gia' campi del modulo
        stato['contesto'] = dict(_contesto_utente(cfg, 'rumore'))
        stato['contesto'].update({
            'tabella_dpi': stato['dpi'],
            'tabella_orario_lavoro_mansione': backend.carica_orari(stato['mansioni']),
            'tabella_mansioni': stato['mansioni'],
            'tabella_HEG': righe_heg,
            'HEG_med': backend.filtra_per_classe(righe_heg, 'MEDIA'),
            'HEG_alto': backend.filtra_per_classe(righe_heg, 'ALTA'),
        })
        log(f'Classe MEDIA: {len(stato["contesto"]["HEG_med"])}, '
            f'classe ALTA: {len(stato["contesto"]["HEG_alto"])}')
        return True

    def decorazioni():
        stato['contesto']['frontespizio'] = backend.costruisci_frontespizio(
            stato['doc'], frontespizio, stato['contesto'])
        stato['contesto']['img_logo_azienda'] = backend.logo_inline(stato['doc'])
        return True

    def scrittura():
        stato['doc'].render(stato['contesto'])
        stato['doc'].save(uscita)
        stato['uscita'] = uscita
        log(f'Docx scritto: {uscita}')
        return True

    return _abbina('rumore', {'lettura': lettura, 'contesto': contesto,
                              'frontespizio': decorazioni, 'scrittura': scrittura})


# ---------------------------------------------------------------------------
# Ramo vibrazioni
# ---------------------------------------------------------------------------

def passi_vibrazioni(cfg, stato):
    """Passi della scrittura della relazione vibrazioni."""
    from docxtpl import DocxTemplate

    cartella_vrv = cfg['percorso_vrv']
    sys.path.insert(0, cartella_vrv)
    file_input = cfg.get('file', {}) or {}
    cartella_output = cfg.get('output', '')
    campi = cfg.get('campi', {}) or {}
    template, frontespizio, logo, uscita = _percorsi_documento(cfg, 'vibrazioni')

    backend = carica_modulo(os.path.join(cartella_vrv, 'utility'), 'write_docx_vib')

    _sovrascrivi(backend, {
        'MAIN_DIRECTORY': cfg.get('main', ''),
        'MISURE_DIRECTORY': cfg.get('misure', ''),
        'OUTPUT_DIRECTORY': cartella_output,
        'FILE_MISURE_HAV': file_input.get('misureHAV', ''),
        'FILE_MISURE_WBV': file_input.get('misureWBV', ''),
        'FILE_DATI_COSTR': file_input.get('datiCostr', ''),
        'FILE_SCHEDA_GRUPPI': cfg.get('scheda', ''),
        'FILE_MISURE_VIB': os.path.join(cartella_output, NOME_MISURE_VIB),
        'FILE_VR_VIB': os.path.join(cartella_output, NOME_VR_VIB),
        'DIR_FOTO': os.path.join(cfg.get('main', ''), 'fotocomp'),
        'DOCUMENTO_WORD_TEMPLATE': template,
        'DIR_FRONTESPIZI': os.path.dirname(frontespizio),
        'FRONTESPIZIO': os.path.basename(frontespizio),
        'LOGO_AZIENDA': logo,
        'OUTPUT_DOCUMENT': uscita,
        # i parametri di calcolo arrivano dall'interfaccia, non da parameters.py
        'par': parametri_backend(getattr(backend, 'par', None),
                                 cfg.get('parametri', {})),
    })

    def lettura():
        stato['doc'] = DocxTemplate(template)
        stato['tabelle'] = backend.leggi_VR_VIB()
        stato['mansioni'] = backend.carica_mansioni()
        stato['banche'] = backend.carica_banche()
        stato['metodo'] = backend.carica_metodo()
        stato['foto'] = backend.carica_foto(stato['doc'])
        log(f'Gruppi HAV/WBV: {len(stato["tabelle"]["HAV"])}/'
            f'{len(stato["tabelle"]["WBV"])}, mansioni esposte: '
            f'{len(stato["mansioni"])}, righe foto: {len(stato["foto"])}')
        return True

    def contesto():
        tabelle = stato['tabelle']
        classe_media = backend.config.CLASSE_MEDIA
        hav_medio = backend.filtra_per_classe(tabelle['HAV'], classe_media)
        wbv_medio = backend.filtra_per_classe(tabelle['WBV'], classe_media)

        stato['contesto'] = dict(_contesto_utente(cfg, 'vibrazioni'))
        stato['contesto'].update(stato['metodo'])
        stato['contesto'].update({
            'img_misure': stato['foto'],
            'tabella_mansioni': stato['mansioni'],
            'banche': stato['banche'],
            'tabella_hav': tabelle['HAV'],
            'tabella_wbv': tabelle['WBV'],
            'superamento': backend.carica_superamento(tabelle),
            # nel capitolo 16 compaiono i soli gruppi in classe media: senza,
            # titolo e tabella vengono tolti dal documento
            'hav_superato': bool(hav_medio),
            'titolo_hav_superamento': backend.TITOLO_HAV_SUPERAMENTO,
            'hav_medio': hav_medio,
            'wbv_superato': bool(wbv_medio),
            'titolo_wbv_superamento': backend.TITOLO_WBV_SUPERAMENTO,
            'wbv_medio': wbv_medio,
        })
        log(f'Classe media HAV/WBV: {len(hav_medio)}/{len(wbv_medio)}')
        return True

    def decorazioni():
        stato['contesto']['frontespizio'] = backend.costruisci_frontespizio(
            stato['doc'], frontespizio, stato['contesto'])
        stato['contesto']['img_logo_azienda'] = backend.logo_inline(stato['doc'])
        return True

    def scrittura():
        stato['doc'].render(stato['contesto'])
        stato['doc'].save(uscita)
        stato['uscita'] = uscita
        log(f'Docx scritto: {uscita}')
        return True

    return _abbina('vibrazioni', {'lettura': lettura, 'contesto': contesto,
                                  'frontespizio': decorazioni, 'scrittura': scrittura})


# ---------------------------------------------------------------------------

def _abbina(ramo, funzioni):
    """Elenco dei passi nell'ordine di passi.py, con le chiavi prefissate dal ramo."""
    return [(f'{ramo}.relazione.{chiave}', nome, funzioni[chiave])
            for chiave, nome in elenco_passi.PASSI_RELAZIONE]


def esegui(cfg, offset=0, totale=None):
    """Scrive la relazione di un ramo. OUTPUT: (ok, percorso del documento)."""
    ramo = cfg.get('ramo', 'rumore')
    if ramo not in ('rumore', 'vibrazioni'):
        raise ValueError(f'Ramo sconosciuto: {ramo}')

    stato = {}
    passi = (passi_rumore(cfg, stato) if ramo == 'rumore'
             else passi_vibrazioni(cfg, stato))
    sequenza = Sequenza(ramo, passi, offset=offset,
                        totale=totale if totale is not None else len(passi))
    if offset == 0:
        sequenza.annuncia()
    return sequenza.esegui(), stato.get('uscita', '')


def main():
    cfg = protocollo.leggi_configurazione()
    protocollo.cattura_stampe()
    inizio = time.time()
    uscita = ''
    try:
        ok, uscita = esegui(cfg, offset=int(cfg.get('offset', 0) or 0),
                            totale=cfg.get('totale'))
    except Exception as errore:
        log(f'{type(errore).__name__}: {errore}', 'error')
        ok = False
    emetti({'tipo': 'fine', 'ok': ok, 'documento': uscita,
            'durata': round(time.time() - inizio, 1)})
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
