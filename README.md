# AnalisiRischio

Interfaccia unica per la valutazione del rischio **rumore** e **vibrazioni
meccaniche**. Si apre il programma, si sceglie la cartella dell'azienda, si
controllano e si correggono i dati, si esegue la valutazione.

`VRR_analisiDati` (rumore) e `VRV_analisiDati` (vibrazioni) fanno da backend e
**non vengono modificati**: questo progetto ne pilota le funzioni pubbliche.

## Avvio

```bash
python app.py                       # riapre l'ultima cartella usata
python app.py /percorso/azienda     # apre direttamente una cartella
```

## La finestra

E' una normale finestra di macOS: si ridimensiona da ogni bordo e da ogni
angolo, ha gli angoli arrotondati e l'ombra di sistema, va a schermo intero e
si trascina dalla fascia scura in alto. Posizione e dimensione vengono
ricordate fra un avvio e l'altro.

La barra del titolo viene resa trasparente e il contenuto sale fin sotto di
essa, cosi' la fascia scura arriva in cima e i tre pallini di sistema ci si
appoggiano sopra, dove il mockup ne disegnava di finti. L'altezza della barra e
lo spazio dei pallini non sono scritti a mano: `app.py` li misura sulla
finestra vera e li passa alla pagina come variabili CSS, perche' cambiano fra
versioni di macOS e vanno a zero a schermo intero.

Se `pyobjc` non c'e', o su un altro sistema operativo, non succede niente di
grave: resta la barra del titolo di sistema sopra la pagina e l'applicazione si
usa allo stesso modo.

## Cosa fa

- **Riconosce la cartella**: a partire dalla root cerca i rami `Rumore` e
  `Vibrazioni` (anche dentro `rev/rev<N>/`), le cartelle `misure` e `output`,
  la `scheda_gruppi_dpi.xlsx` — nella **root**, perche' e' condivisa fra rumore
  e vibrazioni — e i file delle misure di vibrazione, i cui nomi nei lavori
  reali variano. Il layout non e' uniforme fra le aziende e non
  viene dato per scontato.
- **Mostra e fa modificare i dati**: tabella DPI e scheda mansioni, valori
  misurati del rumore (`averaged_data.csv`), dati costruttori e misure HAV/WBV
  delle vibrazioni. Le scritture avvengono sulle stesse celle da cui i dati
  sono stati letti, conservando intestazioni e stile, con copia `.bak`.
- **Controlla i tempi prima di partire**: `analisi_8h` di VRR si ferma con un
  errore se la somma dei `Ti` di un gruppo non e' esattamente `T0`. La verifica
  viene fatta prima, con il dettaglio per gruppo.
- **Esegue in modo controllato**: Rumore, Vibrazioni oppure Combinato, con
  avanzamento per passo, log filtrabile e interruzione. I risultati vanno in
  `output/` di ciascun ramo e i PDF in `output/allegati/` (per il rumore
  `VR8h_totale_aggiornato.pdf` e `Rilievi_Fonometrici.pdf`; per le vibrazioni
  `misureVIB_HAV.pdf`, `misureVIB_WBV.pdf` e `VR_VIB.pdf`). Il log del backend
  VRV e `riepilogo_vibrazioni.json` stanno invece in `Vibrazioni/log/`, cosi'
  in `output/` restano solo i risultati.
- **Scrive le relazioni .docx**: dati generali comuni piu' una sezione per il
  rumore e una per le vibrazioni; tabella DPI, tabella dei gruppi omogenei e
  tabella A(8) precompilate dai risultati. Si genera solo il rumore, solo le
  vibrazioni o tutte e due.
- **Tema chiaro o scuro**: un interruttore in fondo alla barra laterale, la
  scelta viene ricordata.

## Struttura

