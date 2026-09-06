#!/usr/bin/env bash
#
# Baut den Ordner public/ zusammen, den Firebase Hosting ausliefert.
#
#   site/      → landet unter mhwe.services/          (bestehende Startseite)
#   parfums/   → landet unter mhwe.services/parfums   (die Duftsammlung)
#
# Ohne site/ wuerde ein Deploy die bestehende Startseite loeschen.
# Genau davor schuetzt dieses Skript.

set -euo pipefail
cd "$(dirname "$0")"

OHNE_STARTSEITE=0
[ "${1:-}" = "--ohne-startseite" ] && OHNE_STARTSEITE=1

if [ ! -d site ] && [ "$OHNE_STARTSEITE" -eq 0 ]; then
    cat >&2 <<'WARNUNG'

  ABBRUCH — der Ordner site/ fehlt.

  Firebase Hosting ersetzt beim Deploy die GESAMTE Seite. Wuerde jetzt
  deployt, waere die bestehende Startseite von mhwe.services weg und nur
  noch /parfums uebrig.

  So geht es richtig:

    1. Die Dateien der heutigen Startseite (index.html und alles,
       was dazugehoert) in den Ordner  site/  legen.
    2. ./build.sh erneut ausfuehren.

  Falls mhwe.services heute aus einem anderen Projekt deployt wird, ist
  der einfachere Weg: den Ordner parfums/ dort ins public-Verzeichnis
  kopieren und von dort deployen. Siehe parfums/DEPLOY.md.

  Wenn die Seite wirklich NUR aus der Duftsammlung bestehen soll:

    ./build.sh --ohne-startseite

WARNUNG
    exit 1
fi

rm -rf public
mkdir -p public

if [ -d site ]; then
    cp -r site/. public/
    echo "  Startseite  → public/"
else
    cat > public/index.html <<'HTML'
<!DOCTYPE html>
<html lang="de">
<meta charset="utf-8">
<meta http-equiv="refresh" content="0; url=./parfums/">
<title>Weiterleitung</title>
<a href="./parfums/">Zur Duftsammlung</a>
</html>
HTML
    echo "  Startseite  → Weiterleitung auf /parfums (keine site/ vorhanden)"
fi

cp -r parfums public/parfums
rm -f public/parfums/start.sh public/parfums/README.md public/parfums/DEPLOY.md
echo "  Sammlung    → public/parfums/"

echo
echo "  Fertig. $(find public -type f | wc -l | tr -d ' ') Dateien, $(du -sh public | cut -f1) gesamt."
echo "  Vorschau:  npx firebase-tools emulators:start --only hosting"
echo "  Deploy:    ./deploy.sh"
