#!/usr/bin/env python
"""Führt alle Tests des Abstimmungssystems aus.

    python tests/run_all.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SUITES = [
    ('Vollständiger Abstimmungsablauf', 'test_ablauf.py'),
    ('Seiten rendern fehlerfrei', 'test_seiten.py'),
    ('Randfälle', 'test_randfaelle.py'),
]

failed = []
for title, filename in SUITES:
    print(f'\n{"=" * 70}\n  {title}\n{"=" * 70}')
    result = subprocess.run([sys.executable, os.path.join(HERE, filename)])
    if result.returncode != 0:
        failed.append(title)

print(f'\n{"=" * 70}')
if failed:
    print('FEHLGESCHLAGEN: ' + ', '.join(failed))
    sys.exit(1)
print(f'  Alle {len(SUITES)} Testsuiten bestanden.')
