# Anonymes Abstimmungssystem

Online-Abstimmung für Eigentümerversammlungen – anonym, aber mit gesicherter
Stimmberechtigung und ohne Doppelstimmen.

Aufruf im Admin-Bereich unter **🗳 Abstimmungen** (`/admin/abstimmungen`).

---

## 1. Das Grundproblem und die Lösung

Zwei Anforderungen widersprechen sich auf den ersten Blick:

| Anforderung | Was sie verlangt |
|---|---|
| **Anonymität** | Niemand darf erkennen können, wer wie gestimmt hat – auch die Verwaltung nicht, auch nicht mit Datenbankzugriff. |
| **Legitimation** | Es muss beweisbar sein, dass nur Stimmberechtigte gestimmt haben und niemand zweimal. |

Gelöst wird das mit demselben Prinzip wie bei der Urnenwahl auf Papier:
**Wahlberechtigung und Stimmzettel werden getrennt geführt.**
Der Zugangscode ist der Wahlschein, den der Wahlvorstand entwertet; der
Stimmzettel fällt anonym in die Urne.

```
   Stimmregister                              Urne
   (wer darf, wer hat)                        (was wurde gewählt)
   ─────────────────────                      ────────────────────
   Name                                       Quittungscode
   E-Mail                    KEINE            Stimmen
   Einheit               ← VERBINDUNG →       Stimmgewicht
   Stimmgewicht                               Datum (nur Tag)
   abgestimmt: ja/nein                        Stimmzettel-Hash
   Datum (nur Tag)
```

Zwischen beiden Tabellen existiert kein Fremdschlüssel, keine laufende Nummer
und kein gemeinsamer Zeitstempel. Eine Zuordnung ist auch mit vollem
Datenbankzugriff nicht möglich.

### Die vier technischen Bausteine

**1. Zugangscode nur als Hash gespeichert**
Der 25-stellige Code (ca. 128 Bit Entropie) wird erzeugt, einmal angezeigt bzw.
versendet und danach ausschliesslich als SHA-256-Hash abgelegt. Er ist weder
erratbar noch aus der Datenbank rekonstruierbar. Die Verwaltung kann einen Code
deshalb auch nicht nachträglich einsehen und nicht heimlich mitverwenden.

**2. Zwei unabhängige Sperren gegen Doppelstimmen**
Bei der Stimmabgabe laufen in einer einzigen Transaktion zwei bedingte
Aktualisierungen:

```sql
UPDATE election_tokens SET used_on = ? WHERE id = ? AND used_on IS NULL AND revoked = 0
UPDATE election_voters SET voted   = 1 WHERE id = ? AND voted   = 0
```

Trifft eine von beiden nicht genau eine Zeile, wird alles zurückgerollt und
kein Stimmzettel erzeugt. Damit sind auch Doppelklicks, zurückgeschickte
Formulare und parallele Anfragen abgedeckt.

**3. Zeitstempel bewusst nur tagesgenau**
Der häufigste Fehler in selbstgebauten Abstimmungssystemen: Person X wird um
14:03:22 als „hat abgestimmt" markiert, und um 14:03:22 landet ein Stimmzettel
in der Urne – die Anonymität ist rechnerisch aufgehoben. Deshalb speichern
sowohl Präsenzliste als auch Urne **nur das Datum**. Alle Listen und Exporte
sind nach Quittungscode sortiert, nie nach Eingangsreihenfolge.

**4. Beweissicherung durch Hashketten**

* **Protokoll:** Jeder Verwaltungsvorgang wird protokolliert; jeder Eintrag
  enthält den Hash seines Vorgängers. Wird ein Eintrag nachträglich geändert,
  eingefügt oder gelöscht, bricht die Kette und das System zeigt es an.
* **Stimmzettel-Hash:** Jeder Stimmzettel trägt eine Prüfsumme über seinen
  Inhalt.
* **Urnen-Fingerabdruck:** Beim Schliessen der Abstimmung wird eine
  Gesamtprüfsumme über alle Stimmzettel berechnet und eingefroren. Sie ändert
  sich, sobald auch nur ein Stimmzettel nachträglich hinzukommt, verschwindet
  oder verändert wird. Der Fingerabdruck gehört ins Versammlungsprotokoll.

### Was die Stimmberechtigten selbst prüfen können

Nach der Stimmabgabe erhält jede Person einen **Quittungscode** (z. B.
`K7F2-9QMX`). Nach Veröffentlichung des Ergebnisses findet sie ihn auf der
öffentlichen Verifikationsseite wieder und weiss damit: *meine Stimme liegt
unverändert in der Urne und wurde mitgezählt.* Der Code lässt keinen Rückschluss
auf die Person zu.

