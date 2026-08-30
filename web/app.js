/*
 * Interfaccia di AnalisiRischio.
 *
 * La pagina disegna il mockup e parla con Python attraverso l'oggetto 'ponte'
 * esposto da QWebChannel: ponte.chiama(azione, payload) per le operazioni,
 * ponte.evento per gli eventi dell'analisi, che arrivano mentre i runner
 * girano in un altro processo.
 *
 * Le classi e gli stili in linea sono quelli del mockup: quando si aggiunge
 * una schermata conviene copiarli da web/mockup.html invece di inventarne.
 */

'use strict';

// ---------------------------------------------------------------------------
// Ponte verso Python
// ---------------------------------------------------------------------------

let ponte = null;
const inAttesaDelPonte = [];

function chiama(azione, dati) {
  return new Promise((risolvi) => {
    const esegui = () => ponte.chiama(azione, JSON.stringify(dati || {}), (risposta) => {
      let esito;
      try { esito = JSON.parse(risposta); } catch (e) { esito = { errore: 'risposta non valida' }; }
      risolvi(esito);
    });
    if (ponte) esegui(); else inAttesaDelPonte.push(esegui);
  });
}

// ---------------------------------------------------------------------------
// Stato
// ---------------------------------------------------------------------------

const S = {
  schermata: 'cartelle',
  modalita: 'rumore',
  root: '',
  scansione: null,
  config: {},
  parametriRumore: {},
  parametriVibrazioni: {},
  recenti: [],
  campiRelazione: [],
  passiPerModalita: {},

  schede: null,          // {dpi, mansioni, tempi}
  schedeSporche: false,
  risultatiRumore: null,
  misure: null,
  medieSporche: false,
  attrezzature: null,
  attrezzatureSporche: {},
  risultatiVibrazioni: null,

  esecuzione: { inCorso: false, passi: [], righe: [], filtro: 'tutti', coda: true, inizio: 0 },

  relazione: { campi: {}, dati: null, scheda: 'generali', messaggio: '', preset: [] },
  modale: null,
  messaggio: null,
};

const MAX_RIGHE_LOG = 4000;

// ---------------------------------------------------------------------------
// Utilita'
// ---------------------------------------------------------------------------

