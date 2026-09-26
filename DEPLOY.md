# Online stellen mit Render

Die App läuft auf [Render](https://render.com) und aktualisiert sich automatisch
bei jedem Push auf GitHub. Datenbank, Mail-Archiv, Uploads und Schlüssel liegen
auf einer festen Disk (`/var/data`) und bleiben bei Updates erhalten.

**Kosten:** ca. 7 USD/Monat (Starter-Instanz) + 0.25 USD/Monat (1 GB Disk).

## Einmalig einrichten

1. Auf https://render.com mit dem GitHub-Konto anmelden.
2. **New → Blueprint** wählen und das Repository `MHWECH/mhwe` auswählen.
3. Branch mit dieser App wählen. Render liest `render.yaml` automatisch.
4. Bei `ADMIN_PASSWORD` ein sicheres Passwort für den Admin-Bereich eingeben.
5. **Apply** klicken. Nach 2–3 Minuten läuft die App unter
   `https://formular-app-xxxx.onrender.com`.

## Danach

- Admin-Bereich: `https://<deine-adresse>/admin`
- Im Admin unter **E-Mail-Einstellungen** den Mailserver eintragen und
  **Test senden** klicken. Für Gmail: Server `smtp.gmail.com`, Port `587`, TLS,
  und ein [App-Passwort](https://myaccount.google.com/apppasswords) verwenden.
- Mail-Archiv: im Menü **📦 Mail-Archiv**.

## Backup

Render → Service → **Disks** → Snapshots (werden täglich automatisch erstellt).