Das ist der entscheidende Punkt für die rechtliche Belastbarkeit: Das Ergebnis
muss nicht geglaubt werden, es ist **von jeder einzelnen Person überprüfbar**.

---

## 2. Ablauf einer Abstimmung

### Schritt 1 – Abstimmung anlegen

Admin → Abstimmungen → Titel eingeben, z. B. „Ordentliche
Eigentümerversammlung Villas Tropimar 2026".

### Schritt 2 – Rahmendaten festlegen

| Einstellung | Bedeutung |
|---|---|
| **Zeitzone** | Massgeblich für die Frist, z. B. `Europe/Madrid`, `America/Santo_Domingo`, `Europe/Zurich`. |
| **Beginn / Ende** | Nach Fristablauf schliesst die Urne automatisch – auch ohne Zutun der Verwaltung. |
| **Nach Miteigentumsanteilen gewichten** | An: Stimmgewicht = Anteil. Aus: Kopfprinzip, eine Einheit = eine Stimme. |
| **Doppelmehrheit** | Ein Antrag gilt nur als angenommen, wenn er die Mehrheit nach Köpfen **und** nach Anteilen erreicht (in vielen Eigentumsordnungen vorgeschrieben). |
| **Quorum** | Mindestbeteiligung in Prozent für die Beschlussfähigkeit. 0 = kein Quorum. |

### Schritt 3 – Beschlussanträge erfassen

Drei Antragstypen:

* **Ja/Nein** – mit Enthaltung, inklusive Auswertung der erforderlichen Mehrheit
* **Auswahl (eine Antwort)** – z. B. Wahl des Verwaltungsbeirats
* **Auswahl (mehrere Antworten)**

Je Ja/Nein-Antrag werden das **Mehrheitserfordernis** (einfach, absolut, 3/5,
2/3, 3/4, Einstimmigkeit) und die **Bezugsgrösse** festgelegt:

| Bezugsgrösse | Gerechnet wird gegen |
|---|---|
| gültige Stimmen | Ja + Nein (Enthaltungen bleiben aussen vor) |
| alle abgegebenen Stimmen | Ja + Nein + Enthaltung |
| alle Stimmberechtigten | auch die, die nicht abgestimmt haben |

Die Wahl der Bezugsgrösse verändert das Ergebnis erheblich. Sie muss der
Eigentumsordnung bzw. dem anwendbaren Gesetz entsprechen und wird auf dem
Stimmzettel angezeigt, damit sie für alle transparent ist.

> Nach der Eröffnung sind die Anträge gesperrt und nicht mehr änderbar.

### Schritt 4 – Stimmregister pflegen

Ein Eintrag = ein Stimmrecht = in der Regel eine Wohneinheit.

Import direkt aus Excel (Semikolon, Komma oder Tabulator; Dezimalkomma wird
erkannt):

```
Name;E-Mail;Einheit;Stimmgewicht
Maria López;maria@example.com;A-12;3,45
Hans Meier;hans@example.com;B-04;2,80
Pierre Dupont;;C-01;1,20
```

* **Ohne E-Mail-Adresse** → Zugangscode wird per Post/persönlich übergeben.
* **Vollmacht** → im Feld „Bevollmächtigt" eintragen und als E-Mail-Adresse die
  der bevollmächtigten Person hinterlegen. Das Stimmrecht bleibt der Einheit
  zugeordnet, die Vollmacht steht in der Präsenzliste.
* **Stimmgewicht** bei Kopfprinzip überall `1`.

### Schritt 5 – Abstimmung eröffnen

Erzeugt für jedes stimmberechtigte Register die Zugangscodes und versendet auf
Wunsch sofort die Stimmunterlagen per E-Mail.

> ⚠️ **Die Codeliste erscheint genau einmal.** Sie kann als CSV heruntergeladen
> oder gedruckt werden – danach ist sie nicht wiederherstellbar, weil in der
> Datenbank nur Hashes liegen. Für den Postversand unbedingt jetzt sichern.

### Schritt 6 – Während der Abstimmung

Die Präsenzliste zeigt live, wer bereits abgestimmt hat – **nicht wie**.
Nichtwähler können damit gezielt erinnert werden.

Eine Erinnerung stellt zwingend **neue** Codes aus und entwertet die alten;
die alten liegen nur als Hash vor und können nicht erneut versendet werden.
Das ist kein Mangel, sondern die Gegenleistung dafür, dass die Verwaltung mit
den Codes nicht selbst abstimmen kann.

### Schritt 7 – Schliessen und auszählen

Beim Schliessen wird die Urne versiegelt und der Fingerabdruck berechnet. Die
Ergebnisseite weist aus:

