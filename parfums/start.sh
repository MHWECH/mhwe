#!/usr/bin/env bash
# Startet die Duftsammlung lokal.
# Aufruf:  ./start.sh   (danach http://localhost:8080 im Browser oeffnen)

set -e
cd "$(dirname "$0")"

PORT="${PORT:-8080}"
echo "=========================================="
echo "  Duftsammlung laeuft auf:"
echo "  http://localhost:$PORT"
echo "  (Beenden mit Ctrl+C)"
echo "=========================================="

exec python3 -m http.server "$PORT"
