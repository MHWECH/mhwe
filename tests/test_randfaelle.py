"""Randfälle: Fristablauf, Codeerneuerung, Sperren, Löschen."""
import os, re, sys, tempfile, json
from datetime import datetime, timedelta
tmp = tempfile.mkdtemp()
os.environ['DATABASE_URL'] = f'sqlite:///{tmp}/t.db'
os.environ['SECRET_KEY'] = 'k'; os.environ['ADMIN_PASSWORD'] = 'testpass'
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import app, init_db, db
from voting import Election, Question, Voter, VotingToken, AuditLog

with app.app_context():
    db.drop_all(); init_db()
c = app.test_client()
csrf = lambda h: re.search(r'name="_csrf" value="([^"]+)"', h).group(1)
c.post('/admin/login', data={'username': 'admin', 'password': 'testpass'})
t = csrf(c.get('/admin/abstimmungen').get_data(as_text=True))

def check(cond, msg):
    print(('  OK   ' if cond else '  FAIL ') + msg)
    assert cond

def setup(title, roll):
    c.post('/admin/abstimmungen/neu', data={'_csrf': t, 'title': title})
    with app.app_context():
        eid = Election.query.filter_by(title=title).first().id
    qs = [{'text': 'Antrag', 'description': '', 'qtype': 'janein',
           'majority_type': 'einfach', 'majority_base': 'gueltige', 'options': []}]
    c.post(f'/admin/abstimmungen/{eid}/fragen', data={'_csrf': t, 'questions_json': json.dumps(qs)})
    c.post(f'/admin/abstimmungen/{eid}/stimmregister',
           data={'_csrf': t, 'action': 'import', 'import_text': roll})
    return eid

print('\n1) Codeerneuerung entwertet den alten Code')
eid = setup('Erneuerung', 'A;;1;1\nB;;2;1')
r = c.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': t})
alt = re.findall(r'<td class="font-monospace">([A-Z0-9-]{29})</td>', r.get_data(as_text=True))
r = c.post(f'/admin/abstimmungen/{eid}/codes-erneuern', data={'_csrf': t})
neu = re.findall(r'<td class="font-monospace">([A-Z0-9-]{29})</td>', r.get_data(as_text=True))
check(len(neu) == 2 and set(alt).isdisjoint(neu), 'zwei neue Codes ausgestellt')
r = app.test_client().get(f'/stimme/{alt[0]}')
check('nicht mehr gültig' in r.get_data(as_text=True), 'alter Code entwertet')
v = app.test_client()
page = v.get(f'/stimme/{neu[0]}')
check(page.status_code == 200, 'neuer Code funktioniert')
with app.app_context():
    qid = Question.query.filter_by(election_id=eid).first().id
r = v.post(f'/stimme/{neu[0]}', data={'_csrf': csrf(page.get_data(as_text=True)),
                                      f'q_{qid}': 'ja'}, follow_redirects=True)
check('Quittungscode' in r.get_data(as_text=True), 'Stimme abgegeben')
r = c.post(f'/admin/abstimmungen/{eid}/codes-erneuern', data={'_csrf': t},
           follow_redirects=True)
with app.app_context():
    voted = Voter.query.filter_by(election_id=eid, voted=True).first()
    tokens = VotingToken.query.filter_by(voter_id=voted.id).all()
check(sum(1 for x in tokens if not x.revoked and x.used_on is None) == 0,
      'für bereits abgestimmtes Stimmrecht wird kein neuer Code ausgestellt')

print('\n2) Fristablauf schliesst die Urne automatisch')
eid = setup('Frist', 'A;;1;1')
c.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': t})
with app.app_context():
    e = db.session.get(Election, eid)
    e.closes_at = datetime.utcnow() - timedelta(minutes=1)
    db.session.commit()
    token_raw = None
r = c.get(f'/admin/abstimmungen/{eid}')
with app.app_context():
    e = db.session.get(Election, eid)
    check(e.status == 'closed', 'Status nach Fristablauf automatisch geschlossen')
    check(len(e.urn_fingerprint) == 64, 'Fingerabdruck beim Autoschliessen gesetzt')
    entries = [a.action for a in AuditLog.query.filter_by(election_id=eid)]
    check('abstimmung_geschlossen' in entries, 'Autoschliessung protokolliert')

print('\n3) Gesperrtes Stimmrecht kann nicht abstimmen')
eid = setup('Sperre', 'A;;1;1\nB;;2;1')
r = c.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': t})
codes = re.findall(r'<td class="font-monospace">([A-Z0-9-]{29})</td>', r.get_data(as_text=True))
with app.app_context():
    vid = Voter.query.filter_by(election_id=eid).order_by(Voter.id).first().id
c.post(f'/admin/abstimmungen/{eid}/stimmregister/{vid}',
       data={'_csrf': t, 'action': 'toggle_eligible'})
r = app.test_client().get(f'/stimme/{codes[0]}')
check('Kein Stimmrecht' in r.get_data(as_text=True), 'gesperrter Eintrag wird abgewiesen')

print('\n4) Löschen einer durchgeführten Abstimmung verlangt Titelbestätigung')
r = c.post(f'/admin/abstimmungen/{eid}/loeschen', data={'_csrf': t, 'confirm': 'falsch'},
           follow_redirects=True)
with app.app_context():
    check(db.session.get(Election, eid) is not None, 'ohne Bestätigung nicht gelöscht')
r = c.post(f'/admin/abstimmungen/{eid}/loeschen', data={'_csrf': t, 'confirm': 'Sperre'},
           follow_redirects=True)
with app.app_context():
    check(db.session.get(Election, eid) is None, 'mit Titelbestätigung gelöscht')
    check(Voter.query.filter_by(election_id=eid).count() == 0 and
          VotingToken.query.filter_by(election_id=eid).count() == 0 and
          Question.query.filter_by(election_id=eid).count() == 0 and
          AuditLog.query.filter_by(election_id=eid).count() == 0,
          'alle abhängigen Datensätze mitgelöscht')

print('\n5) Anträge sind nach Eröffnung gesperrt')
eid = setup('Sperrtest', 'A;;1;1')
c.post(f'/admin/abstimmungen/{eid}/oeffnen', data={'_csrf': t})
r = c.post(f'/admin/abstimmungen/{eid}/fragen',
           data={'_csrf': t, 'questions_json': json.dumps([])}, follow_redirects=True)
with app.app_context():
    check(Question.query.filter_by(election_id=eid).count() == 1,
          'Anträge nach Eröffnung unveränderbar')
r = c.post(f'/admin/abstimmungen/{eid}/stimmregister',
           data={'_csrf': t, 'action': 'import', 'import_text': 'X;;9;1', 'replace': 'on'},
           follow_redirects=True)
with app.app_context():
    check(Voter.query.filter_by(election_id=eid).count() == 1,
          'Stimmregister-Massenimport nach Eröffnung gesperrt')

print('\n✅ Randfälle bestanden.\n')
