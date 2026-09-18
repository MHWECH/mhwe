# Buchführung — Offline-App für Android

Eine eigenständige Android-App zum Erfassen von Einnahmen und Ausgaben.
Alles läuft **lokal auf dem Gerät**: keine Anmeldung, kein Server, keine Cloud.
Die App hat bewusst **keine `INTERNET`-Berechtigung** im Manifest — sie kann
technisch gar nichts nach draussen senden.

## Funktionen

- **Einnahmen und Ausgaben erfassen** — Datum, Betrag, Kategorie, Text,
  Zahlungsart und optional MwSt-Satz
- **Belege fotografieren** — direkt mit der Kamera oder aus der Galerie; das
  Bild wird app-intern abgelegt und beim Löschen der Buchung mit entfernt
- **Mehrere Mandanten** — getrennte Buchhaltungen, z.B. „Privat" und eine Firma,
  jeweils mit eigener Währung
- **Auswertung** — Summen und Anteile pro Kategorie für Monat oder ganzes Jahr
- **Export** — CSV (Excel-tauglich, Semikolon + UTF-8-BOM) und PDF-Journal im
  A4-Format; danach über das normale Android-Teilen-Fenster verschicken oder
  speichern

Beträge werden intern als ganze Rappen (`Long`) gerechnet — dadurch entstehen
keine Rundungsfehler wie bei Fliesskommazahlen.

## APK bauen

### Über GitHub Actions (kein Setup nötig)

Der Workflow `.github/workflows/android-buchfuehrung.yml` baut die App bei jedem
Push. Das fertige APK landet an zwei Orten:

- **Release** (empfohlen) — direkter Download ohne GitHub-Login:
  <https://github.com/MHWECH/mhwe/releases/tag/buchfuehrung-latest>
- **Actions → der Lauf → Artifacts → `buchfuehrung-debug-apk`** — als ZIP, nur
  eingeloggt herunterladbar

Der Workflow lässt sich auch von Hand starten („Run workflow").

### Lokal

Voraussetzung: JDK 17 und das Android SDK (z.B. via Android Studio).

```bash
cd android-buchfuehrung
./gradlew assembleDebug
```

Das APK liegt danach unter `app/build/outputs/apk/debug/app-debug.apk`.

## Aufs Handy installieren

1. APK aufs Gerät kopieren (USB, Cloud, E-Mail an sich selbst).
2. Beim Antippen fragt Android nach der Erlaubnis, Apps aus dieser Quelle zu
   installieren — bestätigen.
3. Installieren, fertig.

Das Debug-APK ist mit Androids Standard-Debug-Schlüssel signiert und lässt sich
so direkt installieren. Für eine Release-Version (z.B. für den Play Store)
braucht es einen eigenen Signaturschlüssel:

```bash
keytool -genkey -v -keystore buchfuehrung.jks -keyalg RSA \
        -keysize 2048 -validity 10000 -alias buchfuehrung
```

Dieser Schlüssel gehört **nicht** ins Repository.

## Technik

| Bereich | Wahl |
|---|---|
| Sprache | Kotlin |
| Oberfläche | Jetpack Compose, Material 3 |
| Datenbank | Room (SQLite), app-intern |
| PDF | `android.graphics.pdf.PdfDocument` (Bordmittel, keine Bibliothek) |
| minSdk | 26 (Android 8.0) |
| targetSdk / compileSdk | 35 |

### Wo liegen die Daten?

- Datenbank: `/data/data/services.mhwe.buchfuehrung/databases/buchfuehrung.db`
- Belegfotos: `.../files/belege/`
- Exportdateien: `.../cache/export/` (werden vom System bei Bedarf aufgeräumt)

Der Ordner ist für andere Apps nicht lesbar. Ein Gerätewechsel überträgt die
Daten nur über Androids Backup — für alles Wichtige also **regelmässig
exportieren**.