```
app.py                      finestra PyQt5 + ponte QWebChannel verso la pagina
core/
  configurazione.py         ~/.analisirischio : lettura e scrittura dei JSON
  progetto.py               riconoscimento della cartella di lavoro
  schede.py                 scheda_gruppi_dpi.xlsx (DPI + mansioni) e verifica Ti
  input_vibrazioni.py       datiCostr.xlsx, misureHAV.xlsx, misureWBV.xlsx
  risultati_rumore.py       VR8h_riepilogo/_totale + averaged_data.csv
  risultati_vibrazioni.py   log/riepilogo_vibrazioni.json, con ripiego su VR_VIB.xlsx
  esecuzione.py             avvio dei runner, eventi, interruzione
  backend.py                caricamento dei moduli di VRR e VRV
runner/
  passi.py                  elenco dei passi delle due pipeline
  protocollo.py             eventi JSON, cattura delle stampe dei backend
  runner_rumore.py          pipeline VRR
  runner_vibrazioni.py      pipeline VRV
  runner_relazione.py       scrittura .docx con i write_docx dei backend
relazione/
  contesto.py               campi e contesto per i modelli .docx
  generatore.py             avvio del runner della relazione e raccolta esiti
web/
  index.html app.js app.css interfaccia
  tema.css                  token dei colori di stato e tema chiaro
  mockup.css                stili estratti dal mockup (non modificare a mano)
  mockup.html               markup del mockup, riferimento per nuove schermate
strumenti/                  estrazione asset, anteprima, prove
```

## Configurazione

Tutto in **una sola directory**, `~/.analisirischio`
(`ANALISIRISCHIO_HOME` per spostarla):

| file | contenuto |
|---|---|
| `config.json` | percorsi di VRR e VRV, modelli e frontespizi .docx, logo, tema, ultima root aperta |
| `parametri_rumore.json` | `T0`, `u2m`, `u_pos`, versione firmware, limite Lex,8h |
| `parametri_vibrazioni.json` | `C_P_HAV`, `C_P_WBV`, `C_S`, soglie, decimali, export PDF |
| `progetti_recenti.json` | ultime cartelle aperte |

I dati della relazione Word non stanno qui: sono dati dell'azienda, non
dell'installazione, e vivono in `<root>/relazione_dati.json`. Aprendo la
cartella si caricano da soli; il pulsante *Salva* li riscrive sovrascrivendo.

I `parameters.py` dei due backend non vengono mai riscritti: se ne leggono
solo i valori di default al primo avvio.

## Due comportamenti da conoscere

**`averaged_data.csv` non viene cancellato.** `average_values()` di VRR lo
rilegge invece di ricalcolarlo, ed e' li' che finiscono le misure corrette o
aggiunte a mano dalla schermata *Misure singole*. La casella «Rileggi i file di
misura» lo rigenera da zero, perdendole: e' disattivata per impostazione
predefinita.

**Le due pipeline girano in due processi separati**, anche in modalita'
combinata. VRR e VRV importano entrambi un modulo chiamato `config`, che nello
stesso interprete si sovrapporrebbe; inoltre VRR cambia cartella di lavoro e
VRV azzera gli handler del logger.

## Perche' i runner non chiamano `main.main()`

- `VRR/main.py` legge i percorsi dal proprio `parameters.py`, entra nella
  cartella delle misure senza uscirne e lancia due utility con `os.system` e
  percorsi assoluti scritti nel codice.
- `VRV/main.py` pretende `scheda_gruppi_dpi.xlsx` *una cartella sopra* la main
  directory, mentre qui il file sta nella root dell'azienda ed e' comunque
  sostituibile a mano dalla schermata *Schede HEG*.

I runner ripetono la stessa sequenza chiamando le funzioni pubbliche con
percorsi espliciti, cosi' i parametri arrivano dall'interfaccia e i due
backend restano intatti.

## Relazione .docx

Dalla schermata *Relazione Word* si scrive la relazione del rumore, quella
delle vibrazioni o tutte e due. I dati si compilano in tre sezioni:

- **Dati generali** - anagrafica, figure responsabili, date, ototossici e
  interazioni: le chiavi che i due modelli hanno in comune;
- **Dati rumore** - metodo adottato, orari di lavoro, colonne «ototossici» e
  «rumori impulsivi» del quadro sinottico, frontespizio del ramo;
- **Dati vibrazioni** - orario di lavoro e frontespizio del ramo.