* Beteiligung nach Köpfen und nach Anteilen
* Beschlussfähigkeit (Quorum erreicht?)
* je Antrag: Stimmen nach Köpfen und Anteilen, Bezugsgrösse, angenommen/abgelehnt
* Integritätsprüfung von Protokollkette und Urnen-Fingerabdruck

### Schritt 8 – Ergebnis veröffentlichen

Erst danach ist die öffentliche Verifikationsseite erreichbar. Der Link gehört
in das Protokoll und in das Ergebnisschreiben:

```
https://ihre-domain/abstimmung/<public_id>/verifikation
```

---

## 3. Stimmgeheimnis bei gewichteter Abstimmung – wichtiger Hinweis

Sind die Miteigentumsanteile je Einheit **unterschiedlich**, dann verrät ein
veröffentlichter Stimmzettel über sein Stimmgewicht die Einheit – und damit die
Person. Das ist kein Fehler der Software, sondern eine mathematische Folge der
Gewichtung.

Deshalb gibt es drei Stufen der Veröffentlichung:

| Modus | Öffentlich sichtbar | Empfehlung |
|---|---|---|
| **Keine Urnenliste** | nur das Ergebnis | wenn keine Einzelprüfung gewünscht ist |
| **Nur Quittungscodes** | Codes, keine Stimmen | **Standard bei gewichteter Abstimmung** |
| **Codes und Stimmen** | vollständige Urnenliste | nur beim Kopfprinzip oder bei gleichen Anteilen |

Auch im Modus „Nur Quittungscodes" bleibt die vollständige Nachzählung möglich:
Der CSV-Export der Urnenliste steht Verwaltungsbeirat und Rechnungsprüfung zur
Verfügung, und der veröffentlichte Fingerabdruck beweist, dass die
exportierte Liste dieselbe ist, die beim Schliessen versiegelt wurde.

---

## 4. Unterlagen für das Versammlungsprotokoll

Drei Exporte, die zusammen die Abstimmung dokumentieren:

| Export | Inhalt | Enthält Personen? |
|---|---|---|
| **Präsenzliste** | Wer war stimmberechtigt, mit welchem Gewicht, wer hat abgestimmt (Datum), Vollmachten | ja |
| **Urnenliste** | Alle Stimmzettel mit Quittungscode und Stimmen, sortiert nach Code, plus Fingerabdruck | nein |
| **Protokoll** | Alle Verwaltungsvorgänge mit Zeitpunkt, Benutzer und Hashkette | ja (nur Verwaltung) |

Ins Protokoll der Versammlung gehören mindestens:

* der **Urnen-Fingerabdruck** (er versiegelt das Ergebnis nachträglich)
* Beteiligung und Feststellung der Beschlussfähigkeit
* je Antrag: Stimmen, Bezugsgrösse, Mehrheitserfordernis, Feststellung
* der Link zur Verifikationsseite

---

## 5. Rechtliche Absicherung – Checkliste

> Diese Software liefert die technische Grundlage. Ob ein Beschluss wirksam
> zustande kommt, hängt vom anwendbaren Recht (in Spanien z. B. der *Ley de
> Propiedad Horizontal*) und von Ihrer Eigentumsordnung bzw. den Statuten ab.
> **Das ist keine Rechtsberatung.** Lassen Sie den Ablauf vor der ersten
> verbindlichen Abstimmung von der Verwaltung und, bei grösseren Beschlüssen,
> anwaltlich prüfen.

**Vor der Abstimmung**

- [ ] Lässt die Eigentumsordnung / lässt das anwendbare Gesetz eine elektronische
      oder schriftliche Abstimmung ausserhalb der Präsenzversammlung überhaupt zu?
      Falls unklar: vorab durch Beschluss der Versammlung legitimieren.
- [ ] Einladung form- und fristgerecht versendet, mit vollständigem Wortlaut
      aller Beschlussanträge – abgestimmt wird nur über das, was angekündigt war.
- [ ] Mehrheitserfordernis und Bezugsgrösse je Antrag mit der Eigentumsordnung
      abgeglichen (einfach / absolut / 3/5 / 2/3 / 3/4 / Einstimmigkeit).
- [ ] Quorum und Doppelmehrheit korrekt hinterlegt.
- [ ] Stimmregister gegen das aktuelle Grundbuch bzw. die Eigentümerliste
      geprüft – **Stichtag festhalten**. Eigentümerwechsel kurz vor der
      Abstimmung sind der häufigste Anfechtungsgrund.
- [ ] Stimmgewichte = Miteigentumsanteile, Summe stimmt mit der Teilungserklärung
      überein.
- [ ] Vollmachten schriftlich eingeholt und dokumentiert; Formvorschriften der
      Eigentumsordnung beachtet.
