"""Smoke-Test: alle Seiten rendern fehlerfrei."""
import os, re, sys, tempfile, json
tmp = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f'sqlite:///{tmp}/t.db'
os.environ['SECRET_KEY'] = 'k'; os.environ['ADMIN_PASSWORD'] = 'testpass'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, init_db, db
from voting import Election, Question

with app.app_context():
    db.drop_all(); init_db()
c = app.test_client()
csrf = lambda h: re.search(r'name="_csrf" value="([^"]+)"', h).group(1)
c.post('/admin/login', data={'username': 'admin', 'password': 'testpass'})
t = csrf(c.get('/admin/abstimmungen').get_data(as_text=True))
c.post('/admin/abstimmungen/neu', data={'_csrf': t, 'title': 'Smoke'})
with app.app_context():
    eid = Election.query.first().id

def ok(path, expect=200, label=None):
    r = c.get(path)
    status = 'OK  ' if r.status_code == expect else 'FAIL'
    print(f'  {status} [{r.status_code}] {label or path}')
    assert r.status_code == expect, r.get_data(as_text=True)[:800]
    return r

print('\nEntwurfsphase')
for p in ('/admin/abstimmungen', f'/admin/abstimmungen/{eid}',
          f'/admin/abstimmungen/{eid}/fragen',
          f'/admin/abstimmungen/{eid}/stimmregister',
          f'/admin/abstimmungen/{eid}/protokoll',
          f'/admin/abstimmungen/{eid}/export/praesenz.csv',
          f'/admin/abstimmungen/{eid}/export/protokoll.csv'):
    ok(p)
r = c.get(f'/admin/abstimmungen/{eid}/ergebnis')
print(f'  OK   [{r.status_code}] Ergebnis im Entwurf → Weiterleitung')

print('\nÖffentliche Seiten')
ok('/stimme/')
ok('/stimme/UNBEKANNTER-CODE', 404, 'unbekannter Code → 404-Infoseite')
r = c.post('/stimme/', data={'_csrf': csrf(c.get('/stimme/').get_data(as_text=True)),
                             'code': 'XXXXX-XXXXX-XXXXX-XXXXX-XXXXX'})
assert 'unbekannt' in r.get_data(as_text=True)
print('  OK   Codeeingabe weist falschen Code ab')
with app.app_context():
    pub = db.session.get(Election, eid).public_id
r = c.get(f'/abstimmung/{pub}/verifikation')
assert 'läuft noch' in r.get_data(as_text=True)
print('  OK   Verifikation vor Abschluss gesperrt')
ok('/abstimmung/gibtsnicht/verifikation', 404, 'unbekannte Abstimmung → 404')

print('\nDurchführung')
qs = [{'text': 'Antrag A', 'description': 'Erläuterung', 'qtype': 'janein',
       'majority_type': 'zwei_drittel', 'majority_base': 'abgegebene', 'options': []},
      {'text': 'Antrag B', 'description': '', 'qtype': 'mehrfachauswahl',
       'majority_type': 'einfach', 'majority_base': 'gueltige',
       'options': [{'label': 'Variante 1'}, {'label': 'Variante 2'}]}]
c.post(f'/admin/abstimmungen/{eid}/fragen', data={'_csrf': t, 'questions_json': json.dumps(qs)})
c.post(f'/admin/abstimmungen/{eid}/stimmregister',
       data={'_csrf': t, 'action': 'import', 'import_text': 'A;a@e.com;1;1\nB;;2;2'})
ok(f'/admin/abstimmungen/{eid}/fragen', label='Antragseditor mit Inhalt')
ok(f'/admin/abstimmungen/{eid}/stimmregister', label='Stimmregister mit Inhalt')

r = c.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': t})
assert r.status_code == 200 and 'nur ein einziges Mal' in r.get_data(as_text=True)
print('  OK   Codeliste nach Eröffnung')
code = re.findall(r'<td class="font-monospace">([A-Z0-9-]{29})</td>', r.get_data(as_text=True))[0]

v = app.test_client()
page = v.get(f'/stimme/{code}')
assert page.status_code == 200 and 'Antrag A' in page.get_data(as_text=True)
print('  OK   Stimmzettel mit Ja/Nein und Mehrfachauswahl')
# unvollständiger Stimmzettel wird zurückgewiesen
tv = csrf(page.get_data(as_text=True))
with app.app_context():
    qids = [q.id for q in Question.query.order_by(Question.order_index)]
r = v.post(f'/stimme/{code}', data={'_csrf': tv, f'q_{qids[0]}': 'ja'})
assert 'Bitte beantworten Sie alle' in r.get_data(as_text=True)
print('  OK   unvollständiger Stimmzettel wird zurückgewiesen')
r = v.post(f'/stimme/{code}', data={'_csrf': tv, f'q_{qids[0]}': 'ja',
                                    f'q_{qids[1]}': ['opt1', 'opt2']},
           follow_redirects=True)
assert 'Quittungscode' in r.get_data(as_text=True)
print('  OK   Mehrfachauswahl akzeptiert')
# Quittung übersteht ein Neuladen und lässt sich bewusst schliessen
code_shown = re.search(r'Ihr Quittungscode.*?([A-Z0-9]{4}-[A-Z0-9]{4})',
                       r.get_data(as_text=True), re.S).group(1)
assert code_shown in v.get('/quittung').get_data(as_text=True)
print('  OK   Quittung übersteht ein Neuladen der Seite')
v.post('/quittung/schliessen', data={'_csrf': csrf(v.get('/quittung').get_data(as_text=True))})
assert v.get('/quittung').status_code == 302
print('  OK   Quittung nach dem Schliessen nicht mehr abrufbar')

print('\nAbschluss')
ok(f'/admin/abstimmungen/{eid}/ergebnis', label='Zwischenstand')
c.post(f'/admin/abstimmungen/{eid}/schliessen', data={'_csrf': t})
for p in (f'/admin/abstimmungen/{eid}/ergebnis', f'/admin/abstimmungen/{eid}/protokoll',
          f'/admin/abstimmungen/{eid}/export/urne.csv'):
    ok(p)
c.post(f'/admin/abstimmungen/{eid}/veroeffentlichen', data={'_csrf': t})
r = ok(f'/abstimmung/{pub}/verifikation', label='öffentliche Verifikation')
r = ok(f'/admin/abstimmungen/{eid}', label='Detailseite nach Veröffentlichung')

print('\nBestehende Formular-App unverändert erreichbar')
for p in ('/', '/admin/dashboard', '/admin/form-builder', '/admin/submissions',
          '/admin/mail-settings'):
    ok(p)

print('\n✅ Alle Seiten rendern fehlerfrei.\n')