function esc(v) {
  return String(v === null || v === undefined ? '' : v)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function el(id) { return document.getElementById(id); }

function ora() {
  const d = new Date();
  const p = (n) => String(n).padStart(2, '0');
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function nomeBase(percorso) {
  if (!percorso) return '';
  return percorso.split('/').filter(Boolean).pop() || percorso;
}

/* Delega gli eventi: le schermate vengono ridisegnate per intero, quindi
   agganciare i listener ai singoli nodi non conviene. */
function suClic(selettore, gestore) { registra('click', selettore, gestore); }
function suModifica(selettore, gestore) { registra('change', selettore, gestore); }
function suInput(selettore, gestore) { registra('input', selettore, gestore); }

const gestori = { click: [], change: [], input: [] };
function registra(tipo, selettore, gestore) { gestori[tipo].push([selettore, gestore]); }

for (const tipo of Object.keys(gestori)) {
  document.addEventListener(tipo, (evento) => {
    for (const [selettore, gestore] of gestori[tipo]) {
      const nodo = evento.target.closest(selettore);
      if (nodo) { gestore(nodo, evento); return; }
    }
  }, tipo === 'click' ? false : true);
}

function messaggio(testo, genere) {
  S.messaggio = testo ? { testo, genere: genere || 'ok' } : null;
  disegna();
  if (testo) {
    clearTimeout(messaggio._t);
    messaggio._t = setTimeout(() => { S.messaggio = null; disegna(); }, 4200);
  }
}

// ---------------------------------------------------------------------------
// Barra del titolo (finestra senza cornice)
// ---------------------------------------------------------------------------

function inizializzaBarra() {
  const barra = el('tbar');
  let trascinando = false;

  barra.addEventListener('mousedown', (e) => {
    if (e.target.classList.contains('dot3')) return;
    trascinando = true;
    ponte.inizia_trascinamento(e.screenX, e.screenY);
  });
  window.addEventListener('mousemove', (e) => {
    if (trascinando) ponte.trascina(e.screenX, e.screenY);
  });
  window.addEventListener('mouseup', () => {
    if (trascinando) { trascinando = false; ponte.fine_trascinamento(); }
  });
  barra.addEventListener('dblclick', () => ponte.ingrandisci());

  el('btn-chiudi').addEventListener('click', () => ponte.chiudi());
  el('btn-riduci').addEventListener('click', () => ponte.riduci());
  el('btn-ingrandisci').addEventListener('click', () => ponte.ingrandisci());
}

// ---------------------------------------------------------------------------
// Sidebar
// ---------------------------------------------------------------------------

const VOCI = {
  cartelle: { icona: 'ph ph-folder-open', nome: 'Cartella di lavoro', sempre: true },
  schede: { icona: 'ph ph-clipboard-text', nome: 'Schede HEG', sempre: true },
  log: { icona: 'ph ph-terminal-window', nome: 'Log di esecuzione', sempre: true },
  superamenti: { icona: 'ph ph-warning-diamond', nome: 'Superamenti', ramo: 'rumore' },
  misure: { icona: 'ph ph-table', nome: 'Misure singole', ramo: 'rumore' },
  attrezzature: { icona: 'ph ph-target', nome: 'Attrezzature HAV/WBV', ramo: 'vibrazioni' },
  esposizioni: { icona: 'ph ph-warning-diamond', nome: 'Esposizioni A(8)', ramo: 'vibrazioni' },
  relazione: { icona: 'ph ph-file-doc', nome: 'Relazione Word', sempre: true },
};

function vociVisibili() {
  const rami = S.modalita === 'combinato' ? ['rumore', 'vibrazioni'] : [S.modalita];
  const elenco = [];
  for (const [chiave, voce] of Object.entries(VOCI)) {
    if (voce.sempre || rami.includes(voce.ramo)) elenco.push([chiave, voce]);
  }
  return elenco;
}

function bloccata(chiave) {
  const voce = VOCI[chiave];
  if (!voce || voce.sempre) return !S.scansione && chiave !== 'cartelle';
  if (voce.ramo === 'rumore') return !(S.risultatiRumore && S.risultatiRumore.disponibile);
  if (voce.ramo === 'vibrazioni') return !(S.risultatiVibrazioni && S.risultatiVibrazioni.disponibile);
  return false;
}

function disegnaSidebar() {
  const progetto = S.scansione && S.scansione.valida ? nomeBase(S.scansione.root) : 'nessun progetto';
  const alta = S.risultatiRumore ? (S.risultatiRumore.conteggi.ALTA || 0) : 0;
  const combinato = S.modalita === 'combinato';

  let html = `<div class="sec" style="padding:2px 10px 8px">${esc(progetto)}</div>`;
  let ramoCorrente = null;

  for (const [chiave, voce] of vociVisibili()) {
    if (combinato && voce.ramo && voce.ramo !== ramoCorrente) {
      ramoCorrente = voce.ramo;
      html += `<div class="sec" style="padding:10px 10px 4px">${ramoCorrente}</div>`;
    }
    if (combinato && !voce.ramo && ramoCorrente) {
      ramoCorrente = null;
      html += `<div class="sec" style="padding:10px 10px 4px">documento</div>`;
    }
    const spento = bloccata(chiave);
    const badge = chiave === 'superamenti' && alta
      ? `<span style="margin-left:auto;font-size:10px" class="mono">${alta} ALTA</span>` : '';
    const allerta = chiave === 'schede' && S.schede && S.schede.tempi && S.schede.tempi.sforati.length
      ? `<i class="ph-fill ph-warning-circle" style="margin-left:auto;color:#febc2e;font-size:13px"></i>` : '';
    html += `<button class="nvi ${S.schermata === chiave ? 'on' : ''}" data-vai="${chiave}"${spento ? ' disabled' : ''}>`
      + `<i class="${voce.icona}"></i>${esc(voce.nome)}${allerta}${badge}</button>`;
  }

  html += `<div style="margin-top:auto;display:flex;flex-direction:column;gap:8px">
    <div class="sec">Stato</div>
    <div style="font-size:11px;line-height:1.7;color:color-mix(in srgb,var(--color-text) 50%,transparent)">${esc(testoStato())}</div>`;
  if (S.esecuzione.inCorso) {
    html += `<button class="btn btn-secondary btn-block" data-azione="ferma"><i class="ph ph-stop"></i>Interrompi</button>`;
  } else {
    html += `<button class="btn btn-primary btn-block" data-azione="avvia"><i class="ph-fill ph-play"></i>Avvia analisi</button>`;
  }
  html += `</div>`;
  el('side').innerHTML = html;
}

function testoStato() {
  if (S.esecuzione.inCorso) {
    const fatti = S.esecuzione.passi.filter((p) => p.stato === 'fatto' || p.stato === 'saltato').length;
    return `analisi in corso · ${fatti}/${S.esecuzione.passi.length} passi`;
  }
  if (!S.scansione || !S.scansione.valida) return 'nessuna cartella selezionata';
  const parti = [`modalita' ${S.modalita}`];
  if (S.risultatiRumore && S.risultatiRumore.disponibile) {
    parti.push(`rumore: ${S.risultatiRumore.gruppi.length} gruppi`);
  }
  if (S.risultatiVibrazioni && S.risultatiVibrazioni.disponibile) {
    parti.push(`vibrazioni: ${S.risultatiVibrazioni.gruppi.length} gruppi`);
  }
  return parti.join('\n');
}

function statoTitolo() {
  if (S.esecuzione.inCorso) return 'analisi in corso…';
  if (S.scansione && S.scansione.valida) return nomeBase(S.scansione.root);
  return 'nessun progetto aperto';
}

// ---------------------------------------------------------------------------
// Disegno
// ---------------------------------------------------------------------------

const SCHERMATE = {};

function disegna() {
  el('stato-titolo').textContent = statoTitolo();
  disegnaSidebar();
  const disegnaSchermata = SCHERMATE[S.schermata] || SCHERMATE.cartelle;
  el('main').innerHTML = disegnaSchermata();
  el('modale').innerHTML = S.modale ? disegnaModale() : '';
}

function intestazione(titolo, sottotitolo, destra) {
  return `<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
    <div><h4 class="mtitle">${esc(titolo)}</h4>
      <p class="msub">${sottotitolo}</p></div>
    ${destra || ''}</div>`;
}

function bandaMessaggio() {
  if (!S.messaggio) return '';
  const icone = { ok: 'ph-fill ph-check-circle', avviso: 'ph-fill ph-warning-circle', errore: 'ph-fill ph-warning-circle' };
  return `<div class="avviso ${S.messaggio.genere === 'ok' ? 'ok' : S.messaggio.genere === 'errore' ? 'errore' : ''}">
    <i class="${icone[S.messaggio.genere] || icone.ok}"></i><div>${esc(S.messaggio.testo)}</div></div>`;
}

suClic('[data-vai]', (nodo) => vai(nodo.dataset.vai));

async function vai(schermata) {
  S.schermata = schermata;
  disegna();
  if (schermata === 'schede' && !S.schede) await caricaSchede();
  if (schermata === 'superamenti' && !S.risultatiRumore) await caricaRisultatiRumore();
  if (schermata === 'misure' && !S.misure) await caricaMisure();
  if (schermata === 'attrezzature' && !S.attrezzature) await caricaAttrezzature();
  if (schermata === 'esposizioni' && !S.risultatiVibrazioni) await caricaRisultatiVibrazioni();
  if (schermata === 'relazione' && !S.relazione.dati) await caricaRelazione();
  disegna();
}

// ---------------------------------------------------------------------------
// Schermata: Cartella di lavoro
// ---------------------------------------------------------------------------

const ICONE_FORMATO = { xlsx: 'ph ph-file-xls', csv: 'ph ph-table', txt: 'ph ph-terminal-window' };

SCHERMATE.cartelle = function () {
  const s = S.scansione;
  const rumore = (s && s.rumore) || {};
  const vibrazioni = (s && s.vibrazioni) || {};
  const cartelle = rumore.cartelle || [];
  const avvisi = (rumore.avvisi || []).concat(
    s && s.errore ? [s.errore] : []);

  const righeCartelle = cartelle.map((c) => `
    <div style="display:grid;grid-template-columns:1fr 78px 92px;padding:8px 12px;font-size:12.5px;border-top:1px solid var(--color-divider);opacity:${c.valida ? 1 : .45}">
      <span class="mono"><i class="${ICONE_FORMATO[c.fmt] || 'ph ph-folder'}" style="margin-right:7px;color:${c.valida ? 'var(--color-accent)' : '#febc2e'}"></i>${esc(c.path)}</span>
      <span class="tag" style="justify-self:start">${esc(c.fmt)}</span>
      <span style="text-align:right;color:${c.n ? 'inherit' : '#febc2e'}">${esc(c.n)}</span>
    </div>`).join('');

  const supporto = [
    ['output/ (rumore)', rumore.presente ? (rumore.output_pronta ? 'pronta' : 'da creare') : '—', rumore.presente],
    ['scheda_gruppi_dpi.xlsx', s && s.scheda ? nomeBase(s.scheda) : 'non trovata', !!(s && s.scheda)],
    ['VR8h_totale.xlsx', S.risultatiRumore && S.risultatiRumore.disponibile ? 'presente' : 'da produrre',
      !!(S.risultatiRumore && S.risultatiRumore.disponibile)],
    ['misure vibrazioni', vibrazioni.presente
      ? Object.entries(vibrazioni.file || {}).filter(([, v]) => v).map(([k]) => k).join(', ') || 'nessuna'
      : '—', vibrazioni.presente && Object.values(vibrazioni.file || {}).some(Boolean)],
  ].map(([nome, valore, ok], i, arr) => `
    <div class="kv"${i < arr.length - 1 ? ' style="border-bottom:1px solid var(--color-divider)"' : ''}>
      <span class="mono">${esc(nome)}</span>
      <span style="color:${ok ? '#8fe08f' : '#febc2e'}">${esc(valore)}</span></div>`).join('');

  const pr = S.parametriRumore;
  const pv = S.parametriVibrazioni;
  const mostraRumore = S.modalita !== 'vibrazioni';
  const mostraVibrazioni = S.modalita !== 'rumore';

  const modalitaPossibili = [
    ['rumore', 'Rumore', rumore.presente],
    ['vibrazioni', 'Vibrazioni', vibrazioni.presente],
    ['combinato', 'Combinato', rumore.presente && vibrazioni.presente],
  ];

  return `
  ${bandaMessaggio()}
  <div>
    <h4 class="mtitle">Cartella di lavoro</h4>
    <p class="msub">Seleziona la root dell'azienda. I rami Rumore e Vibrazioni, le cartelle misure e output e la scheda dei gruppi vengono riconosciuti automaticamente.</p>
  </div>
  <div style="display:flex;gap:8px;align-items:flex-end">
    <div class="field" style="flex:1"><label>Root azienda</label>
      <input class="input mono" style="font-size:12.5px" id="campo-root" value="${esc(S.root)}">
    </div>
    <button class="btn btn-secondary" data-azione="apri-picker"><i class="ph ph-folder-open"></i>Sfoglia…</button>
    <button class="btn btn-secondary" data-azione="dialogo-cartella"><i class="ph ph-folder"></i>Sistema…</button>
    <button class="btn btn-primary" data-azione="scansiona"><i class="ph ph-arrow-clockwise"></i>Apri</button>
  </div>

  <div style="display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,.85fr);gap:14px;min-height:0;flex:1">
    <div style="display:flex;flex-direction:column;gap:10px;min-height:0">
      <p class="sec">Cartelle di misura riconosciute</p>
      <div style="border:1px solid var(--color-divider);border-radius:8px;overflow:hidden">
        <div style="display:grid;grid-template-columns:1fr 78px 92px;padding:7px 12px;font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:color-mix(in srgb,var(--color-text) 55%,transparent);background:color-mix(in srgb,var(--color-text) 4%,transparent)">
          <span>Cartella</span><span>Formato</span><span style="text-align:right">File</span></div>
        ${righeCartelle || '<div style="padding:14px 12px;font-size:12px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">nessuna cartella di misura riconosciuta</div>'}
      </div>
      ${avvisi.map((a) => `<p style="margin:0;font-size:11px;color:#febc2e"><i class="ph-fill ph-warning-circle" style="margin-right:5px"></i>${esc(a)}</p>`).join('')}

      <p class="sec" style="margin-top:6px">Valutazione da eseguire</p>
      <div class="seg">
        ${modalitaPossibili.map(([chiave, nome, possibile]) => `
          <label class="seg-opt${S.modalita === chiave ? ' on' : ''}"${possibile ? '' : ' style="opacity:.4"'}>
            <input type="radio" name="modalita" value="${chiave}" data-modalita
              ${S.modalita === chiave ? 'checked' : ''}${possibile ? '' : ' disabled'}>${nome}</label>`).join('')}
      </div>
      <p style="margin:0;font-size:11px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">
        ${esc(S.scansione && S.scansione.valida
          ? `${cartelle.filter((c) => c.valida).length} cartelle di misura valide su ${cartelle.length}`
          : 'apri una cartella per iniziare')}</p>
    </div>

    <div style="display:flex;flex-direction:column;gap:12px;min-height:0;overflow-y:auto">
      <p class="sec">File e cartelle di supporto</p>
      <div class="card elev-sm" style="gap:0;padding:4px 12px">${supporto}</div>

      ${mostraRumore ? `
      <p class="sec">Parametri di calcolo · rumore</p>
      <div style="display:flex;flex-direction:column;gap:10px">
        <div class="field"><label>Versione firmware VR</label>
          <div class="seg">
            <label class="seg-opt${String(pr.VERSIONE_FIRMWARE) === '1' ? ' on' : ''}"><input type="radio" name="fw" value="1" data-par-rumore="VERSIONE_FIRMWARE" ${String(pr.VERSIONE_FIRMWARE) === '1' ? 'checked' : ''}>1</label>
            <label class="seg-opt${String(pr.VERSIONE_FIRMWARE) === '2' ? ' on' : ''}"><input type="radio" name="fw" value="2" data-par-rumore="VERSIONE_FIRMWARE" ${String(pr.VERSIONE_FIRMWARE) === '2' ? 'checked' : ''}>2</label>
          </div>
        </div>
        <div style="display:flex;gap:8px">
          <div class="field" style="flex:1"><label>T₀ (min)</label><input class="input mono" style="font-size:12.5px" data-par-rumore="T0" value="${esc(pr.T0)}"></div>
          <div class="field" style="flex:1"><label>u₂ₘ</label><input class="input mono" style="font-size:12.5px" data-par-rumore="u2m" value="${esc(pr.u2m)}"></div>
          <div class="field" style="flex:1"><label>u_pos</label><input class="input mono" style="font-size:12.5px" data-par-rumore="u_pos" value="${esc(pr.u_pos)}"></div>
        </div>
        <div class="field"><label>Valore limite Lex,8h (dBA)</label><input class="input mono" style="font-size:12.5px" data-par-rumore="LIMITE_LEX8H" value="${esc(pr.LIMITE_LEX8H)}"></div>
        <label class="seg-opt" style="justify-content:flex-start;gap:8px;background:transparent;box-shadow:none;padding-left:0">
          <input type="checkbox" data-par-rumore="rileggi_misure" ${pr.rileggi_misure ? 'checked' : ''}>
          <span style="font-size:12px">Rileggi i file di misura</span></label>
        <p style="margin:-4px 0 0;font-size:11px;color:#febc2e">Ricalcola averaged_data.csv da zero: le misure corrette o aggiunte a mano vanno perse.</p>
      </div>` : ''}

      ${mostraVibrazioni ? `
      <p class="sec">Parametri di calcolo · vibrazioni</p>
      <div style="display:flex;gap:8px">
        <div class="field" style="flex:1"><label>C_P HAV</label><input class="input mono" style="font-size:12.5px" data-par-vib="C_P_HAV" value="${esc(pv.C_P_HAV)}"></div>
        <div class="field" style="flex:1"><label>C_P WBV</label><input class="input mono" style="font-size:12.5px" data-par-vib="C_P_WBV" value="${esc(pv.C_P_WBV)}"></div>
        <div class="field" style="flex:1"><label>C_S</label><input class="input mono" style="font-size:12.5px" data-par-vib="C_S" value="${esc(pv.C_S)}"></div>
      </div>
      <label class="seg-opt" style="justify-content:flex-start;gap:8px;background:transparent;box-shadow:none;padding-left:0">
        <input type="checkbox" data-par-vib="ESPORTA_PDF" ${pv.ESPORTA_PDF ? 'checked' : ''}>
        <span style="font-size:12px">Esporta i PDF di allegato (richiede LibreOffice)</span></label>` : ''}

      <div style="margin-top:auto;display:flex;gap:8px;align-items:center;padding-top:8px">
        <button class="btn btn-primary" data-azione="avvia"${S.esecuzione.inCorso ? ' disabled' : ''}><i class="ph-fill ph-play"></i>Avvia analisi</button>
        <span style="font-size:11px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">${esc(S.config.cartella_config ? '' : '')}</span>
      </div>
    </div>
  </div>`;
};

// ---------------------------------------------------------------------------
// Selettori interni di cartella e file
// ---------------------------------------------------------------------------

function disegnaModale() {
  const m = S.modale;
  const voci = (m.voci || []).map((v, i) => `
    <button class="voce${m.selezione === v.path ? ' sel' : ''}" data-voce="${i}">
      <i class="${m.genere === 'file' ? 'ph ph-file-xls' : 'ph ph-folder'}"></i>
      <span style="flex:1">${esc(v.nome)}</span>
      ${v.rev ? `<span class="mono" style="font-size:11px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">${esc(v.rev)}</span>` : ''}
    </button>`).join('');

  return `<div class="velo" data-velo>
    <div class="dialogo" onclick="event.stopPropagation()">
      <div style="font:500 14px var(--font-heading)">${esc(m.titolo)}</div>
      <div style="display:flex;gap:6px;align-items:center">
        <button class="btn btn-secondary" data-azione="modale-su" style="padding:5px 9px"><i class="ph ph-arrows-down-up"></i></button>
        <div class="mono" style="flex:1;font-size:11.5px;color:color-mix(in srgb,var(--color-text) 60%,transparent);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl">${esc(m.percorso)}</div>
      </div>
      <div class="elenco-voci">${voci || '<div style="padding:12px;font-size:12px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">cartella vuota</div>'}</div>
      <div style="display:flex;gap:8px;justify-content:flex-end">
        <button class="btn btn-secondary" data-azione="modale-annulla">Annulla</button>
        <button class="btn btn-primary" data-azione="modale-conferma">${m.genere === 'file' ? 'Apri file' : 'Apri cartella'}</button>
      </div>
    </div></div>`;
}

async function apriModale(genere, percorso, titolo, alConferma) {
  const azione = genere === 'file' ? 'sfoglia_file' : 'sfoglia_cartelle';
  const esito = await chiama(azione, { percorso });
  S.modale = {
    genere, titolo, alConferma,
    percorso: esito.percorso, padre: esito.padre,
    voci: esito.voci || [], selezione: genere === 'file' ? '' : esito.percorso,
  };
  disegna();
}

suClic('[data-voce]', async (nodo) => {
  const voce = S.modale.voci[Number(nodo.dataset.voce)];
  if (S.modale.genere === 'file') { S.modale.selezione = voce.path; disegna(); return; }
  await apriModale('cartella', voce.path, S.modale.titolo, S.modale.alConferma);
});

suClic('[data-azione="modale-su"]', async () => {
  await apriModale(S.modale.genere, S.modale.padre, S.modale.titolo, S.modale.alConferma);
});
suClic('[data-azione="modale-annulla"]', () => { S.modale = null; disegna(); });
suClic('[data-azione="modale-conferma"]', async () => {
  const scelta = S.modale.selezione || S.modale.percorso;
  const alConferma = S.modale.alConferma;
  S.modale = null;
  disegna();
  if (alConferma) await alConferma(scelta);
});

// ---------------------------------------------------------------------------
// Griglia modificabile riusabile
// ---------------------------------------------------------------------------

/*
 * tabella: identificatore usato dagli eventi per sapere quale insieme di righe
 *          aggiornare (vedi modificaCella)
 * righe:   array di array, nell'ordine delle colonne
 */
function griglia(tabella, colonne, righe, opzioni) {
  const o = opzioni || {};
  const solaLettura = new Set(o.solaLettura || []);
  const larghezze = o.larghezze || {};

  const intestazioni = colonne.map((c) => `<th${larghezze[c] ? ` style="width:${larghezze[c]}"` : ''}>${esc(c)}</th>`).join('')
    + (o.senzaElimina ? '' : '<th style="width:34px"></th>');

  const corpo = righe.map((riga, i) => {
    const evidenzia = o.evidenzia && o.evidenzia(riga, i);
    const celle = colonne.map((nome, j) => {
      const valore = riga[j] === undefined ? '' : riga[j];
      const bloccata = solaLettura.has(nome);
      return `<td><input class="cella-edit" data-cella data-tab="${tabella}" data-riga="${i}" data-col="${j}"`
        + ` value="${esc(valore)}"${bloccata ? ' readonly tabindex="-1"' : ''}></td>`;
    }).join('');
    const elimina = o.senzaElimina ? '' :
      `<td><button class="btn-icona" data-elimina data-tab="${tabella}" data-riga="${i}" title="Rimuovi la riga"><i class="ph ph-trash"></i></button></td>`;
    return `<tr${evidenzia ? ' class="riga-sforata"' : ''}>${celle}${elimina}</tr>`;
  }).join('');

  return `<div class="scroll-tab"><table>
    <thead><tr>${intestazioni}</tr></thead>
    <tbody>${corpo || `<tr><td colspan="${colonne.length + 1}" style="padding:14px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">nessuna riga</td></tr>`}</tbody>
  </table></div>`;
}

/* Le tabelle modificabili vivono tutte nello stato: qui si dice, per nome,
   dove stanno le righe e cosa fare dopo una modifica. */
function tabellaDi(nome) {
  switch (nome) {
    case 'dpi': return { righe: S.schede && S.schede.dpi.righe, colonne: S.schede && S.schede.dpi.colonne,
                         dopo: () => { S.schedeSporche = true; } };
    case 'mansioni': return { righe: S.schede && S.schede.mansioni.righe, colonne: S.schede && S.schede.mansioni.colonne,
                              dopo: () => { S.schedeSporche = true; ricalcolaTempi(); } };
    case 'medie': return { righe: S.misure && S.misure.medie.righe.map((r) => r), colonne: null,
                           dopo: () => { S.medieSporche = true; } };
    case 'costruttori': return { righe: S.attrezzature && S.attrezzature.costruttori.righe,
                                 colonne: S.attrezzature && S.attrezzature.costruttori.colonne,
                                 dopo: () => { S.attrezzatureSporche.costruttori = true; } };
    case 'HAV': return { righe: S.attrezzature && S.attrezzature.HAV.righe,
                         colonne: S.attrezzature && S.attrezzature.HAV.colonne,
                         dopo: () => { S.attrezzatureSporche.HAV = true; } };
    case 'WBV': return { righe: S.attrezzature && S.attrezzature.WBV.righe,
                         colonne: S.attrezzature && S.attrezzature.WBV.colonne,
                         dopo: () => { S.attrezzatureSporche.WBV = true; } };
    default: return null;
  }
}

suInput('[data-cella]', (nodo) => {
  const t = tabellaDi(nodo.dataset.tab);
  if (!t || !t.righe) return;
  const riga = t.righe[Number(nodo.dataset.riga)];
  if (!riga) return;
  riga[Number(nodo.dataset.col)] = nodo.value;
  t.dopo();
  aggiornaIndicatori(nodo.dataset.tab);
});

suClic('[data-elimina]', (nodo) => {
  const t = tabellaDi(nodo.dataset.tab);
  if (!t || !t.righe) return;
  t.righe.splice(Number(nodo.dataset.riga), 1);
  t.dopo();
  disegna();
});

suClic('[data-aggiungi]', (nodo) => {
  const nome = nodo.dataset.aggiungi;
  const t = tabellaDi(nome);
  if (!t || !t.righe) return;
  t.righe.push(new Array((t.colonne || []).length).fill(''));
  t.dopo();
  disegna();
});

/* Dopo una modifica di cella non si ridisegna tutto - si perderebbe il fuoco -
   ma il banner dei tempi e i pulsanti di salvataggio vanno aggiornati. */
function aggiornaIndicatori(nome) {
  if (nome === 'mansioni') {
    const banner = el('banner-tempi');
    if (banner) banner.outerHTML = bannerTempi();
  }
  disegnaSidebar();
  for (const nodo of document.querySelectorAll('[data-salva]')) nodo.removeAttribute('disabled');
}

function ricalcolaTempi() {
  if (!S.schede) return;
  const c = S.schede.mansioni.colonne;
  const iId = c.indexOf('ID_GrOm'), iNome = c.indexOf('Descrizione_GrOm'), iTi = c.indexOf('Ti');
  const t0 = Number(S.parametriRumore.T0) || 480;
  const totali = new Map(), nomi = new Map();
  for (const riga of S.schede.mansioni.righe) {
    const codice = String(riga[iId] || '').trim();
    if (!codice) continue;
    const ti = parseFloat(String(riga[iTi] || '').replace(',', '.')) || 0;
    totali.set(codice, (totali.get(codice) || 0) + ti);
    if (!nomi.has(codice) && riga[iNome]) nomi.set(codice, riga[iNome]);
  }
  const gruppi = [...totali.entries()].map(([code, tot]) => {
    const delta = Math.round((tot - t0) * 1000) / 1000;
    return { code, nome: nomi.get(code) || '', tot: Math.round(tot * 100) / 100,
             delta: (delta > 0 ? '+' : '') + delta, oltre: Math.abs(delta) > 1e-6 };
  });
  S.schede.tempi = { t0, gruppi, sforati: gruppi.filter((g) => g.oltre) };
}

// ---------------------------------------------------------------------------
// Schermata: Schede HEG
// ---------------------------------------------------------------------------

function bannerTempi() {
  const t = S.schede && S.schede.tempi;
  if (!t || !t.sforati.length) {
    return `<div id="banner-tempi" class="avviso ok"><i class="ph-fill ph-check-circle"></i>
      <div>Tutti i ${t ? t.gruppi.length : 0} gruppi omogenei hanno somma dei Ti pari a T₀ (${t ? t.t0 : 480} min).</div></div>`;
  }
  const elenchi = t.sforati.map((g) => `<span class="tag" style="margin-right:6px">GrOm ${esc(g.code)} · ${esc(g.tot)} min <span style="color:#febc2e">${esc(g.delta)}</span></span>`).join('');
  return `<div id="banner-tempi" class="avviso"><i class="ph-fill ph-warning-circle"></i>
    <div><div style="margin-bottom:6px">${t.sforati.length} gruppi omogenei con somma dei Ti diversa da T₀ (${t.t0} min) — l'analisi Lex,8h si fermerebbe con un errore.</div>
    <div>${elenchi}</div></div></div>`;
}

SCHERMATE.schede = function () {
  if (!S.schede) return '<p class="msub">caricamento…</p>';
  if (S.schede.errore) {
    return intestazione('Schede HEG', 'Tabella DPI e scheda mansioni')
      + `<div class="avviso errore"><i class="ph-fill ph-warning-circle"></i><div>${esc(S.schede.errore)}</div></div>`;
  }
  const c = S.schede.mansioni.colonne;
  const iId = c.indexOf('ID_GrOm');
  const sforati = new Set((S.schede.tempi ? S.schede.tempi.sforati : []).map((g) => g.code));

  return `
  ${bandaMessaggio()}
  ${intestazione('Schede HEG',
      `Tabella DPI e scheda mansioni lette da <span class="mono">${esc(nomeBase(S.schede.percorso))}</span> · ${S.schede.mansioni.righe.length} righe, ${S.schede.tempi ? S.schede.tempi.gruppi.length : 0} gruppi`,
      `<span class="tag">T₀ ${esc(S.parametriRumore.T0)} min</span>`)}

  <div style="display:flex;gap:8px;align-items:flex-end">
    <div class="field" style="flex:1"><label>File scheda gruppi e DPI</label>
      <div class="mono" style="font-size:12px;padding:6px 0;color:color-mix(in srgb,var(--color-text) 65%,transparent);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl">${esc(S.schede.percorso)}</div>
    </div>
    <button class="btn btn-secondary" data-azione="scegli-scheda"><i class="ph ph-folder-open"></i>Sfoglia…</button>
    <button class="btn btn-secondary" data-azione="ricarica-schede"><i class="ph ph-arrow-clockwise"></i>Ricarica</button>
    <button class="btn btn-primary" data-azione="salva-schede" data-salva${S.schedeSporche ? '' : ' disabled'}><i class="ph ph-floppy-disk"></i>Salva modifiche</button>
  </div>

  ${bannerTempi()}

  <div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.45fr);gap:14px;min-height:0;flex:1">
    <div style="display:flex;flex-direction:column;gap:8px;min-height:0;min-width:0">
      <div style="display:flex;align-items:center;gap:8px">
        <p class="sec" style="flex:1">Tabella DPI</p>
        <button class="btn btn-secondary" data-aggiungi="dpi" style="padding:4px 9px;font-size:11.5px"><i class="ph ph-plus"></i>Aggiungi riga</button>
      </div>
      ${griglia('dpi', S.schede.dpi.colonne, S.schede.dpi.righe,
        { larghezze: { Descrizione: '190px', Marca: '130px', Modello: '150px' } })}
    </div>
    <div style="display:flex;flex-direction:column;gap:8px;min-height:0;min-width:0">
      <div style="display:flex;align-items:center;gap:8px">
        <p class="sec" style="flex:1">Scheda mansioni · gruppi omogenei</p>
        <span style="font-size:11px;color:color-mix(in srgb,var(--color-text) 42%,transparent)">le righe dei gruppi fuori da T₀ sono evidenziate</span>
        <button class="btn btn-secondary" data-aggiungi="mansioni" style="padding:4px 9px;font-size:11.5px"><i class="ph ph-plus"></i>Aggiungi riga</button>
      </div>
      ${griglia('mansioni', c, S.schede.mansioni.righe, {
        evidenzia: (riga) => sforati.has(String(riga[iId] || '').trim()),
        larghezze: { Descrizione_GrOm: '210px', Descrizione_reparto: '150px',
                     Descrizione_compito: '250px', WBV: '150px', HAV: '150px' },
      })}
    </div>
  </div>`;
};

// ---------------------------------------------------------------------------
// Schermata: Log di esecuzione
// ---------------------------------------------------------------------------

const ICONE_PASSO = {
  attesa: ['ph ph-minus', 'color-mix(in srgb,var(--color-text) 30%,transparent)'],
  corso: ['ph ph-arrow-clockwise', 'var(--color-accent)'],
  fatto: ['ph-fill ph-check-circle', '#32cd32'],
  saltato: ['ph ph-minus', '#febc2e'],
  errore: ['ph-fill ph-warning-circle', '#b22222'],
};

const COLORI_LIVELLO = { info: 'color-mix(in srgb,var(--color-text) 55%,transparent)',
                         warning: '#febc2e', error: '#ff8a80' };

SCHERMATE.log = function () {
  const e = S.esecuzione;
  const conteggi = { tutti: e.righe.length, info: 0, warning: 0, error: 0 };
  for (const r of e.righe) conteggi[r.livello] = (conteggi[r.livello] || 0) + 1;

  const visibili = e.filtro === 'tutti' ? e.righe : e.righe.filter((r) => r.livello === e.filtro);
  const fatti = e.passi.filter((p) => p.stato === 'fatto' || p.stato === 'saltato').length;
  const avanzamento = e.passi.length ? Math.round(fatti / e.passi.length * 100) : 0;

  const passi = e.passi.map((p) => {
    const [icona, colore] = ICONE_PASSO[p.stato || 'attesa'];
    return `<div style="display:flex;align-items:center;gap:9px;padding:5px 0;font-size:12.5px;opacity:${p.stato && p.stato !== 'attesa' ? 1 : .5}">
      <i class="${icona}" style="color:${colore};font-size:14px"></i>
      <span style="flex:1">${esc(p.nome)}</span>
      ${p.pipeline ? `<span class="tag" style="font-size:10px">${esc(p.pipeline)}</span>` : ''}
      <span class="mono" style="font-size:11px;color:color-mix(in srgb,var(--color-text) 40%,transparent)">${esc(p.msg || '')}</span>
    </div>`;
  }).join('');

  const righe = visibili.map((r) => `
    <div class="logline" style="border-left-color:${r.livello === 'info' ? 'transparent' : COLORI_LIVELLO[r.livello]};font-size:11.5px;line-height:1.85">
      <span class="mono" style="color:color-mix(in srgb,var(--color-text) 32%,transparent);margin-right:8px">${esc(r.t)}</span>
      <span class="mono" style="color:${COLORI_LIVELLO[r.livello]};margin-right:8px">${esc(r.livello.toUpperCase().padEnd(7))}</span>
      <span>${esc(r.msg)}</span></div>`).join('');

  const filtro = (chiave, etichetta, colore) => `
    <label class="seg-opt${e.filtro === chiave ? ' on' : ''}">
      <input type="radio" name="livello" value="${chiave}" data-filtro-log ${e.filtro === chiave ? 'checked' : ''}>
      ${colore ? `<span style="width:7px;height:7px;border-radius:50%;background:${colore};display:inline-block;margin-right:5px"></span>` : ''}
      ${etichetta} <span class="mono" style="margin-left:5px;opacity:.6">${conteggi[chiave] || 0}</span></label>`;

  return `
  ${intestazione('Log di esecuzione',
      e.inCorso ? 'analisi in corso' : (e.passi.length ? 'ultima esecuzione' : 'nessuna esecuzione in questa sessione'),
      `<span class="mono" style="font-size:12px;color:var(--color-accent)">${esc(e.durata !== undefined ? e.durata + ' s' : '')}</span>`)}

  <div style="display:flex;flex-direction:column;gap:8px">
    <div style="height:4px;border-radius:2px;background:color-mix(in srgb,var(--color-text) 10%,transparent);overflow:hidden">
      <div style="height:100%;width:${avanzamento}%;background:var(--color-accent);transition:width .25s"></div>
    </div>
    <div style="max-height:180px;overflow-y:auto">${passi || '<p class="msub">i passi compaiono all\'avvio dell\'analisi</p>'}</div>
  </div>

  <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
    <div class="seg">
      ${filtro('tutti', 'Tutti', '')}
      ${filtro('info', 'Info', 'var(--color-accent)')}
      ${filtro('warning', 'Warning', '#febc2e')}
      ${filtro('error', 'Errori', '#b22222')}
    </div>
    <div style="margin-left:auto;display:flex;gap:6px">
      <button class="btn btn-secondary" data-azione="coda" style="padding:5px 10px;font-size:11.5px">
        <i class="ph ph-arrows-down-up"></i>${e.coda ? 'Segui la coda' : 'Coda libera'}</button>
      <button class="btn btn-secondary" data-azione="pulisci-log" style="padding:5px 10px;font-size:11.5px"><i class="ph ph-eraser"></i>Pulisci</button>
    </div>
  </div>

  <div id="log-righe" style="flex:1;min-height:0;overflow-y:auto;background:color-mix(in srgb,var(--color-text) 3%,transparent);border-radius:8px;padding:8px 0">
    ${righe || '<div style="padding:10px 12px;font-size:12px;color:color-mix(in srgb,var(--color-text) 40%,transparent)">nessuna riga per questo filtro</div>'}
  </div>`;
};

// ---------------------------------------------------------------------------
// Schermata: Superamenti (rumore)
// ---------------------------------------------------------------------------

SCHERMATE.superamenti = function () {
  const r = S.risultatiRumore;
  if (!r || !r.disponibile) {
    return intestazione('Superamenti del valore limite', 'nessun risultato disponibile')
      + `<div class="avviso"><i class="ph-fill ph-warning-circle"></i><div>Esegui l'analisi del rumore: i risultati vengono letti da VR8h_riepilogo.xlsx.</div></div>`;
  }
  const vista = S.vistaSuperamenti || 'sinottico';
  const soloAlta = !!S.soloAlta;
  const gruppi = soloAlta ? r.gruppi.filter((g) => g.classe === 'ALTA') : r.gruppi;

  const scelta = (chiave, etichetta, icona) => `
    <label class="seg-opt${vista === chiave ? ' on' : ''}">
      <input type="radio" name="vistaSup" value="${chiave}" data-vista-sup ${vista === chiave ? 'checked' : ''}>
      <i class="${icona}" style="margin-right:5px"></i>${etichetta}</label>`;

  let corpo = '';
  if (vista === 'sinottico') {
    corpo = `<div class="scroll-tab"><table>
      <thead><tr><th>Gruppo omogeneo / attività</th><th>Lex,8h</th><th>U</th><th>Lex max</th><th>L picco,C</th><th>LeqA</th><th>Ti</th><th>Classe</th></tr></thead>
      <tbody>${gruppi.map((g) => `
        <tr data-gruppo="${esc(g.code)}" class="gsel">
          <td><span style="width:7px;height:7px;border-radius:50%;background:${g.colore};display:inline-block;margin-right:8px"></span>
              <span class="mono" style="opacity:.55;margin-right:6px">${esc(g.code)}</span>${esc(g.nome)}</td>
          <td class="mono">${esc(g.lex)}</td><td class="mono">${esc(g.u)}</td>
          <td class="mono"${g.oltre_limite ? ' style="color:#ff8a80;font-weight:600"' : ''}>${esc(g.lexmax)}</td>
          <td class="mono">${esc(g.picco)}</td><td class="mono">${esc(g.leqa)}</td><td class="mono">${esc(g.ti)}</td>
          <td><span class="tag" style="color:${g.colore};box-shadow:inset 0 0 0 1px ${g.colore}66">${esc(g.classe)}</span></td>
        </tr>`).join('')}</tbody></table></div>`;
  } else if (vista === 'semaforo') {
    const colonna = (classe, colore) => {
      const dentro = r.gruppi.filter((g) => g.classe === classe);
      return `<div style="display:flex;flex-direction:column;gap:9px;min-height:0;overflow-y:auto">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="width:9px;height:9px;border-radius:50%;background:${colore}"></span>
          <span style="font:500 13px var(--font-heading)">${classe}</span>
          <span class="mono" style="opacity:.5">${dentro.length}</span></div>
        ${dentro.map((g) => `
          <div class="card elev-sm gsel" data-gruppo="${esc(g.code)}" style="padding:9px 11px;gap:6px">
            <div style="display:flex;align-items:center;gap:7px">
              <span class="mono" style="opacity:.5">${esc(g.code)}</span>
              <span style="font-size:12.5px;flex:1">${esc(g.nome)}</span>
              <span class="mono" style="font-size:14px;color:${colore}">${esc(g.lexmax)}</span>
              <span style="font-size:10px;opacity:.5">dBA</span></div>
            <div style="display:flex;gap:10px;font-size:11px;color:color-mix(in srgb,var(--color-text) 50%,transparent)">
              <span>Lex,8h <span class="mono">${esc(g.lex)}</span> ± <span class="mono">${esc(g.u)}</span></span>
              <span>picco <span class="mono">${esc(g.picco)}</span></span></div>
          </div>`).join('')}</div>`;
    };
    corpo = `<div style="display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr) minmax(0,1fr);gap:14px;flex:1;min-height:0">
      ${colonna('ALTA', '#b22222')}${colonna('MEDIA', '#00bfff')}${colonna('BASSA', '#32cd32')}</div>`;
  } else {
    const scelto = r.gruppi.find((g) => g.code === S.gruppoScelto) || r.gruppi[0];
    corpo = `<div style="display:grid;grid-template-columns:230px minmax(0,1fr);gap:14px;flex:1;min-height:0">
      <div style="display:flex;flex-direction:column;gap:4px;overflow-y:auto">
        ${r.gruppi.map((g) => `
          <button class="rowbtn gsel${scelto && g.code === scelto.code ? ' picked' : ''}" data-gruppo="${esc(g.code)}" style="padding:8px 10px;border-radius:8px">
            <div style="display:flex;align-items:center;gap:7px">
              <span class="mono" style="opacity:.5;font-size:11px">${esc(g.code)}</span>
              <span style="font-size:12px;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(g.nome)}</span>
              <span class="mono" style="font-size:12px;color:${g.colore}">${esc(g.lexmax)}</span></div>
          </button>`).join('')}
      </div>
      ${scelto ? dettaglioGruppo(scelto, r.limite) : '<div class="msub">nessun gruppo</div>'}
    </div>`;
  }

  return `
  ${intestazione('Superamenti del valore limite',
      `${r.gruppi.length} gruppi omogenei · limite Lex,8h ${r.limite} dBA`,
      `<span class="tag" style="color:#b22222;box-shadow:inset 0 0 0 1px #b2222266"><i class="ph-fill ph-warning-circle" style="margin-right:5px"></i>${r.conteggi.ALTA || 0} in classe ALTA</span>`)}
  <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <div class="seg">${scelta('sinottico', 'Quadro sinottico', 'ph ph-table')}${scelta('semaforo', 'Semaforo', 'ph ph-columns')}${scelta('dettaglio', 'Dettaglio gruppo', 'ph ph-rows')}</div>
    ${vista === 'sinottico' ? `<label class="seg-opt" style="background:transparent;box-shadow:none"><input type="checkbox" data-solo-alta ${soloAlta ? 'checked' : ''}><span style="margin-left:6px">Solo classe ALTA</span></label>` : ''}
    <span style="margin-left:auto;font-size:11px;color:color-mix(in srgb,var(--color-text) 42%,transparent)">${r.oltre_limite} gruppi oltre il valore limite</span>
  </div>
  ${corpo}`;
};

function dettaglioGruppo(g, limite) {
  const kpi = (etichetta, valore, unita) => `
    <div class="card elev-sm" style="padding:9px 12px;gap:3px">
      <div style="font-size:10px;letter-spacing:.08em;text-transform:uppercase;color:color-mix(in srgb,var(--color-text) 45%,transparent)">${etichetta}</div>
      <div class="mono" style="font-size:17px">${esc(valore)}${unita ? `<span style="font-size:11px;opacity:.5"> ${unita}</span>` : ''}</div></div>`;

  const valore = parseFloat(g.lexmax);
  const percentuale = isNaN(valore) ? 0 : Math.max(0, Math.min(100, (valore - 75) / 20 * 100));

  return `<div style="display:flex;flex-direction:column;gap:12px;min-height:0;overflow-y:auto">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px">
      <div><span class="mono" style="opacity:.5;font-size:12px">${esc(g.code)}</span>
        <h4 class="mtitle" style="font-size:16px">${esc(g.nome)}</h4>
        <p class="msub">${g.n_misure} misure · Ti totale ${esc(g.ti)} min</p></div>
      <span class="tag" style="color:${g.colore};box-shadow:inset 0 0 0 1px ${g.colore}66">CLASSE RISCHIO ${esc(g.classe)}</span>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px">
      ${kpi('Lex,8h', g.lex, 'dBA')}${kpi('U estesa', '± ' + g.u, '')}${kpi('Lex max', g.lexmax, '')}${kpi('L picco,C', g.picco, '')}
    </div>
    <div>
      <div style="position:relative;height:8px;border-radius:4px;background:color-mix(in srgb,var(--color-text) 10%,transparent);margin:14px 0 4px">
        <div style="position:absolute;inset:0;width:${percentuale}%;background:${g.colore};border-radius:4px"></div>
        ${[[80, '80'], [85, '85'], [limite, String(limite)]].map(([v, testo]) => `
          <div style="position:absolute;left:${Math.max(0, Math.min(100, (v - 75) / 20 * 100))}%;top:-13px;transform:translateX(-50%)">
            <div class="mono" style="font-size:9px;color:color-mix(in srgb,var(--color-text) 42%,transparent)">${testo}</div>
            <div style="width:1px;height:14px;background:color-mix(in srgb,var(--color-text) 22%,transparent);margin:0 auto"></div></div>`).join('')}
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:color-mix(in srgb,var(--color-text) 35%,transparent)"><span>75</span><span>95 dBA</span></div>
    </div>
    <p class="sec">Attività del gruppo</p>
    <div class="scroll-tab" style="flex:none;max-height:260px"><table>
      <thead><tr><th>ID misura</th><th>Compito</th><th>Ti (min)</th><th>LeqA</th><th>LeqC</th><th>Ppeak</th><th>Contributo</th></tr></thead>
      <tbody>${g.attivita.map((a) => `<tr>
        <td class="mono">${esc(a.id)}</td><td>${esc(a.desc)}</td><td class="mono">${esc(a.ti)}</td>
        <td class="mono"${a.rossa ? ' style="color:#ff8a80"' : ''}>${esc(a.leqa)}</td>
        <td class="mono">${esc(a.leqc)}</td><td class="mono">${esc(a.ppeak)}</td>
        <td class="mono" style="opacity:.7">${esc(a.contributo)}</td></tr>`).join('')}</tbody></table></div>
  </div>`;
}

// ---------------------------------------------------------------------------
// Schermata: Misure singole (rumore)
// ---------------------------------------------------------------------------

const COLORI_COLONNA = { U: '#87ceeb', LeqA: '#ffa07a', Ppeak: '#ff4500' };

SCHERMATE.misure = function () {
  const m = S.misure;
  if (!m) return '<p class="msub">caricamento…</p>';
  const query = (S.queryMisure || '').toLowerCase();
  const piatto = S.misurePiatte;

  const filtra = (righe) => !query ? righe : righe.filter((r) =>
    String(r.ID_misura || '').toLowerCase().includes(query) ||
    String(r.Descrizione_compito || '').toLowerCase().includes(query));

  const celleRiga = (r) => m.colonne.map((c) => `<td class="mono"${COLORI_COLONNA[c] ? ` style="color:${COLORI_COLONNA[c]}"` : ''}>${esc(r[c])}</td>`).join('');

  let corpo = '';
  let conto = 0;
  if (piatto) {
    const tutte = [];
    for (const g of m.gruppi) for (const r of filtra(g.righe)) tutte.push([g, r]);
    conto = tutte.length;
    corpo = tutte.map(([g, r]) => `<tr><td class="mono" style="opacity:.5">${esc(g.code)}</td>${celleRiga(r)}</tr>`).join('');
  } else {
    for (const g of m.gruppi) {
      const righe = filtra(g.righe);
      if (!righe.length) continue;
      conto += righe.length;
      corpo += `<tr><td colspan="${m.colonne.length}" style="background:color-mix(in srgb,var(--color-accent) 10%,transparent);font-size:11.5px;padding:6px 9px">
        <span class="mono" style="opacity:.6;margin-right:8px">GrOm ${esc(g.code)}</span>${esc(g.nome)}</td></tr>`;
      corpo += righe.map((r) => `<tr>${celleRiga(r)}</tr>`).join('');
    }
  }

  const medie = m.medie || { righe: [], colonne: [] };
  const righeMedie = medie.righe.map((r) => medie.colonne.map((c) => r[c]));

  return `
  ${bandaMessaggio()}
  ${intestazione('Misure singole',
      `${conto} misure dai fogli «Scheda N» di VR8h_totale.xlsx`,
      `<div style="display:flex;gap:8px;align-items:center">
        <input class="input" style="width:220px;font-size:12px" placeholder="Cerca compito o ID misura…" data-query-misure value="${esc(S.queryMisure || '')}">
        <div class="seg">
          <label class="seg-opt${!piatto ? ' on' : ''}"><input type="radio" name="ragg" data-ragg value="gruppo" ${!piatto ? 'checked' : ''}>Per gruppo</label>
          <label class="seg-opt${piatto ? ' on' : ''}"><input type="radio" name="ragg" data-ragg value="piatto" ${piatto ? 'checked' : ''}>Elenco piatto</label>
        </div></div>`)}

  <div style="display:flex;gap:14px;font-size:11px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">
    ${Object.entries(COLORI_COLONNA).map(([c, colore]) => `<span><span style="width:8px;height:8px;border-radius:2px;background:${colore};display:inline-block;margin-right:5px"></span>${c}</span>`).join('')}
    <span style="margin-left:auto">Colonne evidenziate come nel foglio «Scheda N»</span>
  </div>

  <div class="scroll-tab" style="flex:1.3"><table>
    <thead><tr>${piatto ? '<th style="width:56px">GrOm</th>' : ''}${m.colonne.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
    <tbody>${corpo || `<tr><td colspan="${m.colonne.length + 1}" style="padding:14px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">nessuna misura</td></tr>`}</tbody>
  </table></div>

  <div style="display:flex;align-items:center;gap:8px">
    <p class="sec" style="flex:1">Valori misurati · averaged_data.csv</p>
    <span style="font-size:11px;color:color-mix(in srgb,var(--color-text) 42%,transparent)">modificabili: l'analisi li rilegge da qui invece di ricalcolarli</span>
    <button class="btn btn-secondary" data-aggiungi="medie" style="padding:4px 9px;font-size:11.5px"><i class="ph ph-plus"></i>Aggiungi riga</button>
    <button class="btn btn-primary" data-azione="salva-medie" data-salva${S.medieSporche ? '' : ' disabled'} style="padding:4px 9px;font-size:11.5px"><i class="ph ph-floppy-disk"></i>Salva</button>
  </div>
  ${medie.errore
    ? `<div class="avviso"><i class="ph-fill ph-warning-circle"></i><div>${esc(medie.errore)}</div></div>`
    : griglia('medie', medie.colonne, righeMedie, { larghezze: { ID: '80px' } })}`;
};

// ---------------------------------------------------------------------------
// Schermata: Attrezzature HAV/WBV (vibrazioni)
// ---------------------------------------------------------------------------

SCHERMATE.attrezzature = function () {
  const a = S.attrezzature;
  if (!a) return '<p class="msub">caricamento…</p>';
  const scheda = S.schedaAttrezzature || 'costruttori';

  const tabelle = {
    costruttori: { titolo: 'datiCostr.xlsx · dati da libretto o banca dati', dati: a.costruttori },
    HAV: { titolo: 'misureHAV.xlsx · misure mano-braccio', dati: a.HAV },
    WBV: { titolo: 'misureWBV.xlsx · misure corpo intero', dati: a.WBV },
  };
  const corrente = tabelle[scheda];
  const dati = corrente.dati || { colonne: [], righe: [], errore: 'non disponibile' };

  const linguetta = (chiave, etichetta) => {
    const d = tabelle[chiave].dati || {};
    const n = (d.righe || []).length;
    return `<button class="tabx${scheda === chiave ? ' on' : ''}" data-scheda-attr="${chiave}">${etichetta}
      <span class="mono" style="margin-left:6px;opacity:.55">${d.errore ? '—' : n}</span></button>`;
  };

  return `
  ${bandaMessaggio()}
  ${intestazione('Attrezzature HAV/WBV',
      'Dati di ingresso delle vibrazioni: si scrivono nelle stesse celle da cui sono stati letti',
      `<button class="btn btn-primary" data-azione="salva-attrezzature" data-salva${S.attrezzatureSporche[scheda] ? '' : ' disabled'}><i class="ph ph-floppy-disk"></i>Salva modifiche</button>`)}

  <div style="display:flex;gap:2px;border-bottom:1px solid var(--color-divider)">
    ${linguetta('costruttori', 'Dati costruttori')}${linguetta('HAV', 'Misure HAV')}${linguetta('WBV', 'Misure WBV')}
  </div>

  <div style="display:flex;align-items:center;gap:8px">
    <p class="sec" style="flex:1">${esc(corrente.titolo)}</p>
    <span class="mono" style="font-size:11px;color:color-mix(in srgb,var(--color-text) 40%,transparent);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:340px;direction:rtl">${esc(dati.percorso || '')}</span>
    ${dati.errore ? '' : `<button class="btn btn-secondary" data-aggiungi="${scheda}" style="padding:4px 9px;font-size:11.5px"><i class="ph ph-plus"></i>Aggiungi riga</button>`}
  </div>

  ${dati.errore
    ? `<div class="avviso"><i class="ph-fill ph-warning-circle"></i><div>${esc(dati.errore)}
        ${scheda !== 'costruttori' ? ' Le misure di questo tipo verranno cercate solo in datiCostr.xlsx.' : ''}</div></div>`
    : griglia(scheda, dati.colonne, dati.righe, {
        solaLettura: dati.sola_lettura || [],
        larghezze: { ID: '80px', foto: '70px' },
      })}`;
};

// ---------------------------------------------------------------------------
// Schermata: Esposizioni A(8) (vibrazioni)
// ---------------------------------------------------------------------------

SCHERMATE.esposizioni = function () {
  const v = S.risultatiVibrazioni;
  if (!v || !v.disponibile) {
    return intestazione('Esposizioni A(8)', 'nessun risultato disponibile')
      + `<div class="avviso"><i class="ph-fill ph-warning-circle"></i><div>Esegui l'analisi delle vibrazioni: i risultati vengono letti da VR_VIB.xlsx.</div></div>`;
  }
  const pv = S.parametriVibrazioni;

  const lato = (g, tipo) => {
    const d = g[tipo] || {};
    if (!d.presente) return `<td colspan="4" style="opacity:.35;font-size:11.5px">non esposto</td>`;
    return `<td class="mono">${esc(d.a8)}</td><td class="mono" style="opacity:.6">± ${esc(d.ua8)}</td>
      <td class="mono">${esc(d.a8max)}</td>
      <td><span class="tag" style="color:${d.colore};box-shadow:inset 0 0 0 1px ${d.colore}66">${esc(d.classe)}</span></td>`;
  };

  const avvisi = [];
  for (const g of v.gruppi) {
    for (const tipo of ['HAV', 'WBV']) {
      const e = (g[tipo] || {}).errore;
      if (e) avvisi.push(`GrOm ${g.code} · ${tipo}: ${e}`);
    }
  }

  return `
  ${intestazione('Esposizioni A(8)',
      `${v.gruppi.length} gruppi omogenei esposti · soglie HAV ${pv.SOGLIA_MEDIA_HAV}/${pv.SOGLIA_ALTA_HAV} · WBV ${pv.SOGLIA_MEDIA_WBV}/${pv.SOGLIA_ALTA_WBV} m/s²`,
      `<span class="tag">${v.fonte === 'json' ? 'da riepilogo dell\'analisi' : 'riletto da VR_VIB.xlsx'}</span>`)}

  <div style="display:flex;gap:14px">
    ${['HAV', 'WBV'].map((tipo) => `
      <div class="card elev-sm" style="flex:1;padding:10px 12px;gap:7px">
        <div class="sec">${tipo}</div>
        <div style="display:flex;gap:12px">
          ${[['ALTA', '#b22222'], ['MEDIA', '#00bfff'], ['BASSA', '#32cd32']].map(([c, colore]) => `
            <span style="display:flex;align-items:center;gap:6px;font-size:12px">
              <span style="width:8px;height:8px;border-radius:50%;background:${colore}"></span>${c}
              <span class="mono" style="opacity:.6">${v.conteggi[tipo][c] || 0}</span></span>`).join('')}
        </div></div>`).join('')}
  </div>

  <div class="scroll-tab" style="flex:1"><table>
    <thead>
      <tr><th rowspan="2">GrOm</th><th rowspan="2">Gruppo omogeneo</th>
          <th colspan="4" style="text-align:center;border-left:1px solid var(--color-divider)">HAV — mano-braccio</th>
          <th colspan="4" style="text-align:center;border-left:1px solid var(--color-divider)">WBV — corpo intero</th></tr>
      <tr><th style="border-left:1px solid var(--color-divider)">A(8)</th><th>UA(8)</th><th>A(8) MAX</th><th>Classe</th>
          <th style="border-left:1px solid var(--color-divider)">A(8)</th><th>UA(8)</th><th>A(8) MAX</th><th>Classe</th></tr>
    </thead>
    <tbody>${v.gruppi.map((g) => `<tr>
      <td class="mono" style="opacity:.55">${esc(g.code)}</td><td>${esc(g.nome)}</td>
      ${lato(g, 'HAV')}${lato(g, 'WBV')}</tr>`).join('')}</tbody>
  </table></div>

  ${avvisi.length ? `<div class="avviso"><i class="ph-fill ph-warning-circle"></i>
    <div>${avvisi.map((a) => `<div>${esc(a)}</div>`).join('')}</div></div>` : ''}`;
};

// ---------------------------------------------------------------------------
// Schermata: Relazione Word
// ---------------------------------------------------------------------------

SCHERMATE.relazione = function () {
  const r = S.relazione;
  const dati = r.dati || { tabella_dpi: [], tabella_HEG: [], tabella_vibrazioni: [],
                           colonne_dpi: [], colonne_heg: [], colonne_vib: [] };
  const scheda = r.scheda;

  const gruppi = {};
  for (const campo of S.campiRelazione) {
    (gruppi[campo.gruppo] = gruppi[campo.gruppo] || []).push(campo);
  }

  const modulo = Object.entries(gruppi).map(([nome, campi]) => `
    <div class="card elev-sm" style="padding:11px 13px;gap:9px">
      <p class="sec">${esc(nome)}</p>
      ${campi.map((c) => `
        <div class="field"><label>${esc(c.etichetta)}</label>
          <input class="input" style="font-size:12.5px" data-campo-relazione="${c.chiave}" value="${esc(r.campi[c.chiave] || '')}"></div>`).join('')}
    </div>`).join('');

  const tabellaSolaLettura = (colonne, righe) => `
    <div class="scroll-tab"><table>
      <thead><tr>${colonne.map((c) => `<th>${esc(c)}</th>`).join('')}</tr></thead>
      <tbody>${righe.map((riga) => `<tr>${colonne.map((c) => `<td class="mono">${esc(riga[c])}</td>`).join('')}</tr>`).join('')
        || `<tr><td colspan="${colonne.length}" style="padding:14px;color:color-mix(in srgb,var(--color-text) 45%,transparent)">nessun dato: esegui prima l'analisi</td></tr>`}</tbody>
    </table></div>`;

  let corpo;
  if (scheda === 'generali') {
    corpo = `<div style="display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:12px;overflow-y:auto;flex:1;align-content:start">${modulo}</div>
      <div style="font-size:11.5px;color:color-mix(in srgb,var(--color-text) 50%,transparent)">
        Il quadro sinottico con le classi di rischio viene inserito automaticamente nelle conclusioni: ${esc(dati.frase_presenza || '—')}</div>`;
  } else if (scheda === 'dpi') {
    corpo = tabellaSolaLettura(dati.colonne_dpi, dati.tabella_dpi);
  } else if (scheda === 'heg') {
    corpo = tabellaSolaLettura(dati.colonne_heg, dati.tabella_HEG);
  } else {
    corpo = tabellaSolaLettura(dati.colonne_vib, dati.tabella_vibrazioni);
  }

  const linguetta = (chiave, etichetta) =>
    `<button class="tabx${scheda === chiave ? ' on' : ''}" data-scheda-relazione="${chiave}">${etichetta}</button>`;

  return `
  ${bandaMessaggio()}
  ${intestazione('Dati per la relazione',
      `Modello <span class="mono">${esc(nomeBase(S.config.modello_relazione_rumore) || '—')}</span>`,
      `<div style="display:flex;gap:6px">
        <button class="btn btn-secondary" data-azione="carica-preset"><i class="ph ph-upload-simple"></i>Carica</button>
        <button class="btn btn-secondary" data-azione="salva-preset"><i class="ph ph-floppy-disk"></i>Salva</button>
        <button class="btn btn-primary" data-azione="genera-documento"><i class="ph ph-file-doc"></i>Genera documento</button>
      </div>`)}

  ${r.messaggio ? `<div class="avviso"><i class="ph-fill ph-warning-circle"></i><div>${esc(r.messaggio)}</div></div>` : ''}

  <div style="display:flex;gap:2px;border-bottom:1px solid var(--color-divider)">
    ${linguetta('generali', 'Dati generali')}${linguetta('dpi', 'Tabella DPI')}
    ${linguetta('heg', 'Tabella HEG')}${linguetta('vib', 'Tabella vibrazioni')}
  </div>
  ${corpo}`;
};

// ---------------------------------------------------------------------------
// Caricamenti
// ---------------------------------------------------------------------------

async function caricaSchede() {
  S.schede = await chiama('leggi_schede', { t0: S.parametriRumore.T0 });
  S.schedeSporche = false;
}

async function caricaRisultatiRumore() {
  S.risultatiRumore = await chiama('risultati_rumore', { parametri: S.parametriRumore });
}

async function caricaMisure() {
  S.misure = await chiama('misure_singole', {});
  S.medieSporche = false;
}

async function caricaAttrezzature() {
  S.attrezzature = await chiama('leggi_attrezzature', {});
  S.attrezzatureSporche = {};
}

async function caricaRisultatiVibrazioni() {
  S.risultatiVibrazioni = await chiama('risultati_vibrazioni', {});
}

async function caricaRelazione() {
  S.relazione.dati = await chiama('relazione_dati', { campi: S.relazione.campi });
}

async function ricaricaTutto() {
  S.schede = null; S.risultatiRumore = null; S.misure = null;
  S.attrezzature = null; S.risultatiVibrazioni = null; S.relazione.dati = null;
  await caricaRisultatiRumore();
  await caricaRisultatiVibrazioni();
}

// ---------------------------------------------------------------------------
// Azioni
// ---------------------------------------------------------------------------

suInput('#campo-root', (nodo) => { S.root = nodo.value; });

suClic('[data-azione="apri-picker"]', () => {
  const partenza = S.root || S.config.cartella_lavori || '';
  apriModale('cartella', partenza, 'Seleziona la cartella dell\'azienda', async (scelta) => {
    S.root = scelta;
    await scansiona();
  });
});

suClic('[data-azione="dialogo-cartella"]', async () => {
  const esito = await chiama('dialogo_cartella', { percorso: S.root || S.config.cartella_lavori });
  if (esito.percorso) { S.root = esito.percorso; await scansiona(); }
});

suClic('[data-azione="scansiona"]', () => scansiona());

async function scansiona() {
  const esito = await chiama('scansiona', { root: S.root });
  S.scansione = esito;
  if (esito.valida) {
    S.modalita = esito.modalita_suggerita;
    await ricaricaTutto();
    messaggio(`Cartella aperta: ${nomeBase(esito.root)} · modalita' ${S.modalita}`, 'ok');
  } else {
    S.risultatiRumore = S.risultatiVibrazioni = null;
    messaggio(esito.errore || 'Cartella non utilizzabile.', 'errore');
  }
  disegna();
}

suModifica('[data-modalita]', async (nodo) => {
  S.modalita = nodo.value;
  const voci = vociVisibili().map(([c]) => c);
  if (!voci.includes(S.schermata)) S.schermata = 'cartelle';
  await chiama('salva_parametri', { config: { modalita: S.modalita } });
  disegna();
});

function leggiParametro(nodo) {
  if (nodo.type === 'checkbox') return nodo.checked;
  if (nodo.type === 'radio') return nodo.value;
  const numero = Number(String(nodo.value).replace(',', '.'));
  return nodo.value !== '' && !isNaN(numero) ? numero : nodo.value;
}

suModifica('[data-par-rumore]', async (nodo) => {
  S.parametriRumore[nodo.dataset.parRumore] = leggiParametro(nodo);
  await chiama('salva_parametri', { rumore: S.parametriRumore });
  if (nodo.dataset.parRumore === 'T0' && S.schede) { ricalcolaTempi(); disegna(); }
});

suModifica('[data-par-vib]', async (nodo) => {
  S.parametriVibrazioni[nodo.dataset.parVib] = leggiParametro(nodo);
  await chiama('salva_parametri', { vibrazioni: S.parametriVibrazioni });
});

// ---- schede ----
suClic('[data-azione="ricarica-schede"]', async () => { await caricaSchede(); disegna(); });

suClic('[data-azione="scegli-scheda"]', () => {
  const partenza = S.schede && S.schede.percorso
    ? S.schede.percorso.replace(/\/[^/]*$/, '') : S.root;
  apriModale('file', partenza, 'Seleziona la scheda dei gruppi', async (scelta) => {
    await chiama('imposta_file', { chiave: 'scheda', percorso: scelta });
    await caricaSchede();
    disegna();
  });
});

suClic('[data-azione="salva-schede"]', async () => {
  const esito = await chiama('salva_schede', {
    dpi: S.schede.dpi.righe, mansioni: S.schede.mansioni.righe,
    colonne_dpi: S.schede.dpi.colonne, colonne_mansioni: S.schede.mansioni.colonne,
  });
  if (esito.ok) { S.schedeSporche = false; messaggio('Schede salvate. Copia di sicurezza in .bak', 'ok'); }
  else messaggio(esito.errore || 'Salvataggio non riuscito.', 'errore');
});

// ---- misure ----
suInput('[data-query-misure]', (nodo) => {
  S.queryMisure = nodo.value;
  const posizione = nodo.selectionStart;
  disegna();
  const nuovo = document.querySelector('[data-query-misure]');
  if (nuovo) { nuovo.focus(); nuovo.setSelectionRange(posizione, posizione); }
});
suModifica('[data-ragg]', (nodo) => { S.misurePiatte = nodo.value === 'piatto'; disegna(); });

suClic('[data-azione="salva-medie"]', async () => {
  const colonne = S.misure.medie.colonne;
  const righe = S.misure.medie.righe.map((r) => {
    const oggetto = {};
    for (const c of colonne) oggetto[c] = r[c];
    return oggetto;
  });
  const esito = await chiama('salva_medie', { righe });
  if (esito.ok) { S.medieSporche = false; messaggio('Valori misurati salvati in averaged_data.csv', 'ok'); }
  else messaggio(esito.errore || 'Salvataggio non riuscito.', 'errore');
});

// ---- superamenti ----
suModifica('[data-vista-sup]', (nodo) => { S.vistaSuperamenti = nodo.value; disegna(); });
suModifica('[data-solo-alta]', (nodo) => { S.soloAlta = nodo.checked; disegna(); });
suClic('[data-gruppo]', (nodo) => {
  S.gruppoScelto = nodo.dataset.gruppo;
  S.vistaSuperamenti = 'dettaglio';
  disegna();
});

// ---- attrezzature ----
suClic('[data-scheda-attr]', (nodo) => { S.schedaAttrezzature = nodo.dataset.schedaAttr; disegna(); });
suClic('[data-azione="salva-attrezzature"]', async () => {
  const quale = S.schedaAttrezzature || 'costruttori';
  const dati = S.attrezzature[quale];
  const esito = await chiama('salva_attrezzature', { quale, righe: dati.righe });
  if (esito.ok) { S.attrezzatureSporche[quale] = false; messaggio('Dati salvati. Copia di sicurezza in .bak', 'ok'); }
  else messaggio(esito.errore || 'Salvataggio non riuscito.', 'errore');
});

// ---- log ----
suModifica('[data-filtro-log]', (nodo) => { S.esecuzione.filtro = nodo.value; disegna(); });
suClic('[data-azione="coda"]', () => { S.esecuzione.coda = !S.esecuzione.coda; disegna(); });
suClic('[data-azione="pulisci-log"]', () => { S.esecuzione.righe = []; disegna(); });

// ---- relazione ----
suClic('[data-scheda-relazione]', (nodo) => { S.relazione.scheda = nodo.dataset.schedaRelazione; disegna(); });
suInput('[data-campo-relazione]', (nodo) => { S.relazione.campi[nodo.dataset.campoRelazione] = nodo.value; });

suClic('[data-azione="salva-preset"]', async () => {
  const nome = nomeBase(S.scansione && S.scansione.root) || 'preset';
  await chiama('relazione_preset', { operazione: 'salva', nome, dati: S.relazione.campi });
  messaggio(`Dati della relazione salvati come «${nome}»`, 'ok');
});

suClic('[data-azione="carica-preset"]', async () => {
  const elenco = await chiama('relazione_preset', { operazione: 'elenco' });
  const preset = elenco.preset || [];
  if (!preset.length) { messaggio('Nessun preset salvato.', 'avviso'); return; }
  const nome = nomeBase(S.scansione && S.scansione.root);
  const scelto = preset.includes(nome) ? nome : preset[0];
  const esito = await chiama('relazione_preset', { operazione: 'carica', nome: scelto });
  S.relazione.campi = esito.dati || {};
  await caricaRelazione();
  messaggio(`Caricato il preset «${scelto}»`, 'ok');
  disegna();
});

suClic('[data-azione="genera-documento"]', async () => {
  const esito = await chiama('relazione_genera', { campi: S.relazione.campi });
  S.relazione.messaggio = esito.messaggio || '';
  disegna();
});

// ---- esecuzione ----
suClic('[data-azione="avvia"]', () => avvia(false));
suClic('[data-azione="ferma"]', async () => { await chiama('interrompi', {}); });

async function avvia(ignoraTempi) {
  if (S.schedeSporche) {
    messaggio('Ci sono modifiche non salvate nelle schede: salvale prima di avviare.', 'avviso');
    return;
  }
  const esito = await chiama('avvia', {
    modalita: S.modalita,
    rileggi_misure: !!S.parametriRumore.rileggi_misure,
    ignora_tempi: ignoraTempi,
  });
  if (!esito.ok) {
    if (esito.tempi) {
      S.schede = S.schede || {};
      S.schede.tempi = esito.tempi;
      S.schermata = 'schede';
      await caricaSchede();
      S.schede.tempi = esito.tempi;
    }
    messaggio(esito.errore || 'Avvio non riuscito.', 'errore');
    disegna();
    return;
  }
  S.esecuzione.inCorso = true;
  S.schermata = 'log';
  disegna();
}

// ---------------------------------------------------------------------------
// Eventi dell'analisi
// ---------------------------------------------------------------------------

function aggiungiRiga(livello, msg) {
  const righe = S.esecuzione.righe;
  righe.push({ t: ora(), livello: livello || 'info', msg });
  // il log di una lettura misure puo' essere lungo: si tiene la coda
  if (righe.length > MAX_RIGHE_LOG) righe.splice(0, righe.length - MAX_RIGHE_LOG);
}

function scorriInFondo() {
  if (!S.esecuzione.coda) return;
  const contenitore = el('log-righe');
  if (contenitore) contenitore.scrollTop = contenitore.scrollHeight;
}

async function riceviEvento(evento) {
  const e = S.esecuzione;
  switch (evento.tipo) {
    case 'avvio':
      e.inCorso = true;
      e.inizio = Date.now();
      e.durata = undefined;
      e.passi = (evento.passi || []).map((p) => ({ ...p, stato: 'attesa', msg: '' }));
      aggiungiRiga('info', `Avvio analisi · modalita' ${evento.modalita || ''}`);
      break;

    case 'passo': {
      // i runner numerano i passi con continuita' anche in modalita' combinata
      const indice = (evento.indice || 1) - 1;
      const passo = e.passi[indice];
      if (passo) {
        passo.stato = evento.stato;
        passo.msg = evento.msg || '';
        if (evento.nome) passo.nome = evento.nome;
      }
      if (evento.stato === 'corso') aggiungiRiga('info', `▸ ${evento.nome}`);
      if (evento.stato === 'errore') aggiungiRiga('error', `✕ ${evento.nome}: ${evento.msg || ''}`);
      if (evento.stato === 'saltato') aggiungiRiga('warning', `− ${evento.nome} saltato`);
      break;
    }

    case 'log':
      aggiungiRiga(evento.livello, evento.msg);
      break;

    case 'interrotta':
      aggiungiRiga('warning', 'Analisi interrotta su richiesta.');
      for (const p of e.passi) if (p.stato === 'corso') p.stato = 'errore';
      break;

    case 'fine':
      e.inCorso = false;
      e.durata = evento.durata;
      aggiungiRiga(evento.ok ? 'info' : 'error',
        evento.ok ? `Analisi conclusa in ${evento.durata} s` : 'Analisi conclusa con errori');
      await ricaricaTutto();
      messaggio(evento.ok ? `Analisi conclusa in ${evento.durata} s`
                          : 'Analisi conclusa con errori: controlla il log',
                evento.ok ? 'ok' : 'errore');
      break;

    default:
      break;
  }
  disegna();
  scorriInFondo();
}

// ---------------------------------------------------------------------------
// Avvio
// ---------------------------------------------------------------------------

async function inizializza() {
  const stato = await chiama('stato_iniziale', {});
  S.config = stato.config || {};
  S.parametriRumore = stato.parametri_rumore || {};
  S.parametriVibrazioni = stato.parametri_vibrazioni || {};
  S.recenti = stato.recenti || [];
  S.campiRelazione = stato.campi_relazione || [];
  S.passiPerModalita = stato.passi || {};
  S.relazione.messaggio = (stato.relazione || {}).messaggio || '';
  S.modalita = S.config.modalita || 'rumore';
  S.root = S.config.ultima_root || '';

  disegna();
  if (S.root) await scansiona();
}

new QWebChannel(qt.webChannelTransport, (canale) => {
  ponte = canale.objects.ponte;
  ponte.evento.connect((testo) => {
    let evento;
    try { evento = JSON.parse(testo); } catch (err) { return; }
    riceviEvento(evento);
  });
  while (inAttesaDelPonte.length) inAttesaDelPonte.shift()();
  inizializzaBarra();
  inizializza();
});
