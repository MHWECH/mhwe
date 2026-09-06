# Duftsammlung — Website

Statische Website fuer die Parfum-Sammlung. Kein Build, kein Framework,
keine Datenbank: HTML, CSS und ein bisschen JavaScript. Laeuft auf jedem
Webserver — auch auf einem einfachen Hosting-Paket oder GitHub Pages.

## Starten

```bash
./start.sh
```

Danach im Browser `http://localhost:8080` oeffnen.

Wichtig: Die Seite braucht einen Webserver. Ein Doppelklick auf
`index.html` funktioniert nicht, weil der Browser die Datei
`data/parfums.json` dann aus Sicherheitsgruenden blockiert.

## Aufbau

```
parfums/
├── index.html              Seitengeruest
├── css/style.css           Gestaltung (dunkel, Gold-Akzente)
├── js/app.js               Laden, Suche, Filter, Detailansicht
├── data/parfums.json       ← hier werden die Daten gepflegt
└── assets/img/
    ├── *.jpg               grosse Bilder (max. 1600 px)
    └── thumb/*.jpg         kleine Bilder fuer das Raster
```

## Daten pflegen

Alles Inhaltliche steht in **`data/parfums.json`**. Am Code muss dafuer
nichts geaendert werden.

Felder pro Parfum:

| Feld            | Bedeutung                                                    |
|-----------------|--------------------------------------------------------------|
| `id`            | eindeutiger Kurzname, gleich wie der Bild-Dateiname           |
| `marke`         | Hersteller, erscheint auch als Filter-Knopf                   |
| `name`          | Name des Dufts                                                |
| `konzentration` | z.B. `Eau de Parfum`, `Extrait de Parfum`                     |
| `groesse_ml`    | Zahl oder `null`                                              |
| `duftfamilie`   | z.B. `holzig`, `orientalisch` — leer lassen ist erlaubt       |
| `duftnoten`     | `kopf`, `herz`, `basis` — je eine Liste von Begriffen         |
| `beschreibung`  | eigene Notiz, freier Text                                     |
| `bewertung`     | `1` bis `5` (Sterne) oder `null`                              |
| `anlass`        | Liste, z.B. `["Abend", "Buero"]`                              |
| `jahreszeit`    | Liste, z.B. `["Herbst", "Winter"]`                            |
| `bilder`        | Liste von Bildnamen ohne `.jpg` — das erste ist das Titelbild |
| `im_regal`      | `true` / `false`                                              |

Leere Felder zeigt die Detailansicht als *noch offen* an. **Duftnoten und
Beschreibungen sind bewusst leer** — dort steht nichts Erfundenes drin,
das gehoert selbst ergaenzt.

## Neues Parfum aufnehmen

1. Foto machen und als JPEG speichern:
   - `assets/img/<id>.jpg` — lange Kante max. 1600 px
   - `assets/img/thumb/<id>.jpg` — lange Kante max. 800 px
2. In `data/parfums.json` einen neuen Block ergaenzen (einen bestehenden
   kopieren und anpassen ist am schnellsten).
3. Seite neu laden — fertig.

## Veroeffentlichen

Zieladresse: **https://mhwe.services/parfums**

Alle Pfade in der Seite sind relativ, sie laeuft daher unter jedem
Unterpfad ohne Anpassung. Die konkreten Schritte je nach Hosting stehen
in **[DEPLOY.md](DEPLOY.md)**.
