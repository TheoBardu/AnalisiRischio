#! /usr/bin/env python3
"""
AnalisiRischio - interfaccia unica per la valutazione del rischio rumore e
vibrazioni.

Programma standalone: si apre, si sceglie la cartella dell'azienda, si
controllano e si correggono i dati, si esegue la valutazione. VRR_analisiDati e
VRV_analisiDati fanno da backend e non vengono modificati.

La finestra e' una QWebEngineView che carica web/index.html; il dialogo fra
pagina e Python passa da QWebChannel, con un unico oggetto 'ponte' che espone
una chiamata sincrona per le operazioni e un segnale per gli eventi
dell'analisi.

USO: python app.py [cartella_azienda]
"""

import json
import os
import sys
import traceback

from PyQt5.QtCore import (QEvent, QFile, QIODevice, QObject, QRect, Qt, QUrl,
                          pyqtSignal, pyqtSlot)
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import (QWebEnginePage, QWebEngineProfile,
                                      QWebEngineScript, QWebEngineSettings,
                                      QWebEngineView)
from PyQt5.QtWidgets import QApplication, QFileDialog, QMainWindow

CARTELLA_PROGETTO = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, CARTELLA_PROGETTO)

from core import (configurazione, esecuzione, input_vibrazioni, progetto,
                  risultati_rumore, risultati_vibrazioni, schede)
from relazione import contesto as contesto_relazione
from relazione import generatore
from runner import passi as elenco_passi

LARGHEZZA = 1240
ALTEZZA = 754        # 38 della barra + 716 della shell, come nel mockup
LARGHEZZA_MINIMA = 900
ALTEZZA_MINIMA = 560

# margine fra i pallini di macOS e il testo della barra
MARGINE_PALLINI = 14


class Pagina(QWebEnginePage):
    """Pagina che inoltra i messaggi della console al terminale."""

    def javaScriptConsoleMessage(self, livello, messaggio, riga, sorgente):
        if livello >= QWebEnginePage.WarningMessageLevel:
            print(f'[web:{riga}] {messaggio}', file=sys.stderr)


