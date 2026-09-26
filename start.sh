#!/usr/bin/env bash
# Startet die Formular-WebApp
# Konfiguration über Umgebungsvariablen oder .env-Datei

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Lade .env falls vorhanden
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Datenbank initialisieren
python - <<'EOF'
from app import app, init_db
with app.app_context():
    init_db()
EOF

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-5000}"

echo "=========================================="
echo "  Formular-WebApp startet..."
echo "  Adresse: http://$HOST:$PORT"
echo "  Admin:   http://$HOST:$PORT/admin"
echo "=========================================="

if python -c "import gunicorn" 2>/dev/null; then
    exec python -m gunicorn wsgi:application \
        --bind "$HOST:$PORT" \
        --workers 2 \
        --timeout 60
else
    echo "  Hinweis: gunicorn nicht installiert, starte Flask-Entwicklungsserver."
    exec python app.py
fi
