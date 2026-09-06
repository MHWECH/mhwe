# Veroeffentlichen auf mhwe.services/parfums

Die Seite ist rein statisch. Sie braucht **kein PHP, kein Python und keine
Datenbank** auf dem Server — nur einen Ort, an dem Dateien liegen duerfen.

Alle Pfade in der Seite sind relativ (`css/style.css`, `data/parfums.json`,
`assets/img/...`). Deshalb laeuft sie unter jedem Unterpfad, ohne dass
etwas angepasst werden muss.

Der Ordner heisst `parfums/` — genau so, wie die Adresse spaeter lautet.
Ordner hochladen, fertig.

---

## Variante A — Klassisches Webspace (FTP/SFTP)

Der haeufigste Fall bei Schweizer Anbietern (Hostpoint, Infomaniak, Cyon,
Metanet).

1. Mit dem FTP-Programm (z.B. FileZilla, Cyberduck) auf den Webspace
   verbinden.
2. In das Verzeichnis wechseln, in dem `index.html` der Hauptseite liegt.
   Es heisst je nach Anbieter `public_html`, `httpdocs`, `www` oder `web`.
3. Den kompletten Ordner **`parfums`** dort hineinziehen.

Ergebnis:

```
public_html/
├── index.html          ← bestehende Hauptseite, bleibt unberuehrt
└── parfums/            ← neu
    ├── index.html
    ├── css/  js/  data/
    └── assets/img/
```

Aufrufbar unter `https://mhwe.services/parfums`.

Bei Aenderungen an `data/parfums.json` oder neuen Fotos: nur die
geaenderten Dateien nochmal hochladen.

---

## Variante B — GitHub Pages

Im Repository liegt bereits ein fertiger Workflow:
`.github/workflows/pages.yml`.

Er ist absichtlich **nicht automatisch aktiv**, damit er nicht ins Leere
laeuft, solange Pages nicht eingerichtet ist.

So wird er scharf geschaltet:

1. Auf GitHub unter *Settings → Pages* als Quelle **GitHub Actions**
   waehlen.
2. Unter *Settings → Pages → Custom domain* `mhwe.services` eintragen.
3. Beim DNS-Anbieter der Domain einen `CNAME`-Eintrag auf
   `mhwech.github.io` setzen (bzw. die `A`-Records von GitHub, wenn es
   die Hauptdomain ohne `www` ist).
4. Den Workflow einmal von Hand starten: *Actions → Deploy parfums to
   GitHub Pages → Run workflow*.

Damit er kuenftig bei jedem Push automatisch laeuft, in
`.github/workflows/pages.yml` den auskommentierten `push:`-Block wieder
aktivieren.

Achtung: GitHub Pages uebernimmt dann die **ganze** Domain, nicht nur den
Unterpfad. Das passt nur, wenn mhwe.services ohnehin dort liegt.

---

## Variante C — Eigener Server (nginx)

Ordner nach `/var/www/mhwe/parfums/` kopieren, z.B. mit:

```bash
rsync -av --delete parfums/ user@server:/var/www/mhwe/parfums/
```

Dann in der Server-Konfiguration ergaenzen:

```nginx
location /parfums/ {
    alias /var/www/mhwe/parfums/;
    try_files $uri $uri/ /parfums/index.html;
}

# Ohne Schraegstrich am Ende sauber weiterleiten
location = /parfums {
    return 301 /parfums/;
}
```

Danach `sudo nginx -t && sudo systemctl reload nginx`.

Bei Apache genuegt es meist, den Ordner ins DocumentRoot zu legen — es
braucht keine eigene Konfiguration.

---

## Variante D — Netlify / Vercel

Der Ordner wird als Unterpfad mit ausgeliefert, wenn er im
veroeffentlichten Verzeichnis liegt.

**Netlify** — `netlify.toml` im Repository-Wurzelverzeichnis:

```toml
[build]
  publish = "."
  command = ""
```

**Vercel** — `vercel.json`:

```json
{ "cleanUrls": true }
```

In beiden Faellen die Domain `mhwe.services` im Projekt hinterlegen. Der
Ordner `parfums/` ist dann automatisch unter `/parfums` erreichbar.

---

## Vorher lokal anschauen

```bash
cd parfums
./start.sh          # http://localhost:8080
```

---

## Hinweis zur Sichtbarkeit

In `index.html` steht:

```html
<meta name="robots" content="noindex, nofollow">
```

Damit taucht die Sammlung **nicht** in Google auf — wer die Adresse hat,
sieht sie trotzdem. Ein echter Schutz ist das nicht; dafuer braeuchte es
ein Passwort (bei den meisten Hostings per `.htaccess` einrichtbar).

Soll die Seite gefunden werden: die Zeile einfach loeschen.
