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

## Cosa fa

- **Riconosce la cartella**: a partire dalla root cerca i rami `Rumore` e
  `Vibrazioni` (anche dentro `rev/rev<N>/`), le cartelle `misure` e `output`,
  la `scheda_gruppi_dpi.xlsx` e i file delle misure di vibrazione, i cui nomi
  nei lavori reali variano. Il layout non e' uniforme fra le aziende e non
  viene dato per scontato.
- **Mostra e fa modificare i dati**: tabella DPI e scheda mansioni, valori
  misurati del rumore (`averaged_data.csv`), dati costruttori e misure HAV/WBV
  delle vibrazioni. Le scritture avvengono sulle stesse celle da cui i dati
  sono stati letti, conservando intestazioni e stile, con copia `.bak`.
- **Controlla i tempi prima di partire**: `analisi_8h` di VRR si ferma con un
  errore se la somma dei `Ti` di un gruppo non e' esattamente `T0`. La verifica
  viene fatta prima, con il dettaglio per gruppo.
- **Esegue in modo controllato**: Rumore, Vibrazioni oppure Combinato, con
  avanzamento per passo, log filtrabile e interruzione.
- **Prepara i dati della relazione**: modulo, tabella DPI, tabella dei gruppi
  omogenei e tabella A(8), precompilate dai risultati.

## Struttura

```
app.py                      finestra PyQt5 + ponte QWebChannel verso la pagina
core/
  configurazione.py         ~/.analisirischio : lettura e scrittura dei JSON
  progetto.py               riconoscimento della cartella di lavoro
  schede.py                 scheda_gruppi_dpi.xlsx (DPI + mansioni) e verifica Ti
  input_vibrazioni.py       datiCostr.xlsx, misureHAV.xlsx, misureWBV.xlsx
  risultati_rumore.py       VR8h_riepilogo/_totale + averaged_data.csv
  risultati_vibrazioni.py   riepilogo_vibrazioni.json, con ripiego su VR_VIB.xlsx
  esecuzione.py             avvio dei runner, eventi, interruzione
  backend.py                caricamento dei moduli di VRR e VRV
runner/
  passi.py                  elenco dei passi delle due pipeline
  protocollo.py             eventi JSON, cattura delle stampe dei backend
  runner_rumore.py          pipeline VRR
  runner_vibrazioni.py      pipeline VRV
relazione/
  contesto.py               costruzione del contesto per il modello .docx
  generatore.py             PUNTO DI ESTENSIONE: scrittura del documento
web/
  index.html app.js app.css interfaccia
  mockup.css                stili estratti dal mockup (non modificare a mano)
  mockup.html               markup del mockup, riferimento per nuove schermate
strumenti/                  estrazione asset, anteprima, prove
```

## Configurazione

Tutto in **una sola directory**, `~/.analisirischio`
(`ANALISIRISCHIO_HOME` per spostarla):

| file | contenuto |
|---|---|
| `config.json` | percorsi di VRR e VRV, cartella dei modelli, ultima root aperta |
| `parametri_rumore.json` | `T0`, `u2m`, `u_pos`, versione firmware, limite Lex,8h |
| `parametri_vibrazioni.json` | `C_P_HAV`, `C_P_WBV`, `C_S`, soglie, decimali, export PDF |
| `progetti_recenti.json` | ultime cartelle aperte |
| `relazione/<nome>.json` | preset dei dati della relazione |

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
  directory, mentre nei lavori reali il file sta nel ramo `Rumore`.

I runner ripetono la stessa sequenza chiamando le funzioni pubbliche con
percorsi espliciti, cosi' i parametri arrivano dall'interfaccia e i due
backend restano intatti.

## Relazione .docx

L'interfaccia e' completa e i dati sono pronti; manca la scrittura del
documento. Si implementa una sola funzione in `relazione/generatore.py`:

```python
def genera(contesto, template, output):
    documento = DocxTemplate(template)
    documento.render(contesto)
    documento.save(output)
    return output
```

Poi si mette `DISPONIBILE = True` nello stesso file. Il contesto arriva gia'
costruito da `relazione/contesto.py`, con `tabella_dpi`, `tabella_HEG` e
`tabella_vibrazioni` popolate dai risultati.

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
