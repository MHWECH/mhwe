"""End-to-End-Test des Abstimmungsablaufs."""
import os, re, shutil, sys, tempfile

tmp = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f'sqlite:///{tmp}/test.db'
os.environ['SECRET_KEY'] = 'test-key'
os.environ['ADMIN_USERNAME'] = 'admin'
os.environ['ADMIN_PASSWORD'] = 'testpass'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, init_db, db
from voting import (Election, Question, Voter, VotingToken, Ballot, AuditLog,
                    compute_results, verify_audit_chain, compute_urn_fingerprint)

app.config['TESTING'] = False
with app.app_context():
    db.drop_all()
    init_db()

client = app.test_client()

def csrf(html):
    m = re.search(r'name="_csrf" value="([^"]+)"', html)
    assert m, 'kein CSRF-Token gefunden'
    return m.group(1)

def check(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    if not cond:
        raise SystemExit(1)

print('\n1) Admin-Login')
r = client.get('/admin/login')
r = client.post('/admin/login', data={'username': 'admin', 'password': 'testpass'},
                follow_redirects=True)
check(b'Dashboard' in r.data, 'angemeldet')

print('\n2) Abstimmung anlegen')
r = client.get('/admin/abstimmungen')
token = csrf(r.get_data(as_text=True))
r = client.post('/admin/abstimmungen/neu',
                data={'_csrf': token, 'title': 'EV Villas Tropimar 2026'},
                follow_redirects=True)
with app.app_context():
    election = Election.query.first()
    eid = election.id
check(election is not None, f'Abstimmung #{eid} angelegt')

print('\n3) Rahmendaten setzen (Doppelmehrheit, Quorum 50 %)')
r = client.post(f'/admin/abstimmungen/{eid}', data={
    '_csrf': token, 'title': 'EV Villas Tropimar 2026',
    'description': 'Ordentliche Eigentümerversammlung',
    'timezone_name': 'Europe/Madrid',
    'opens_at': '', 'closes_at': '2030-12-31T23:59',
    'weighted': 'on', 'double_majority': 'on',
    'quorum_heads': '50', 'quorum_weight': '50',
    'verification_mode': 'codes', 'invitation_subject': 'Test',
    'invitation_body': '',
}, follow_redirects=True)
with app.app_context():
    e = db.session.get(Election, eid)
    check(e.quorum_heads == 50 and e.double_majority, 'Rahmendaten gespeichert')
    check(e.closes_at.hour == 22, f'Zeitzone Europe/Madrid → UTC ({e.closes_at})')

print('\n4) Beschlussanträge erfassen')
import json
questions = [
    {'text': 'Genehmigung der Jahresabrechnung 2025', 'description': '',
     'qtype': 'janein', 'majority_type': 'einfach', 'majority_base': 'gueltige',
     'options': []},
    {'text': 'Sanierung der Poolanlage (Sonderumlage 45.000 EUR)', 'description': '',
     'qtype': 'janein', 'majority_type': 'drei_fuenftel', 'majority_base': 'alle',
     'options': []},
    {'text': 'Wahl des Verwaltungsbeirats', 'description': '',
     'qtype': 'einzelauswahl', 'majority_type': 'einfach', 'majority_base': 'gueltige',
     'options': [{'label': 'Maria López'}, {'label': 'Hans Meier'}]},
]
r = client.post(f'/admin/abstimmungen/{eid}/fragen',
                data={'_csrf': token, 'questions_json': json.dumps(questions)},
                follow_redirects=True)
with app.app_context():
    qs = Question.query.filter_by(election_id=eid).order_by(Question.order_index).all()
check(len(qs) == 3, f'{len(qs)} Anträge gespeichert')

print('\n5) Stimmregister importieren')
roll = """Name;E-Mail;Einheit;Stimmgewicht
Maria López;maria@example.com;A-12;3,45
Hans Meier;hans@example.com;B-04;2,80
Sofia Rossi;sofia@example.com;B-05;2,80
Pierre Dupont;;C-01;1,20
Anna Schmidt;anna@example.com;C-02;1,20"""
r = client.post(f'/admin/abstimmungen/{eid}/stimmregister',
                data={'_csrf': token, 'action': 'import', 'import_text': roll},
                follow_redirects=True)
with app.app_context():
    voters = Voter.query.filter_by(election_id=eid).all()
    total = sum(v.weight for v in voters)
check(len(voters) == 5, f'{len(voters)} Stimmrechte importiert')
check(abs(total - 11.45) < 1e-6, f'Summe Stimmgewicht = {total} (Dezimalkomma erkannt)')

print('\n6) Abstimmung eröffnen (Codes erzeugen)')
r = client.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': token})
html = r.get_data(as_text=True)
codes = re.findall(r'<td class="font-monospace">([A-Z0-9-]{29})</td>', html)
check(len(codes) == 5, f'{len(codes)} Zugangscodes einmalig angezeigt')
with app.app_context():
    e = db.session.get(Election, eid)
    check(e.status == 'open', 'Status = open')
    stored = [t.token_hash for t in VotingToken.query.filter_by(election_id=eid)]
    check(all(len(h) == 64 for h in stored), 'nur Hashes gespeichert')
    check(not any(c in ' '.join(stored) for c in codes), 'kein Klartext in der Datenbank')

print('\n7) Stimmabgabe')
with app.app_context():
    qids = [q.id for q in Question.query.filter_by(election_id=eid)
            .order_by(Question.order_index)]

votes = [
    ('ja', 'ja', 'opt1'),      # Maria   3.45
    ('ja', 'ja', 'opt1'),      # Hans    2.80
    ('ja', 'nein', 'opt2'),    # Sofia   2.80
    ('nein', 'nein', 'opt2'),  # Pierre  1.20
]
receipts = []
for code, (a1, a2, a3) in zip(codes, votes):
    voter_client = app.test_client()
    page = voter_client.get(f'/stimme/{code}')
    check(page.status_code == 200, f'Stimmzettel abrufbar für {code[:11]}…')
    t = csrf(page.get_data(as_text=True))
    r = voter_client.post(f'/stimme/{code}', data={
        '_csrf': t, f'q_{qids[0]}': a1, f'q_{qids[1]}': a2, f'q_{qids[2]}': a3},
        follow_redirects=True)
    body = r.get_data(as_text=True)
    m = re.search(r'Ihr Quittungscode.*?([A-Z0-9]{4}-[A-Z0-9]{4})', body, re.S)
    check(m is not None, '  → Quittungscode erhalten: '
          + (m.group(1) if m else 'KEINER – ' + ('Stimmzettel abgelehnt'
             if 'Beschlussantrag' in body else 'unklar')))
    receipts.append(m.group(1))

print('\n8) Doppelabstimmung wird verhindert')
c2 = app.test_client()
page = c2.get(f'/stimme/{codes[0]}')
check(b'bereits abgegeben' in page.data, 'zweiter Aufruf desselben Codes blockiert')
r = c2.post(f'/stimme/{codes[0]}', data={'_csrf': 'x', f'q_{qids[0]}': 'nein'})
with app.app_context():
    check(Ballot.query.filter_by(election_id=eid).count() == 4,
          'weiterhin genau 4 Stimmzettel in der Urne')

print('\n9) Ungültiger und entwerteter Code')
r = app.test_client().get('/stimme/AAAAA-BBBBB-CCCCC-DDDDD-EEEEE')
check(r.status_code == 404 and 'ungültig' in r.get_data(as_text=True),
      'unbekannter Code wird abgewiesen')

print('\n10) Anonymität: keine Verbindung Person ↔ Stimmzettel')
with app.app_context():
    ballot_columns = {c.name for c in Ballot.__table__.columns}
    check('voter_id' not in ballot_columns and 'token_hash' not in ballot_columns,
          f'Urne enthält keine Personenspalte: {sorted(ballot_columns)}')
    check(all(b.cast_on is not None for b in Ballot.query.all()),
          'Stimmzettel nur tagesgenau (keine Uhrzeit)')
    voted = Voter.query.filter_by(voted=True).all()
    check(all(v.voted_on is not None for v in voted),
          'Präsenzliste nur tagesgenau (keine Uhrzeit)')

print('\n11) Abstimmung schliessen und auszählen')
r = client.post(f'/admin/abstimmungen/{eid}/schliessen',
                data={'_csrf': token}, follow_redirects=True)
with app.app_context():
    e = db.session.get(Election, eid)
    res = compute_results(e)
    check(e.status == 'closed', 'Urne geschlossen')
    check(len(e.urn_fingerprint) == 64, f'Fingerabdruck {e.urn_fingerprint[:16]}…')
    check(res['cast_heads'] == 4, f"4 von 5 Stimmen ({res['turnout_heads']:.1f} % Köpfe)")
    check(abs(res['cast_weight'] - 10.25) < 1e-6,
          f"Stimmgewicht {res['cast_weight']} von {res['eligible_weight']}")
    check(res['quorum_ok'], 'Quorum 50 % erreicht')

    q1, q2, q3 = res['questions']
    # TOP 1: 3x Ja (9.05), 1x Nein (1.20) – einfache Mehrheit
    check(q1['tallies']['ja']['heads'] == 3 and q1['tallies']['nein']['heads'] == 1,
          'TOP 1: 3 Ja / 1 Nein')
    check(q1['evaluation']['heads']['angenommen'] and
          q1['evaluation']['weight']['angenommen'], 'TOP 1 angenommen (Doppelmehrheit)')
    # TOP 2: 2x Ja (6.25 von 11.45 = 54.6 %) – 3/5 aller Stimmberechtigten verfehlt
    check(abs(q2['tallies']['ja']['weight'] - 6.25) < 1e-6,
          f"TOP 2: Ja-Anteile {q2['tallies']['ja']['weight']}")
    check(not q2['evaluation']['weight']['angenommen'],
          'TOP 2 abgelehnt – 3/5 aller Anteile (6,87) nicht erreicht')
    check(q2['evaluation']['weight']['basis'] == res['eligible_weight'],
          'Bezugsgrösse = alle Stimmberechtigten')
    # TOP 3: Wahl
    check(q3['tallies']['opt1']['heads'] == 2 and q3['tallies']['opt2']['heads'] == 2,
          'TOP 3: 2:2 nach Köpfen')

print('\n12) Manipulationserkennung')
with app.app_context():
    ok, err = verify_audit_chain(eid)
    check(ok, 'Protokollkette unversehrt')
    entry = AuditLog.query.filter_by(election_id=eid).order_by(AuditLog.id).offset(2).first()
    original = entry.details
    entry.details = 'nachträglich geändert'
    db.session.commit()
    ok, err = verify_audit_chain(eid)
    check(not ok, f'nachträgliche Änderung an Eintrag {err + 1} erkannt')
    entry.details = original
    db.session.commit()
    check(verify_audit_chain(eid)[0], 'nach Wiederherstellung wieder unversehrt')

    e = db.session.get(Election, eid)
    before = e.urn_fingerprint
    extra = Ballot(election_id=eid, receipt_code='FAKE-CODE', weight=1.0,
                   answers_json='{}', ballot_hash='x' * 64)
    db.session.add(extra)
    db.session.commit()
    check(compute_urn_fingerprint(e) != before,
          'nachträglich eingeworfener Stimmzettel verändert den Fingerabdruck')
    db.session.delete(extra)
    db.session.commit()
    check(compute_urn_fingerprint(e) == before, 'Fingerabdruck nach Entfernen wieder korrekt')

print('\n13) Veröffentlichung und Verifikation durch Stimmberechtigte')
r = client.post(f'/admin/abstimmungen/{eid}/veroeffentlichen',
                data={'_csrf': token}, follow_redirects=True)
with app.app_context():
    pub = db.session.get(Election, eid).public_id
r = app.test_client().get(f'/abstimmung/{pub}/verifikation')
page = r.get_data(as_text=True)
check(r.status_code == 200, 'Verifikationsseite öffentlich erreichbar')
for receipt in receipts:
    check(receipt in page, f'Quittungscode {receipt} in der Urnenliste auffindbar')
check('Genehmigung der Jahresabrechnung' in page, 'Ergebnisse veröffentlicht')

print('\n14) Exporte')
for path, name in ((f'/admin/abstimmungen/{eid}/export/urne.csv', 'Urnenliste'),
                   (f'/admin/abstimmungen/{eid}/export/praesenz.csv', 'Präsenzliste'),
                   (f'/admin/abstimmungen/{eid}/export/protokoll.csv', 'Protokoll')):
    r = client.get(path)
    check(r.status_code == 200 and len(r.data) > 100,
          f'{name} exportierbar ({len(r.data)} Bytes)')
r = client.get(f'/admin/abstimmungen/{eid}/export/praesenz.csv')
body = r.get_data(as_text=True)
check('Maria López' in body and 'FAKE' not in body, 'Präsenzliste enthält Personen, keine Stimmen')
r = client.get(f'/admin/abstimmungen/{eid}/export/urne.csv')
body = r.get_data(as_text=True)
# "Maria López" kommt als Kandidatenname bei TOP 3 vor – geprüft wird, dass keine
# Wähleridentität (Einheit, E-Mail, Datensatz-ID) in der Urnenliste steht.
check(not any(x in body for x in ('A-12', 'B-04', 'C-01', '@example.com', 'Sofia', 'Pierre')),
      'Urnenliste enthält keine Wähleridentität (Einheiten, E-Mails, Namen)')

print('\n15) Zugriffsschutz')
anon = app.test_client()
for path in ('/admin/abstimmungen', f'/admin/abstimmungen/{eid}',
             f'/admin/abstimmungen/{eid}/export/urne.csv'):
    r = anon.get(path)
    check(r.status_code == 302 and '/admin/login' in r.headers.get('Location', ''),
          f'{path} nur für angemeldete Verwaltung')
r = client.post(f'/admin/abstimmungen/{eid}/loeschen', data={'_csrf': 'falsch'},
                follow_redirects=True)
check(b'Sicherheitspr' in r.data, 'CSRF-Schutz greift')

shutil.rmtree(tmp, ignore_errors=True)
print('\n✅ Alle Tests bestanden.\n')
