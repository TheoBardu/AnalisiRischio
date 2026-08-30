#! /usr/bin/env python3
"""
Elenco dei passi delle due pipeline.

Sta qui, e non dentro i runner, perche' serve a entrambe le parti: i runner lo
usano per dare un nome ai passi che eseguono, l'interfaccia per disegnare la
lista di avanzamento prima ancora che il processo parta.
"""

PASSI_RUMORE = [
    ('pulizia', 'Pulizia risultati precedenti'),
    ('lettura_misure', 'Lettura misure fonometriche'),
    ('medie', 'Calcolo delle medie'),
    ('scheda_info', 'Lettura scheda gruppi e DPI'),
    ('analisi_8h', 'Analisi Lex,8h'),
    ('dpi', 'Applicazione DPI (HML)'),
    ('rilievi', 'Creazione Rilievi Fonometrici'),
    ('pdf', 'Export PDF'),
]

PASSI_VIBRAZIONI = [
    ('preparazione', 'Preparazione cartella di output'),
    ('lettura', 'Lettura misure e scheda gruppi'),
    ('calcolo_hav', 'Calcolo misure HAV'),
    ('calcolo_wbv', 'Calcolo misure WBV'),
    ('scrittura_misure', 'Scrittura misureVIB.xlsx'),
    ('schede', 'Calcolo A(8) e schede gruppi'),
    ('pdf', 'Export PDF degli allegati'),
]

PER_PIPELINE = {'rumore': PASSI_RUMORE, 'vibrazioni': PASSI_VIBRAZIONI}


def passi_di(modalita):
    """
    Passi complessivi di una modalita', con il prefisso della pipeline.

    OUTPUT: lista di dict {chiave, nome, pipeline}; le chiavi sono rese uniche
            con il prefisso della pipeline, perche' in modalita' combinata
            entrambe hanno un passo 'pdf'.
    """
    pipeline = (['rumore', 'vibrazioni'] if modalita == 'combinato'
                else [modalita])
    elenco = []
    for nome_pipeline in pipeline:
        for chiave, nome in PER_PIPELINE.get(nome_pipeline, []):
            elenco.append({'chiave': f'{nome_pipeline}.{chiave}',
                           'nome': nome, 'pipeline': nome_pipeline})
    return elenco
