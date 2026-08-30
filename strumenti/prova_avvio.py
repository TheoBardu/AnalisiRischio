#! /usr/bin/env python3
"""
Prova di avvio dell'interfaccia senza intervento manuale.

Apre la finestra, aspetta che la pagina sia pronta, poi interroga lo stato
JavaScript per verificare che il ponte funzioni, che la cartella sia stata
riconosciuta e che le schermate si disegnino senza errori.

USO: python strumenti/prova_avvio.py <cartella_di_prova>
"""

import json
import os
import sys

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

CARTELLA_PROGETTO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CARTELLA_PROGETTO)

from PyQt5.QtCore import QTimer                                  # noqa: E402
from PyQt5.QtWidgets import QApplication                         # noqa: E402

import app as applicazione                                       # noqa: E402
from core import configurazione                                  # noqa: E402

SCHERMATE = ['cartelle', 'schede', 'log', 'superamenti', 'misure',
             'attrezzature', 'esposizioni', 'relazione']


def main():
    radice = sys.argv[1] if len(sys.argv) > 1 else ''
    cfg = configurazione.config()
    cfg['ultima_root'] = radice
    configurazione.scrivi(configurazione.CONFIG, cfg)

    qapp = QApplication(sys.argv[:1])
    finestra = applicazione.Finestra()
    finestra.show()

    errori = []
    esiti = {}

    def raccogli(nome):
        def callback(valore):
            esiti[nome] = valore
        return callback

    def interroga():
        """Percorre le schermate come farebbe l'utente, con vai()."""
        codice = """
        (async function () {
          window.__esito = null;
          const esito = { ponte: !!ponte, modalita: S.modalita,
                          root: S.root, valida: !!(S.scansione && S.scansione.valida),
                          schermate: {}, errori: [] };
          for (const nome of %s) {
            try {
              await vai(nome);
              esito.schermate[nome] = document.getElementById('main').innerHTML.length;
            } catch (e) { esito.errori.push(nome + ': ' + e.message); }
          }
          esito.voci = vociVisibili().map(v => v[0]);
          esito.gruppiRumore = S.risultatiRumore ? S.risultatiRumore.gruppi.length : -1;
          esito.gruppiVib = S.risultatiVibrazioni ? S.risultatiVibrazioni.gruppi.length : -1;
          esito.schede = S.schede ? S.schede.mansioni.righe.length : -1;
          esito.attrezzature = S.attrezzature ? Object.keys(S.attrezzature).length : -1;
          window.__esito = JSON.stringify(esito);
        })()
        """ % json.dumps(SCHERMATE)
        finestra.vista.page().runJavaScript(codice)
        QTimer.singleShot(4000, raccogli_esito)

    def raccogli_esito():
        finestra.vista.page().runJavaScript(
            'window.__esito', raccogli('stato'))
        QTimer.singleShot(1200, concludi)

    def concludi():
        grezzo = esiti.get('stato')
        if not grezzo:
            errori.append('nessuna risposta da JavaScript')
        else:
            dati = json.loads(grezzo)
            print(f"ponte attivo   : {dati['ponte']}")
            print(f"root           : {dati['root']}")
            print(f"cartella valida: {dati['valida']}   modalita': {dati['modalita']}")
            print(f"voci sidebar   : {', '.join(dati['voci'])}")
            print(f"gruppi rumore  : {dati['gruppiRumore']}   vibrazioni: {dati['gruppiVib']}"
                  f"   righe mansioni: {dati['schede']}")
            print('schermate disegnate (byte di html):')
            for nome, lunghezza in dati['schermate'].items():
                stato = 'ok  ' if lunghezza > 200 else 'VUOTA'
                print(f'   {stato} {nome:14} {lunghezza}')
                if lunghezza <= 200:
                    errori.append(f'schermata vuota: {nome}')
            for e in dati['errori']:
                errori.append(f'errore di rendering {e}')
        qapp.quit()

    # il caricamento della pagina e la scansione iniziale sono asincroni
    QTimer.singleShot(6000, interroga)
    QTimer.singleShot(20000, qapp.quit)
    qapp.exec_()

    if errori:
        print('\nPROBLEMI:')
        for e in errori:
            print('  -', e)
        return 1
    print('\nAvvio riuscito.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
