#! /usr/bin/env python3
"""
Prova end-to-end: avvia una valutazione dall'interfaccia e ne segue gli eventi.

Verifica la catena completa - pagina, ponte, gestore di esecuzione, runner,
backend - e riporta lo stato finale dei passi e le righe di log raccolte.

USO: python strumenti/prova_esecuzione.py <cartella> [modalita]
"""

import json
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CARTELLA_PROGETTO)

from PyQt5.QtCore import QTimer                                 # noqa: E402
from PyQt5.QtWidgets import QApplication                        # noqa: E402

import app as applicazione                                      # noqa: E402
from core import configurazione                                 # noqa: E402

ATTESA_MASSIMA = 300     # secondi


def main():
    radice = sys.argv[1] if len(sys.argv) > 1 else ''
    modalita = sys.argv[2] if len(sys.argv) > 2 else 'combinato'

    cfg = configurazione.config()
    cfg['ultima_root'] = radice
    configurazione.scrivi(configurazione.CONFIG, cfg)

    qapp = QApplication(sys.argv[:1])
    finestra = applicazione.Finestra()
    finestra.show()
    pagina = finestra.vista.page()

    esiti = {}
    trascorsi = {'s': 0}

    def avvia():
        pagina.runJavaScript(f'S.modalita = "{modalita}"; avvia(false);')
        QTimer.singleShot(2000, controlla)

    def controlla():
        trascorsi['s'] += 2
        pagina.runJavaScript(
            'JSON.stringify({corso: S.esecuzione.inCorso,'
            ' passi: S.esecuzione.passi.map(p => [p.nome, p.stato]),'
            ' righe: S.esecuzione.righe.length,'
            ' errori: S.esecuzione.righe.filter(r => r.livello === "error").length,'
            ' avvisi: S.esecuzione.righe.filter(r => r.livello === "warning").length,'
            ' durata: S.esecuzione.durata,'
            ' gruppiRumore: S.risultatiRumore ? S.risultatiRumore.gruppi.length : -1,'
            ' gruppiVib: S.risultatiVibrazioni ? S.risultatiVibrazioni.gruppi.length : -1})',
            ricevi)

    def ricevi(grezzo):
        if not grezzo:
            QTimer.singleShot(2000, controlla)
            return
        stato = json.loads(grezzo)
        esiti['stato'] = stato
        if stato['corso'] and trascorsi['s'] < ATTESA_MASSIMA:
            fatti = sum(1 for _, s in stato['passi'] if s in ('fatto', 'saltato'))
            print(f"  … {trascorsi['s']:>3}s  {fatti}/{len(stato['passi'])} passi, "
                  f"{stato['righe']} righe di log", flush=True)
            QTimer.singleShot(2000, controlla)
            return
        concludi()

    def concludi():
        stato = esiti.get('stato', {})
        print()
        for nome, esito in stato.get('passi', []):
            print(f'  {esito:8} {nome}')
        print(f"\ndurata          : {stato.get('durata')} s")
        print(f"righe di log    : {stato.get('righe')}  "
              f"(avvisi {stato.get('avvisi')}, errori {stato.get('errori')})")
        print(f"gruppi rumore   : {stato.get('gruppiRumore')}   "
              f"vibrazioni: {stato.get('gruppiVib')}")
        qapp.quit()

    QTimer.singleShot(7000, avvia)
    QTimer.singleShot((ATTESA_MASSIMA + 30) * 1000, qapp.quit)
    qapp.exec_()

    stato = esiti.get('stato', {})
    falliti = [n for n, e in stato.get('passi', []) if e not in ('fatto', 'saltato')]
    if falliti:
        print('\nPASSI NON COMPLETATI: ' + ', '.join(falliti))
        return 1
    print('\nEsecuzione completata.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
