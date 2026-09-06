#!/usr/bin/env bash
#
# Veroeffentlicht die Seite auf Firebase Hosting.
# Vorher einmalig:  npm install -g firebase-tools && firebase login

set -euo pipefail
cd "$(dirname "$0")"

if grep -q "HIER-FIREBASE-PROJEKT-ID-EINTRAGEN" .firebaserc; then
    cat >&2 <<'WARNUNG'

  ABBRUCH — in .firebaserc fehlt die Projekt-ID.

  Die ID steht in der Firebase-Konsole oben links neben dem Projektnamen,
  oder unter  Projekteinstellungen → Projekt-ID.
  Alternativ auflisten mit:  firebase projects:list

  Dann in .firebaserc eintragen statt HIER-FIREBASE-PROJEKT-ID-EINTRAGEN.

WARNUNG
    exit 1
fi

./build.sh "$@"

echo
echo "  Deploy laeuft ..."
firebase deploy --only hosting
