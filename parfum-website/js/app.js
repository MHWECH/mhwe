/* Duftsammlung — kleine Vanilla-JS-Anwendung, kein Build noetig. */

const $ = (sel) => document.querySelector(sel);

const el = {
  titel:    $('#titel'),
  unter:    $('#untertitel'),
  stand:    $('#stand'),
  suche:    $('#suche'),
  filter:   $('#markenfilter'),
  zaehler:  $('#zaehler'),
  raster:   $('#raster'),
  leer:     $('#leer'),
  fehler:   $('#fehler'),
  overlay:  $('#overlay'),
  detail:   $('#detail'),
  schliessen: $('#schliessen'),
};

let alle = [];
let markeAktiv = 'alle';
let suchtext = '';
let letzterFokus = null;

// ── Laden ────────────────────────────────────────────────────
fetch('data/parfums.json')
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((daten) => {
    alle = daten.parfums || [];
    const meta = daten.meta || {};
    if (meta.titel) { el.titel.textContent = meta.titel; document.title = meta.titel; }
    el.unter.textContent = meta.untertitel || '';
    el.stand.textContent = formatDatum(meta.stand);
    baueFilter();
    zeichne();
  })
  .catch(() => { el.fehler.hidden = false; });

function formatDatum(iso) {
  if (!iso) return '—';
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleDateString('de-CH', { day: '2-digit', month: 'long', year: 'numeric' });
}

// ── Filter ───────────────────────────────────────────────────
function baueFilter() {
  const marken = [...new Set(alle.map((p) => p.marke))].sort((a, b) => a.localeCompare(b, 'de'));
  ['alle', ...marken].forEach((marke) => {
    const b = document.createElement('button');
    b.className = 'chip';
    b.type = 'button';
    b.textContent = marke === 'alle' ? 'Alle' : marke;
    b.setAttribute('aria-pressed', String(marke === markeAktiv));
    b.addEventListener('click', () => {
      markeAktiv = marke;
      [...el.filter.children].forEach((c) => c.setAttribute('aria-pressed', String(c === b)));
      zeichne();
    });
    el.filter.appendChild(b);
  });
}

el.suche.addEventListener('input', (e) => {
  suchtext = e.target.value.trim().toLowerCase();
  zeichne();
});

function gefiltert() {
  return alle.filter((p) => {
    const passtMarke = markeAktiv === 'alle' || p.marke === markeAktiv;
    const heuhaufen = `${p.marke} ${p.name} ${p.duftfamilie || ''}`.toLowerCase();
    return passtMarke && heuhaufen.includes(suchtext);
  });
}

// ── Raster zeichnen ──────────────────────────────────────────
function zeichne() {
  const liste = gefiltert();
  el.raster.innerHTML = '';

  liste.forEach((p) => {
    const karte = document.createElement('button');
    karte.className = 'karte';
    karte.type = 'button';
    karte.innerHTML = `
      <div class="karte-bild">
        <img src="assets/img/thumb/${p.bilder[0]}.jpg" alt="Flakon ${p.marke} ${p.name}" loading="lazy" width="450" height="600">
      </div>
      <div class="karte-text">
        <p class="karte-marke">${esc(p.marke)}</p>
        <h2 class="karte-name">${esc(p.name)}</h2>
        <p class="karte-meta">${esc(p.konzentration || '')}${p.groesse_ml ? ' &middot; ' + p.groesse_ml + ' ml' : ''}</p>
      </div>`;
    karte.addEventListener('click', () => oeffne(p));
    el.raster.appendChild(karte);
  });

  el.leer.hidden = liste.length > 0;
  el.zaehler.textContent = `${liste.length} von ${alle.length}`;
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

// ── Detailansicht ────────────────────────────────────────────
function oeffne(p) {
  letzterFokus = document.activeElement;
  el.detail.innerHTML = `
    <div class="detail-bilder">
      ${p.bilder.map((b) => `<img src="assets/img/${b}.jpg" alt="Flakon ${esc(p.marke)} ${esc(p.name)}" loading="lazy">`).join('')}
    </div>
    <div class="detail-text">
      <p class="detail-marke">${esc(p.marke)}</p>
      <h2 id="detail-titel">${esc(p.name)}</h2>
      <dl class="detail-fakten">
        ${zeile('Art', esc(p.konzentration))}
        ${zeile('Grösse', p.groesse_ml ? p.groesse_ml + ' ml' : '')}
        ${zeile('Duftfamilie', esc(p.duftfamilie))}
        ${zeile('Kopfnote', liste(p.duftnoten?.kopf))}
        ${zeile('Herznote', liste(p.duftnoten?.herz))}
        ${zeile('Basisnote', liste(p.duftnoten?.basis))}
        ${zeile('Anlass', liste(p.anlass))}
        ${zeile('Jahreszeit', liste(p.jahreszeit))}
        ${zeile('Bewertung', p.bewertung ? '&#9733;'.repeat(p.bewertung) : '')}
        ${zeile('Notiz', esc(p.beschreibung))}
      </dl>
    </div>`;
  el.overlay.hidden = false;
  document.body.style.overflow = 'hidden';
  el.schliessen.focus();
}

function liste(arr) {
  return Array.isArray(arr) && arr.length ? arr.map(esc).join(', ') : '';
}

function zeile(label, wert) {
  const inhalt = wert ? wert : '<span class="offen">noch offen</span>';
  return `<div><dt>${label}</dt><dd>${inhalt}</dd></div>`;
}

function schliesse() {
  el.overlay.hidden = true;
  document.body.style.overflow = '';
  if (letzterFokus) letzterFokus.focus();
}

el.schliessen.addEventListener('click', schliesse);
el.overlay.addEventListener('click', (e) => { if (e.target === el.overlay) schliesse(); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && !el.overlay.hidden) schliesse(); });