- [ ] Frist (Datum, Uhrzeit, Zeitzone) eindeutig kommuniziert.
- [ ] Zugangsweg für Personen ohne E-Mail/Internet sichergestellt – sonst droht
      der Vorwurf, Stimmberechtigte seien ausgeschlossen worden.

**Während der Abstimmung**

- [ ] Codeliste beim Erzeugen gesichert; Papierversand nachweisbar (Einschreiben
      oder Empfangsbestätigung).
- [ ] Kein Zwischenergebnis veröffentlichen – das kann das Stimmverhalten
      beeinflussen und die Anfechtbarkeit erhöhen.
- [ ] Jede Codeerneuerung wird protokolliert; Anlass kurz dokumentieren.

**Nach der Abstimmung**

- [ ] Urne geschlossen, Fingerabdruck notiert.
- [ ] Integritätsanzeige geprüft: Protokollkette unversehrt, Fingerabdruck stimmt.
- [ ] Alle drei Exporte gesichert und dem Protokoll beigefügt.
- [ ] Ergebnis von der Versammlungsleitung förmlich festgestellt und
      veröffentlicht; Beschlussanfechtungsfrist mitgeteilt.
- [ ] Alle Stimmberechtigten über die Verifikationsseite informiert.

**Datenschutz (DSGVO)**

- [ ] Rechtsgrundlage: Durchführung der Eigentümerversammlung (Art. 6 Abs. 1
      lit. b/c/f DSGVO) – im Einladungsschreiben benennen.
- [ ] Verarbeitet werden Name, E-Mail, Einheit, Stimmgewicht und die Tatsache
      der Teilnahme – **nicht** das Stimmverhalten. Das ist in der
      Datenschutzinformation so zu beschreiben.
- [ ] Löschfrist für Präsenzliste und Protokoll festlegen (üblicherweise
      Ablauf der Anfechtungsfrist zzgl. Aufbewahrungspflichten).
- [ ] Auftragsverarbeitungsvertrag mit dem Hoster abschliessen, sofern die
      Anwendung nicht selbst betrieben wird.

**Was diese Software bewusst NICHT leistet**

* **Identitätsprüfung.** Sie stellt sicher, dass ein gültiger Zugangscode
  verwendet wurde – nicht, dass die richtige Person ihn benutzt hat. Genau wie
  bei der Briefwahl. Wer eine stärkere Bindung braucht, ergänzt eine
  Zwei-Faktor-Bestätigung oder eine qualifizierte elektronische Signatur.
* **Schutz gegen die Serverbetreiberin.** Wer Schreibzugriff auf die Datenbank
  hat, kann Stimmen einwerfen. Erkennbar wird das über den Fingerabdruck, das
  Protokoll und die Zahl der entwerteten Codes – verhindert wird es nicht.
  Gegenmassnahmen: Zugriff nur für die Verwaltung, Fingerabdruck sofort nach
  dem Schliessen an alle kommunizieren, regelmässige Sicherungen an einen Ort
  ausserhalb der Verwaltungshoheit (z. B. Verwaltungsbeirat).
* **Zwangsfreiheit.** Wer seinen Quittungscode weitergibt, kann sein
  Stimmverhalten belegen. Bei Präsenzwahl ist das ausgeschlossen. Für
  Eigentümerversammlungen wird das üblicherweise akzeptiert; die Alternative
  wäre der Verzicht auf die individuelle Verifizierbarkeit.

---

## 6. Betrieb

### Konfiguration

```bash
BASE_URL=https://abstimmung.ihre-domain.tld   # für korrekte Links in E-Mails
SESSION_COOKIE_SECURE=true                    # bei HTTPS-Betrieb setzen
SECRET_KEY=...                                # fest setzen, sonst zufällig erzeugt
```

**HTTPS ist Pflicht.** Die Zugangscodes stehen in der URL; über HTTP wären sie
im Klartext im Netz unterwegs. Die Stimmzettelseiten setzen
`Referrer-Policy: no-referrer` und `noindex`, damit Codes nicht über
Referrer-Header oder Suchmaschinen abfliessen.

### Sicherung

Vor dem Schliessen und unmittelbar danach eine Kopie der Datenbank
(`instance/formapp.db`) ausserhalb des Servers ablegen. Der Urnen-Fingerabdruck
belegt später, dass Sicherung und Original übereinstimmen.

### Tests

```bash
python tests/run_all.py
```

Geprüft werden unter anderem: vollständiger Abstimmungsablauf, Auszählung mit
Gewichtung und Doppelmehrheit, Abwehr von Doppelstimmen, Trennung von
Stimmregister und Urne, Erkennung nachträglicher Manipulation an Protokoll und
Urne, Fristablauf, Codeerneuerung und Zugriffsschutz.
