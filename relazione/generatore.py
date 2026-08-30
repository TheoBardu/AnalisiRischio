#! /usr/bin/env python3
"""
Generazione della relazione .docx.

PUNTO DI ESTENSIONE. L'interfaccia e' gia' completa: raccoglie i dati generali,
precompila le tabelle DPI, gruppi omogenei e vibrazioni dai risultati
dell'analisi, e salva o ricarica i preset. Quello che manca e' soltanto la
scrittura del documento, che va implementata qui dentro.

Per aggiungerla basta sostituire il corpo di genera() con il codice che
compila il modello. L'ambiente ha gia' docxtpl e python-docx, e in
VRR/utility/write_docx.py c'e' l'esempio di riferimento:

    from docxtpl import DocxTemplate
    def genera(contesto, template, output):
        documento = DocxTemplate(template)
        documento.render(contesto)
        documento.save(output)
        return output

Il contesto arriva gia' pronto da relazione/contesto.py: campi singoli come
nome_azienda o data_revisione, e le liste tabella_dpi, tabella_HEG e
tabella_vibrazioni per i cicli del modello.
"""

import os

DISPONIBILE = False

MESSAGGIO_NON_IMPLEMENTATO = (
    'La generazione del documento non e\' ancora attiva: i dati sono pronti e '
    'salvati, manca solo il codice di scrittura in relazione/generatore.py.')


def genera(contesto, template, output):
    """
    Scrive la relazione a partire dal modello.

    INPUT:  contesto - dizionario prodotto da relazione.contesto.costruisci()
            template - percorso del modello .docx
            output   - percorso del documento da scrivere
    OUTPUT: percorso del documento scritto
    """
    raise NotImplementedError(MESSAGGIO_NON_IMPLEMENTATO)


def stato(template, output):
    """
    Descrive se e cosa si puo' generare, per il messaggio dell'interfaccia.

    OUTPUT: {'disponibile', 'messaggio', 'template_presente'}
    """
    template_presente = bool(template) and os.path.exists(template)
    if not DISPONIBILE:
        messaggio = MESSAGGIO_NON_IMPLEMENTATO
    elif not template_presente:
        messaggio = f'Modello non trovato: {template}'
    else:
        messaggio = f'Pronto a scrivere {os.path.basename(output or "")}'
    return {'disponibile': DISPONIBILE and template_presente,
            'messaggio': messaggio,
            'template_presente': template_presente}