Il frontespizio si sceglie in due passi: la riga con la cartella (pulsante
per il dialogo di sistema, oppure percorso scritto a mano) e sotto il menu
con i `.docx` trovati in quella cartella. La cartella e' un'impostazione
dell'installazione e finisce in `config.json` come `cartella_frontespizi_rumore`
e `cartella_frontespizi_vibrazioni`; vuota, vale la sottocartella `RUM/` o
`VIB/` di `<cartella_modelli>/docx/frontespizi`. Il file scelto, invece, e' un
dato dell'azienda: in `relazione_dati.json` sta con il **percorso completo**,
ed e' quello che la relazione usa. Il menu elenca solo i `.docx` della cartella
scelta: se il valore salvato e' vuoto, e' un nome senza cartella (file delle
versioni precedenti) o punta a un'altra cartella, all'apertura viene riportato
sul file di pari nome, sul default di `frontespizio_<ramo>` in `config.json` o
sul primo disponibile, cosi' menu, file e documento dicono sempre la stessa cosa.

Tabelle DPI, gruppi omogenei ed esposizioni A(8) non si compilano: arrivano
dai risultati dell'analisi e si vedono in sola lettura nelle tre linguette
successive. I valori predefiniti dei campi sono quelli che i due `write_docx`
dei backend avevano scritti nel codice, quindi un progetto nuovo parte gia'
compilato. Salva/Carica conservano tutto in `~/.analisirischio/relazione/`.

I documenti finiscono in `<ramo>/output/Relazione_RUM.docx` e
`Relazione_VIB.docx`.

### Perche' anche qui un runner separato

`runner/runner_relazione.py` gira in un processo per ramo, per lo stesso
motivo delle pipeline di calcolo: i due backend importano entrambi un modulo
chiamato `config`, con contenuti diversi.

I due script non sono richiamabili come sono:

- `VRR/utility/write_docx_Rumore.py` non ha un `main()`: dalla «SEZIONE 3» in
  poi il codice gira all'import e scrive un documento contro percorsi cablati.
  Il runner ne carica quindi la sola testa, fino a quella sentinella, e
  ottiene le funzioni di caricamento senza eseguirne il corpo.
- `VRV/utility/write_docx_vib.py` ha un `main()`, ma legge i percorsi dai
  propri globali e i parametri da `parameters.py`.

In entrambi i casi il runner sovrascrive i globali dei percorsi con quelli che
arrivano dall'interfaccia e ripete la sola unione dei dizionari. I due backend
restano intatti.

## Tema chiaro e scuro

L'interruttore sta in fondo alla barra laterale, accanto a «Stato», e la
scelta finisce in `config.json` (`tema`), con una copia in `localStorage` che
la pagina legge prima del primo disegno per non far lampeggiare il tema
sbagliato all'avvio.

Il tema scuro e' il blocco `:root` di `mockup.css`, invariato; quello chiaro
sta in `web/tema.css` e ridefinisce soltanto i token. Nello stesso file
vivono i colori di stato - classi di rischio, avvisi, livelli di log, colonne
delle misure - che prima stavano scritti a mano dentro `app.css` e negli stili
in linea di `app.js`: sono gli unici che il tema chiaro non puo' ereditare,
perche' quei valori accesi su fondo bianco non si leggerebbero.

## Strumenti

```bash
python strumenti/estrai_asset.py            # rigenera web/mockup.css e i font dal mockup
python strumenti/prova_avvio.py <cartella>  # apre l'interfaccia e disegna ogni schermata
python strumenti/prova_esecuzione.py <cartella> [modalita]   # valutazione completa
python strumenti/controlla_js.sh web/app.js # sintassi del JavaScript
```

Per lavorare sull'aspetto senza avviare Qt:

```bash
python strumenti/genera_fixture.py <cartella> web/fixture.json
python -c "import json; d=json.load(open('web/fixture.json')); \
  open('web/fixture.js','w').write('window.__fixture = '+json.dumps(d)+';')"
python strumenti/servi_anteprima.py          # http://127.0.0.1:8777/anteprima.html
```

`web/fixture.js` contiene i dati veri dell'azienda usata: non va distribuito.

## Requisiti

`pip install -r requirements.txt`, piu' LibreOffice (comando `soffice`) per
l'export dei PDF, che se manca fa saltare solo quel passo.
