# Veroeffentlichen auf mhwe.services/parfums

Die Seite ist rein statisch und braucht **kein PHP, kein Python und keine
Datenbank**. Alle Pfade sind relativ, sie laeuft daher unter jedem
Unterpfad, ohne dass am Code etwas geaendert werden muss.

---

## Firebase Hosting

### Das Wichtigste zuerst

Firebase Hosting **ersetzt bei jedem Deploy die gesamte Seite** durch den
Inhalt des Ordners `public/`. Es gibt kein "nur diesen Unterordner
hochladen".

Und: Firebase kann `/parfums` **nicht** auf eine andere Hosting-Site
umleiten. Rewrites koennen nur auf einen Pfad, eine Cloud Function oder
Cloud Run zeigen — nicht auf eine zweite Hosting-Site.

Daraus folgt: Die Duftsammlung muss zusammen mit der bestehenden
Startseite in **einem** Deploy ausgeliefert werden.

Davor schuetzt `build.sh` — es bricht ab, wenn die Startseite fehlt.

### Einmalige Einrichtung

```bash
npm install -g firebase-tools
firebase login
firebase projects:list          # zeigt die Projekt-ID
```

Die Projekt-ID in `.firebaserc` eintragen, anstelle von
`HIER-FIREBASE-PROJEKT-ID-EINTRAGEN`.

### Fall A — mhwe.services wird aus diesem Repository deployt

Die Dateien der heutigen Startseite in den Ordner `site/` legen:

```
mhwe/
├── site/               ← bestehende Startseite (index.html usw.)
├── parfums/            ← die Duftsammlung
├── firebase.json
└── build.sh, deploy.sh
```

Dann:

```bash
./deploy.sh
```

Das Skript baut daraus:

```
public/
├── index.html          → mhwe.services/
└── parfums/            → mhwe.services/parfums
```

und deployt. `site/` und `public/` sind in `.gitignore` — die bestehende
Startseite landet also nicht mit im Repository.

### Fall B — mhwe.services wird woanders deployt

Der einfachere Weg, wenn die Startseite schon ein eigenes Firebase-Projekt
oder -Verzeichnis hat:

```bash
cp -r parfums /pfad/zum/anderen/projekt/public/parfums
cd /pfad/zum/anderen/projekt
firebase deploy --only hosting
```

Dort ist `parfums/` dann Teil des normalen Deploys. `firebase.json`,
`build.sh` und `deploy.sh` aus diesem Repository werden nicht gebraucht.

Die Cache-Regeln aus `firebase.json` lohnt es sich zu uebernehmen:

```json
"headers": [
  { "source": "/parfums/data/**",
    "headers": [{ "key": "Cache-Control", "value": "no-cache" }] },
  { "source": "/parfums/assets/**",
    "headers": [{ "key": "Cache-Control", "value": "public, max-age=604800" }] }
]
```

`no-cache` fuer `data/` sorgt dafuer, dass Aenderungen an der Sammlung
sofort sichtbar sind. Die Fotos werden eine Woche zwischengespeichert.

### Vorher anschauen, ohne zu veroeffentlichen

```bash
./build.sh
npx firebase-tools emulators:start --only hosting
```

Zeigt die Seite genau so, wie sie live aussehen wird — ohne dass etwas
veroeffentlicht wird.

### Domain

Ist `mhwe.services` bereits mit dem Projekt verbunden (Firebase-Konsole →
*Hosting* → *Benutzerdefinierte Domain*), ist nach dem Deploy nichts
weiter zu tun. Die Sammlung ist dann unter
`https://mhwe.services/parfums` erreichbar.

---

## Andere Hostings

Falls die Seite doch woanders liegt — der Ordner `parfums/` funktioniert
ueberall gleich.

**Klassisches Webspace (FTP/SFTP):** Ordner `parfums` in das Verzeichnis
mit der bestehenden `index.html` ziehen (`public_html`, `httpdocs` oder
`www`). Fertig.

**Eigener nginx-Server:**

```nginx
location /parfums/ {
    alias /var/www/mhwe/parfums/;
    try_files $uri $uri/ /parfums/index.html;
}
location = /parfums { return 301 /parfums/; }
```

**GitHub Pages:** Der Workflow `.github/workflows/pages.yml` liegt bereit,
absichtlich nur von Hand startbar. Achtung: Pages uebernimmt dann die
ganze Domain, nicht nur den Unterpfad.

---

## Lokal anschauen

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
ein Passwort (bei Firebase ueber Cloud Functions oder Firebase Auth).

Soll die Seite gefunden werden: die Zeile einfach loeschen.