class Ponte(QObject):
    """
    Oggetto esposto alla pagina come 'ponte'.

    chiama(azione, payload) copre tutte le operazioni sincrone; gli eventi
    dell'analisi, che arrivano da un altro thread, viaggiano sul segnale
    evento.
    """

    evento = pyqtSignal(str)

    def __init__(self, finestra):
        super().__init__()
        self.finestra = finestra
        self.esecuzione = esecuzione.Esecuzione(self._inoltra_evento)
        self.scansione = {}

    # ------------------------------------------------------------------
    def _inoltra_evento(self, evento):
        """Callback dell'esecuzione: serializza e spedisce alla pagina."""
        try:
            self.evento.emit(json.dumps(evento, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            pass

    # ------------------------------------------------------------------
    def annuncia_finestra(self, misure):
        """Comunica alla pagina le misure della barra del titolo."""
        self._inoltra_evento(dict(misure, tipo='finestra'))

    # ------------------------------------------------------------------
    @pyqtSlot(str, str, result=str)
    def chiama(self, azione, payload):
        """
        Punto d'ingresso unico delle chiamate dalla pagina.

        INPUT:  azione  - nome dell'operazione
                payload - argomenti in JSON
        OUTPUT: JSON con l'esito, oppure {'errore': ...}
        """
        try:
            dati = json.loads(payload) if payload else {}
        except json.JSONDecodeError:
            dati = {}
        metodo = getattr(self, f'_azione_{azione}', None)
        if metodo is None:
            return json.dumps({'errore': f'Azione sconosciuta: {azione}'})
        try:
            risultato = metodo(dati)
        except Exception as errore:
            traceback.print_exc()
            risultato = {'errore': f'{type(errore).__name__}: {errore}'}
        return json.dumps(risultato, ensure_ascii=False, default=str)

    # ---- finestra ----------------------------------------------------
    # Chiusura, riduzione, ingrandimento, trascinamento e ridimensionamento
    # sono tutti gestiti da macOS: la finestra e' nativa e ha i suoi pulsanti.
    # Alla pagina servono solo le misure della barra del titolo, per lasciare
    # spazio ai pallini e per dimensionare la propria fascia scura.

    # ---- stato e configurazione --------------------------------------
    def _azione_stato_iniziale(self, _):
        cfg = configurazione.config()
        return {
            'config': cfg,
            'parametri_rumore': configurazione.parametri_rumore(),
            'parametri_vibrazioni': configurazione.parametri_vibrazioni(),
            'recenti': configurazione.progetti_recenti(),
            'cartella_config': configurazione.cartella_config(),
            'finestra': self.finestra.misure_barra,
            'preset_relazione': configurazione.preset_relazione(),
            'relazione': generatore.stato(
                configurazione.percorso_modello('modello_relazione_rumore'), ''),
            'campi_relazione': contesto_relazione.CAMPI_GENERALI,
            'layout_relazione': contesto_relazione.LAYOUT_GENERALI,
            'passi': {m: elenco_passi.passi_di(m)
                      for m in ('rumore', 'vibrazioni', 'combinato')},
        }

    def _azione_salva_parametri(self, dati):
        if 'rumore' in dati:
            configurazione.scrivi(configurazione.PARAMETRI_RUMORE, dati['rumore'])
        if 'vibrazioni' in dati:
            configurazione.scrivi(configurazione.PARAMETRI_VIBRAZIONI,
                                  dati['vibrazioni'])
        if 'config' in dati:
            cfg = configurazione.config()
            cfg.update(dati['config'])
            configurazione.scrivi(configurazione.CONFIG, cfg)
        return {'ok': True}

    # ---- cartella di lavoro ------------------------------------------
    def _azione_scansiona(self, dati):
        root = dati.get('root', '')
        self.scansione = progetto.scansiona(root)
        if self.scansione.get('valida'):
            configurazione.aggiungi_progetto_recente(self.scansione['root'])
            cfg = configurazione.config()
            cfg['ultima_root'] = self.scansione['root']
            configurazione.scrivi(configurazione.CONFIG, cfg)
        return self.scansione

    def _azione_sfoglia_cartelle(self, dati):
        return progetto.elenco_cartelle(dati.get('percorso', ''))

    def _azione_sfoglia_file(self, dati):
        return progetto.elenco_file(dati.get('percorso', ''),
                                    tuple(dati.get('estensioni', ['.xlsx'])))

    def _azione_dialogo_cartella(self, dati):
        """Selettore nativo, come alternativa a quello interno."""
        cartella = QFileDialog.getExistingDirectory(
            self.finestra, 'Seleziona la cartella dell\'azienda',
            dati.get('percorso', '') or os.path.expanduser('~'))
        return {'percorso': cartella}

    def _azione_dialogo_file(self, dati):
        percorso, _ = QFileDialog.getOpenFileName(
            self.finestra, 'Seleziona il file',
            dati.get('percorso', '') or os.path.expanduser('~'),
            'Fogli di calcolo (*.xlsx *.xls)')
        return {'percorso': percorso}

    def _azione_imposta_file(self, dati):
        """Sovrascrive un percorso riconosciuto dalla scansione."""
        chiave = dati.get('chiave', '')
        percorso = dati.get('percorso', '')
        if chiave == 'scheda':
            self.scansione['scheda'] = percorso
            for ramo in ('rumore', 'vibrazioni'):
                if self.scansione.get(ramo, {}).get('presente'):
                    self.scansione[ramo]['scheda'] = percorso
        elif chiave in ('misureHAV', 'misureWBV', 'datiCostr'):
            if self.scansione.get('vibrazioni', {}).get('presente'):
                self.scansione['vibrazioni']['file'][chiave] = percorso
        return self.scansione

    # ---- schede gruppi e DPI -----------------------------------------
    def _azione_leggi_schede(self, dati):
        percorso = dati.get('percorso') or self.scansione.get('scheda', '')
        risultato = schede.leggi(percorso)
        t0 = float(dati.get('t0') or configurazione.parametri_rumore().get('T0', 480))
        risultato['tempi'] = schede.verifica_tempi(
            risultato['mansioni']['righe'], risultato['mansioni']['colonne'], t0)
        return risultato

    def _azione_salva_schede(self, dati):
        percorso = dati.get('percorso') or self.scansione.get('scheda', '')
        return schede.salva(percorso, dati.get('dpi', []), dati.get('mansioni', []),
                            dati.get('colonne_dpi'), dati.get('colonne_mansioni'))

    # ---- risultati rumore --------------------------------------------
    def _azione_risultati_rumore(self, dati):
        ramo = self.scansione.get('rumore', {})
        if not ramo.get('presente'):
            return {'disponibile': False, 'gruppi': [], 'conteggi': {}}
        par = configurazione.parametri_rumore()
        par.update(dati.get('parametri', {}))
        return risultati_rumore.sintesi(
            ramo.get('vr8h_riepilogo', ''), ramo.get('vr8h_totale', ''),
            t0=float(par.get('T0', 480)), limite=float(par.get('LIMITE_LEX8H', 87)),
            soglia_media=float(par.get('SOGLIA_MEDIA', 80)),
            soglia_alta=float(par.get('SOGLIA_ALTA', 85)))

    def _azione_misure_singole(self, dati):
        ramo = self.scansione.get('rumore', {})
        risultato = risultati_rumore.misure_singole(ramo.get('vr8h_totale', ''))
        risultato['medie'] = risultati_rumore.leggi_medie(
            os.path.join(ramo.get('misure', ''), 'data'))
        return risultato

    def _azione_salva_medie(self, dati):
        ramo = self.scansione.get('rumore', {})
        return risultati_rumore.salva_medie(
            os.path.join(ramo.get('misure', ''), 'data'), dati.get('righe', []))

    # ---- vibrazioni ---------------------------------------------------
    def _azione_risultati_vibrazioni(self, _):
        ramo = self.scansione.get('vibrazioni', {})
        if not ramo.get('presente'):
            return {'disponibile': False, 'gruppi': [], 'conteggi': {}}
        return risultati_vibrazioni.sintesi(
            ramo.get('output', ''), ramo.get('vr_vib', ''),
            configurazione.parametri_vibrazioni())

    def _azione_leggi_attrezzature(self, _):
        ramo = self.scansione.get('vibrazioni', {})
        file_input = ramo.get('file', {})
        return {
            'costruttori': input_vibrazioni.leggi_dati_costruttori(
                file_input.get('datiCostr', '')),
            'HAV': input_vibrazioni.leggi_misure(file_input.get('misureHAV', ''), 'HAV'),
            'WBV': input_vibrazioni.leggi_misure(file_input.get('misureWBV', ''), 'WBV'),
        }

    def _azione_salva_attrezzature(self, dati):
        ramo = self.scansione.get('vibrazioni', {})
        file_input = ramo.get('file', {})
        quale = dati.get('quale', '')
        righe = dati.get('righe', [])
        if quale == 'costruttori':
            return input_vibrazioni.salva_dati_costruttori(
                file_input.get('datiCostr', ''), righe)
        if quale in ('HAV', 'WBV'):
            return input_vibrazioni.salva_misure(
                file_input.get(f'misure{quale}', ''), quale, righe)
        return {'ok': False, 'errore': f'Tabella sconosciuta: {quale}'}

    # ---- esecuzione ---------------------------------------------------
    def _configurazioni_runner(self, modalita, opzioni):
        """Costruisce le configurazioni dei runner dalla scansione corrente."""
        cfg = configurazione.config()
        configurazioni = {}
        if modalita in ('rumore', 'combinato'):
            ramo = self.scansione.get('rumore', {})
            configurazioni['rumore'] = {
                'percorso_vrr': cfg['percorso_vrr'],
                'main': ramo.get('main', ''), 'misure': ramo.get('misure', ''),
                'output': ramo.get('output', ''),
                'scheda': self.scansione.get('scheda', ''),
                'rileggi_misure': bool(opzioni.get('rileggi_misure', False)),
                'parametri': configurazione.parametri_rumore(),
            }
        if modalita in ('vibrazioni', 'combinato'):
            ramo = self.scansione.get('vibrazioni', {})
            configurazioni['vibrazioni'] = {
                'percorso_vrv': cfg['percorso_vrv'],
                'main': ramo.get('main', ''), 'misure': ramo.get('misure', ''),
                'output': ramo.get('output', ''),
                'file': ramo.get('file', {}),
                'scheda': self.scansione.get('scheda', ''),
                'parametri': configurazione.parametri_vibrazioni(),
            }
        return configurazioni

    def _azione_avvia(self, dati):
        modalita = dati.get('modalita', 'rumore')
        if not self.scansione.get('valida'):
            return {'ok': False, 'errore': 'Seleziona prima una cartella di lavoro valida.'}

        # i Ti fuori da T0 fanno fallire analisi_8h: meglio dirlo qui
        if modalita in ('rumore', 'combinato') and not dati.get('ignora_tempi'):
            lettura = schede.leggi(self.scansione.get('scheda', ''))
            t0 = float(configurazione.parametri_rumore().get('T0', 480))
            tempi = schede.verifica_tempi(lettura['mansioni']['righe'],
                                          lettura['mansioni']['colonne'], t0)
            if tempi['sforati']:
                return {'ok': False, 'tempi': tempi,
                        'errore': f'{len(tempi["sforati"])} gruppi omogenei hanno '
                                  f'somma dei Ti diversa da T0 ({t0:g} min): '
                                  f'l\'analisi Lex,8h si fermerebbe con un errore.'}

        return self.esecuzione.avvia(modalita,
                                     self._configurazioni_runner(modalita, dati))

    def _azione_interrompi(self, _):
        return {'ok': self.esecuzione.interrompi()}

    # ---- relazione ----------------------------------------------------
    def _azione_relazione_dati(self, dati):
        """Tabelle precompilate dai risultati dell'analisi."""
        rumore = self._azione_risultati_rumore({})
        vibrazioni = self._azione_risultati_vibrazioni({})
        lettura = schede.leggi(self.scansione.get('scheda', ''))
        contesto = contesto_relazione.costruisci(
            dati.get('campi', {}), rumore.get('gruppi', []),
            vibrazioni.get('gruppi', []),
            lettura['dpi']['righe'], lettura['dpi']['colonne'])
        return {
            'tabella_dpi': contesto['tabella_dpi'],
            'tabella_HEG': contesto['tabella_HEG'],
            'tabella_vibrazioni': contesto['tabella_vibrazioni'],
            'frase_presenza': contesto['frase_presenza'],
            'colonne_dpi': contesto_relazione.COLONNE_TABELLA_DPI,
            'colonne_heg': contesto_relazione.COLONNE_TABELLA_HEG,
            'colonne_vib': contesto_relazione.COLONNE_TABELLA_VIB,
        }

    def _azione_relazione_preset(self, dati):
        operazione = dati.get('operazione', 'elenco')
        if operazione == 'elenco':
            return {'preset': configurazione.preset_relazione()}
        nome = (dati.get('nome') or 'preset').strip() or 'preset'
        if operazione == 'salva':
            configurazione.scrivi_preset_relazione(nome, dati.get('dati', {}))
            return {'ok': True, 'preset': configurazione.preset_relazione()}
        if operazione == 'carica':
            return {'ok': True, 'dati': configurazione.leggi_preset_relazione(nome)}
        return {'errore': f'Operazione sconosciuta: {operazione}'}

    def _azione_relazione_genera(self, dati):
        template = (dati.get('template')
                    or configurazione.percorso_modello('modello_relazione_rumore'))
        uscita = dati.get('output', '')
        rumore = self._azione_risultati_rumore({})
        vibrazioni = self._azione_risultati_vibrazioni({})
        lettura = schede.leggi(self.scansione.get('scheda', ''))
        contesto = contesto_relazione.costruisci(
            dati.get('campi', {}), rumore.get('gruppi', []),
            vibrazioni.get('gruppi', []),
            lettura['dpi']['righe'], lettura['dpi']['colonne'])
        try:
            percorso = generatore.genera(contesto, template, uscita)
        except NotImplementedError as errore:
            return {'ok': False, 'messaggio': str(errore), 'stub': True}
        except Exception as errore:
            return {'ok': False, 'messaggio': str(errore)}
        return {'ok': True, 'messaggio': f'Documento scritto: {percorso}'}


class Finestra(QMainWindow):
    """
    Finestra nativa con la barra del titolo resa trasparente.

    Restando una finestra normale, ridimensionamento da ogni bordo, angoli
    arrotondati, ombra e pieno schermo li fa macOS. La barra del titolo viene
    pero' resa trasparente e il contenuto sale fin sotto di essa, cosi' la
    fascia scura disegnata dalla pagina arriva in cima e i tre pallini di
    sistema ci si appoggiano sopra, dove il mockup ne disegnava di finti.
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle('Analisi Valutazione Rischio')
        self.setMinimumSize(LARGHEZZA_MINIMA, ALTEZZA_MINIMA)
        self.misure_barra = {'altezza_barra': 0, 'spazio_pallini': 0}
        self._ripristina_geometria()

        profilo = QWebEngineProfile.defaultProfile()
        self._inietta_webchannel(profilo)

        self.vista = QWebEngineView(self)
        self.vista.setPage(Pagina(profilo, self.vista))
        impostazioni = self.vista.settings()
        impostazioni.setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        impostazioni.setAttribute(QWebEngineSettings.ShowScrollBars, False)
        self.setCentralWidget(self.vista)

        self.ponte = Ponte(self)
        canale = QWebChannel(self.vista.page())
        canale.registerObject('ponte', self.ponte)
        self.vista.page().setWebChannel(canale)

        self.vista.load(QUrl.fromLocalFile(
            os.path.join(CARTELLA_PROGETTO, 'web', 'index.html')))

    @staticmethod
    def _inietta_webchannel(profilo):
        """
        Rende disponibile qwebchannel.js alla pagina.

        Il file e' una risorsa di Qt: iniettarlo come script evita di doverne
        scrivere una copia accanto alla pagina.
        """
        if any(s.name() == 'qwebchannel' for s in profilo.scripts().toList()):
            return
        risorsa = QFile(':/qtwebchannel/qwebchannel.js')
        if not risorsa.open(QIODevice.ReadOnly):
            print('qwebchannel.js non disponibile', file=sys.stderr)
            return
        sorgente = bytes(risorsa.readAll()).decode('utf-8')
        risorsa.close()

        script = QWebEngineScript()
        script.setName('qwebchannel')
        script.setSourceCode(sorgente)
        script.setInjectionPoint(QWebEngineScript.DocumentCreation)
        script.setWorldId(QWebEngineScript.MainWorld)
        script.setRunsOnSubFrames(False)
        profilo.scripts().insert(script)

    # ------------------------------------------------------------------
    # Aspetto nativo
    # ------------------------------------------------------------------

    def applica_aspetto_macos(self):
        """
        Rende trasparente la barra del titolo e porta il contenuto sotto di essa.

        Qt non espone queste proprieta' della NSWindow, quindi si passa da
        pyobjc. Va chiamata dopo show(): prima la finestra di sistema non
        esiste ancora. Se qualcosa non e' disponibile - altro sistema
        operativo, pyobjc assente, API cambiata - non si fa nulla e la
        finestra resta quella nativa normale, con la sua barra del titolo:
        si perde l'aspetto, non l'uso.

        OUTPUT: le misure aggiornate, con zeri quando lo stile non e' applicato
        """
        self.misure_barra = {'altezza_barra': 0, 'spazio_pallini': 0}
        if sys.platform != 'darwin':
            return self.misure_barra
        try:
            import AppKit
            import objc

            finestra_ns = objc.objc_object(c_void_p=int(self.winId())).window()
            finestra_ns.setStyleMask_(
                finestra_ns.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
            finestra_ns.setTitlebarAppearsTransparent_(True)
            finestra_ns.setTitleVisibility_(AppKit.NSWindowTitleHidden)
            self.misure_barra = self._misura_barra(AppKit, finestra_ns)
        except Exception as errore:
            print(f'aspetto nativo non applicato: {errore}', file=sys.stderr)
        return self.misure_barra

    @staticmethod
    def _misura_barra(AppKit, finestra_ns):
        """
        Altezza della barra del titolo e spazio occupato dai tre pallini.

        Si misurano invece di scriverli a mano: cambiano fra versioni di macOS,
        e a schermo intero la barra sparisce del tutto.

        La misura viene da contentLayoutRect, cioe' la parte di contenuto che la
        barra del titolo non copre. Non si puo' usare contentRectForFrameRect_:
        con la maschera a contenuto pieno il contenuto occupa gia' tutto il
        frame e la differenza sarebbe sempre zero. contentLayoutRect invece
        tiene conto della barra, e a schermo intero, dove la barra non c'e',
        torna da solo pari all'intero frame.

        OUTPUT: {'altezza_barra': int, 'spazio_pallini': int}
        """
        frame = finestra_ns.frame()
        altezza = int(round(frame.size.height
                            - finestra_ns.contentLayoutRect().size.height))

        spazio = 0
        pulsante = finestra_ns.standardWindowButton_(AppKit.NSWindowZoomButton)
        if pulsante is not None:
            riquadro = pulsante.frame()
            spazio = int(round(riquadro.origin.x + riquadro.size.width)) + MARGINE_PALLINI

        # a schermo intero la barra non c'e': niente fascia, niente spazio
        if altezza <= 0:
            return {'altezza_barra': 0, 'spazio_pallini': 0}
        return {'altezza_barra': altezza, 'spazio_pallini': spazio}

    def changeEvent(self, evento):
        """A schermo intero la barra del titolo sparisce: la pagina va avvisata."""
        super().changeEvent(evento)
        if evento.type() == QEvent.WindowStateChange and self.isVisible():
            precedenti = dict(self.misure_barra)
            self.applica_aspetto_macos()
            if self.misure_barra != precedenti:
                self.ponte.annuncia_finestra(self.misure_barra)

    # ------------------------------------------------------------------
    # Geometria ricordata fra un avvio e l'altro
    # ------------------------------------------------------------------

    def _ripristina_geometria(self):
        """Riapre la finestra dove e come era, se quel posto esiste ancora."""
        cfg = configurazione.config()
        salvata = cfg.get('geometria_finestra') or []
        if len(salvata) == 4 and all(isinstance(v, int) for v in salvata):
            riquadro = QRect(*salvata)
            # una finestra salvata su un monitor scollegato riaprirebbe fuori campo
            if riquadro.width() >= LARGHEZZA_MINIMA and riquadro.height() >= ALTEZZA_MINIMA \
                    and any(s.availableGeometry().intersects(riquadro)
                            for s in QGuiApplication.screens()):
                self.setGeometry(riquadro)
                if cfg.get('finestra_massimizzata'):
                    self.setWindowState(self.windowState() | Qt.WindowMaximized)
                return
        self.resize(LARGHEZZA, ALTEZZA)

    def _salva_geometria(self):
        cfg = configurazione.config()
        # da massimizzata normalGeometry tiene la dimensione "vera"
        riquadro = self.normalGeometry()
        cfg['geometria_finestra'] = [riquadro.x(), riquadro.y(),
                                     riquadro.width(), riquadro.height()]
        cfg['finestra_massimizzata'] = self.isMaximized()
        configurazione.scrivi(configurazione.CONFIG, cfg)

    def closeEvent(self, evento):
        self._salva_geometria()
        self.ponte.esecuzione.interrompi()
        super().closeEvent(evento)


def main():
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)
    applicazione = QApplication(sys.argv)
    applicazione.setApplicationName('AnalisiRischio')

    # la cartella passata da riga di comando viene scritta in configurazione
    # prima di aprire la finestra: e' da li' che app.js la legge, chiedendo lo
    # stato iniziale appena la pagina e' pronta
    if len(sys.argv) > 1:
        cfg = configurazione.config()
        cfg['ultima_root'] = os.path.abspath(sys.argv[1])
        configurazione.scrivi(configurazione.CONFIG, cfg)

    finestra = Finestra()
    finestra.show()
    # dopo show(): prima la finestra di sistema non esiste ancora
    finestra.applica_aspetto_macos()

    return applicazione.exec_()


if __name__ == '__main__':
    sys.exit(main())
