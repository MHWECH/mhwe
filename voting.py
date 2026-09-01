"""Anonymes Abstimmungssystem für Eigentümerversammlungen.

Architektur der Anonymität
──────────────────────────
Das **Stimmregister** (wer ist stimmberechtigt, wer hat abgestimmt) und die
**Urne** (welche Stimmzettel wurden abgegeben) sind zwei strikt getrennte
Tabellen. Zwischen ihnen existiert **kein Fremdschlüssel und kein gemeinsames
Merkmal**, über das sich eine Stimme einer Person zuordnen liesse:

  Voter        ──┐                        ┌── Ballot
   name          │  VotingToken           │    receipt_code (Quittung)
   email         ├──  token_hash          │    answers_json
   unit          │   used_on (nur Datum)  │    weight
   weight        │   revoked              │    cast_on (nur Datum)
   voted (bool)──┘                        └──  ballot_hash
   voted_on (nur Datum)                        (keine voter_id!)

  ── Zeitstempel werden bewusst nur tagesgenau gespeichert, damit sich
     "Person X hat um 14:03:22 abgestimmt" nicht mit "Stimmzettel Y ging um
     14:03:22 ein" verknüpfen lässt.
  ── Der Zugangscode wird ausschliesslich als SHA-256-Hash gespeichert.
     Selbst mit vollem Datenbankzugriff lässt sich weder der Code
     rekonstruieren noch eine Stimme zuordnen.
  ── Die Reihenfolge der Stimmzettel wird nirgends ausgegeben; sortiert wird
     immer nach Quittungscode.

Schutz gegen Doppelabstimmung
─────────────────────────────
Zwei unabhängige, atomare Sperren in einer Transaktion:
  1. der Zugangscode ist einmalig verwendbar (used_on IS NULL → UPDATE)
  2. das Stimmregister führt ein voted-Flag (voted = 0 → UPDATE)
Beide UPDATEs müssen genau eine Zeile treffen, sonst wird die Transaktion
zurückgerollt. Damit sind auch Doppelklicks und parallele Requests abgedeckt.

Nachvollziehbarkeit (Beweissicherung)
─────────────────────────────────────
  ── Fortlaufendes, hashverkettetes Protokoll (AuditLog) über alle
     administrativen Vorgänge → nachträgliche Änderungen sind erkennbar.
  ── Jeder Stimmzettel trägt einen Inhalts-Hash, die Urne einen
     Gesamt-Fingerabdruck (Merkle-artige Prüfsumme über alle Stimmzettel),
     der beim Schliessen eingefroren und veröffentlicht wird.
  ── Jede stimmende Person erhält einen Quittungscode und kann damit
     überprüfen, dass ihre Stimme in der Urne liegt (individuelle
     Verifizierbarkeit).
"""

from flask import (Blueprint, render_template, request, redirect, url_for,
                   session, flash, Response)
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import csv
import hashlib
import io
import json
import secrets
import uuid

from app import app, db, login_required, MailConfig, _send_raw_email

voting_bp = Blueprint('voting', __name__)

# Zeichenvorrat ohne verwechselbare Zeichen (kein 0/O, 1/I/L)
CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'

JA_NEIN = [
    {'value': 'ja', 'label': 'Ja'},
    {'value': 'nein', 'label': 'Nein'},
    {'value': 'enthaltung', 'label': 'Enthaltung'},
]

MAJORITY_TYPES = {
    'einfach': 'Einfache Mehrheit (Ja > Nein)',
    'absolut': 'Absolute Mehrheit (mehr als 50 %)',
    'drei_fuenftel': 'Qualifizierte Mehrheit 3/5',
    'zwei_drittel': 'Qualifizierte Mehrheit 2/3',
    'drei_viertel': 'Qualifizierte Mehrheit 3/4',
    'einstimmig': 'Einstimmigkeit',
}

MAJORITY_BASES = {
    'gueltige': 'gültige Stimmen (ohne Enthaltungen)',
    'abgegebene': 'alle abgegebenen Stimmen (inkl. Enthaltungen)',
    'alle': 'alle Stimmberechtigten (auch nicht abgestimmte)',
}

MAJORITY_FRACTIONS = {
    'absolut': (1, 2),
    'drei_fuenftel': (3, 5),
    'zwei_drittel': (2, 3),
    'drei_viertel': (3, 4),
}

VERIFICATION_MODES = {
    'aus': 'Keine öffentliche Urnenliste',
    'codes': 'Nur Quittungscodes veröffentlichen (Stimme prüfbar, Inhalt geheim)',
    'voll': 'Quittungscodes und Stimmen veröffentlichen (volle Nachzählbarkeit)',
}


# ─── Models ──────────────────────────────────────────────────────────────────

class Election(db.Model):
    """Eine Abstimmung (z. B. eine Eigentümerversammlung mit mehreren TOPs)."""
    __tablename__ = 'elections'
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, nullable=False,
                          default=lambda: secrets.token_hex(8))
    title = db.Column(db.String(300), nullable=False, default='Abstimmung')
    description = db.Column(db.Text, default='')
    # draft → open → closed → published
    status = db.Column(db.String(20), nullable=False, default='draft')
    timezone_name = db.Column(db.String(64), default='Europe/Madrid')
    opens_at = db.Column(db.DateTime)          # UTC
    closes_at = db.Column(db.DateTime)         # UTC
    weighted = db.Column(db.Boolean, default=True)      # nach Miteigentumsanteilen
    double_majority = db.Column(db.Boolean, default=False)  # Köpfe UND Anteile
    quorum_heads = db.Column(db.Float, default=0.0)     # Prozent der Stimmberechtigten
    quorum_weight = db.Column(db.Float, default=0.0)    # Prozent der Anteile
    verification_mode = db.Column(db.String(20), default='codes')
    send_vote_confirmation = db.Column(db.Boolean, default=False)
    invitation_subject = db.Column(db.String(500),
                                   default='Ihre Stimmunterlagen: {titel}')
    invitation_body = db.Column(db.Text, default='')
    urn_fingerprint = db.Column(db.String(64), default='')
    closed_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    questions = db.relationship('Question', backref='election', cascade='all, delete-orphan',
                                order_by='Question.order_index')
    voters = db.relationship('Voter', backref='election', cascade='all, delete-orphan')

    @property
    def tz(self):
        try:
            return ZoneInfo(self.timezone_name or 'Europe/Madrid')
        except (ZoneInfoNotFoundError, ValueError):
            return ZoneInfo('UTC')

    @property
    def is_editable(self):
        """Inhalte dürfen nur geändert werden, solange niemand abstimmen konnte."""
        return self.status == 'draft'


class Question(db.Model):
    """Ein Beschlussantrag / Tagesordnungspunkt innerhalb einer Abstimmung."""
    __tablename__ = 'election_questions'
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    order_index = db.Column(db.Integer, default=0)
    text = db.Column(db.Text, nullable=False, default='')
    description = db.Column(db.Text, default='')
    qtype = db.Column(db.String(20), default='janein')   # janein | einzelauswahl | mehrfachauswahl
    options_json = db.Column(db.Text, default='[]')
    majority_type = db.Column(db.String(20), default='einfach')
    majority_base = db.Column(db.String(20), default='gueltige')

    @property
    def options(self):
        if self.qtype == 'janein':
            return JA_NEIN
        return json.loads(self.options_json or '[]')

    @options.setter
    def options(self, value):
        self.options_json = json.dumps(value, ensure_ascii=False)

    @property
    def majority_label(self):
        return (f'{MAJORITY_TYPES.get(self.majority_type, self.majority_type)} '
                f'– Basis: {MAJORITY_BASES.get(self.majority_base, self.majority_base)}')


class Voter(db.Model):
    """Stimmregister: ein Datensatz = ein Stimmrecht (in der Regel eine Einheit)."""
    __tablename__ = 'election_voters'
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    name = db.Column(db.String(300), nullable=False, default='')
    email = db.Column(db.String(300), default='')
    unit = db.Column(db.String(120), default='')          # Wohnung / Objekt
    weight = db.Column(db.Float, nullable=False, default=1.0)  # Miteigentumsanteil
    eligible = db.Column(db.Boolean, nullable=False, default=True)
    proxy_name = db.Column(db.String(300), default='')    # Bevollmächtigte Person
    note = db.Column(db.Text, default='')
    # Präsenzliste – bewusst OHNE Uhrzeit
    voted = db.Column(db.Boolean, nullable=False, default=False)
    voted_on = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tokens = db.relationship('VotingToken', backref='voter', cascade='all, delete-orphan')

    @property
    def active_token(self):
        for t in self.tokens:
            if not t.revoked:
                return t
        return None


class VotingToken(db.Model):
    """Einmal-Zugangscode. Gespeichert wird ausschliesslich der Hash."""
    __tablename__ = 'election_tokens'
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    voter_id = db.Column(db.Integer, db.ForeignKey('election_voters.id'), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    used_on = db.Column(db.Date)          # nur Datum – siehe Modulkopf
    revoked = db.Column(db.Boolean, nullable=False, default=False)


class Ballot(db.Model):
    """Urne. Enthält keinerlei Bezug zur stimmenden Person."""
    __tablename__ = 'election_ballots'
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), nullable=False)
    receipt_code = db.Column(db.String(16), unique=True, nullable=False, index=True)
    answers_json = db.Column(db.Text, nullable=False, default='{}')
    weight = db.Column(db.Float, nullable=False, default=1.0)
    cast_on = db.Column(db.Date)          # nur Datum – siehe Modulkopf
    ballot_hash = db.Column(db.String(64), nullable=False, default='')

    @property
    def answers(self):
        return json.loads(self.answers_json or '{}')


class AuditLog(db.Model):
    """Hashverkettetes Protokoll – nachträgliche Manipulation wird erkennbar."""
    __tablename__ = 'election_audit'
    id = db.Column(db.Integer, primary_key=True)
    election_id = db.Column(db.Integer, db.ForeignKey('elections.id'), index=True)
    at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    actor = db.Column(db.String(200), default='')
    action = db.Column(db.String(80), nullable=False, default='')
    details = db.Column(db.Text, default='')
    prev_hash = db.Column(db.String(64), default='')
    entry_hash = db.Column(db.String(64), default='')

    def compute_hash(self):
        payload = '|'.join([
            self.prev_hash or '',
            self.at.strftime('%Y-%m-%dT%H:%M:%S') if self.at else '',
            self.actor or '',
            self.action or '',
            self.details or '',
        ])
        return hashlib.sha256(payload.encode('utf-8')).hexdigest()


# ─── Hilfsfunktionen ─────────────────────────────────────────────────────────

def _now():
    return datetime.utcnow()


def _actor():
    return session.get('admin_username', 'system')


def _audit(election_id, action, details='', actor=None):
    """Hängt einen Eintrag an die Protokollkette an (ohne commit)."""
    prev = (AuditLog.query.filter_by(election_id=election_id)
            .order_by(AuditLog.id.desc()).first())
    entry = AuditLog(election_id=election_id, at=_now(),
                     actor=actor if actor is not None else _actor(),
                     action=action, details=details,
                     prev_hash=prev.entry_hash if prev else '')
    entry.entry_hash = entry.compute_hash()
    db.session.add(entry)
    return entry


def verify_audit_chain(election_id):
    """Prüft die Hashkette. Gibt (ok, index_des_ersten_fehlers) zurück."""
    entries = (AuditLog.query.filter_by(election_id=election_id)
               .order_by(AuditLog.id.asc()).all())
    prev_hash = ''
    for idx, entry in enumerate(entries):
        if (entry.prev_hash or '') != prev_hash:
            return False, idx
        if entry.compute_hash() != entry.entry_hash:
            return False, idx
        prev_hash = entry.entry_hash
    return True, None


def _hash_token(raw):
    return hashlib.sha256(raw.strip().upper().encode('utf-8')).hexdigest()


def _new_token():
    """Zugangscode mit ca. 128 Bit Entropie, in Blöcken für die Postversion."""
    raw = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(25))
    return '-'.join(raw[i:i + 5] for i in range(0, 25, 5))


def _new_receipt_code():
    while True:
        raw = ''.join(secrets.choice(CODE_ALPHABET) for _ in range(8))
        code = f'{raw[:4]}-{raw[4:]}'
        if not Ballot.query.filter_by(receipt_code=code).first():
            return code


def _ballot_hash(election, receipt_code, answers, weight):
    canonical = json.dumps(answers, sort_keys=True, separators=(',', ':'),
                           ensure_ascii=False)
    payload = f'{election.public_id}|{receipt_code}|{canonical}|{weight:.6f}'
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def compute_urn_fingerprint(election):
    """Gesamtprüfsumme der Urne – über die sortierten Stimmzettel-Hashes."""
    hashes = sorted(b.ballot_hash for b in
                    Ballot.query.filter_by(election_id=election.id).all())
    joined = '\n'.join(hashes)
    return hashlib.sha256(joined.encode('utf-8')).hexdigest()


# ─── CSRF (leichtgewichtig, ohne Zusatzabhängigkeit) ─────────────────────────

def csrf_token():
    token = session.get('_csrf')
    if not token:
        token = secrets.token_urlsafe(32)
        session['_csrf'] = token
    return token


def _check_csrf():
    sent = request.form.get('_csrf', '')
    expected = session.get('_csrf', '')
    return bool(expected) and secrets.compare_digest(sent, expected)


app.jinja_env.globals['csrf_token'] = csrf_token


# ─── Zeitzonen ───────────────────────────────────────────────────────────────

def to_local(dt, election):
    if not dt:
        return None
    return dt.replace(tzinfo=timezone.utc).astimezone(election.tz)


def fmt_local(dt, election, with_time=True):
    local = to_local(dt, election)
    if not local:
        return '–'
    return local.strftime('%d.%m.%Y %H:%M' if with_time else '%d.%m.%Y')


def parse_local_datetime(value, election):
    """Wandelt die Eingabe eines <input type=datetime-local> in UTC um."""
    value = (value or '').strip()
    if not value:
        return None
    for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            naive = datetime.strptime(value, fmt)
        except ValueError:
            continue
        return (naive.replace(tzinfo=election.tz)
                .astimezone(timezone.utc).replace(tzinfo=None))
    return None


def to_input_value(dt, election):
    local = to_local(dt, election)
    return local.strftime('%Y-%m-%dT%H:%M') if local else ''


app.jinja_env.globals['fmt_local'] = fmt_local
app.jinja_env.globals['to_input_value'] = to_input_value


# ─── Statuslogik ─────────────────────────────────────────────────────────────

def refresh_status(election):
    """Schliesst eine Abstimmung automatisch nach Ablauf der Frist."""
    if election.status == 'open' and election.closes_at and _now() >= election.closes_at:
        close_election(election, actor='system (Fristablauf)')
        return True
    return False


def voting_is_live(election):
    if election.status != 'open':
        return False
    if election.opens_at and _now() < election.opens_at:
        return False
    if election.closes_at and _now() >= election.closes_at:
        return False
    return True


def close_election(election, actor=None):
    election.status = 'closed'
    election.closed_at = _now()
    election.urn_fingerprint = compute_urn_fingerprint(election)
    ballots = Ballot.query.filter_by(election_id=election.id).count()
    _audit(election.id, 'abstimmung_geschlossen',
           f'Urne geschlossen. {ballots} Stimmzettel. '
           f'Fingerabdruck: {election.urn_fingerprint}', actor=actor)
    db.session.commit()


# ─── Auszählung ──────────────────────────────────────────────────────────────

def _fraction_ok(value, total, fraction):
    """value >= fraction * total, ganzzahlig gerechnet wo möglich."""
    num, den = fraction
    if fraction == (1, 2):          # absolute Mehrheit: echt mehr als die Hälfte
        return value * 2 > total
    return value * den >= total * num


def evaluate_question(question, tallies, totals):
    """Bewertet einen Ja/Nein-Antrag gegen das hinterlegte Mehrheitserfordernis.

    tallies: {'ja': {'heads': x, 'weight': y}, ...}
    totals:  {'heads': …, 'weight': …, 'eligible_heads': …, 'eligible_weight': …}
    Gibt je Zählweise (heads/weight) ein Ergebnisdictionary zurück.
    """
    result = {}
    for mode, total_key, eligible_key in (('heads', 'heads', 'eligible_heads'),
                                          ('weight', 'weight', 'eligible_weight')):
        ja = tallies.get('ja', {}).get(mode, 0)
        nein = tallies.get('nein', {}).get(mode, 0)
        enth = tallies.get('enthaltung', {}).get(mode, 0)

        if question.majority_base == 'gueltige':
            base = ja + nein
        elif question.majority_base == 'abgegebene':
            base = ja + nein + enth
        else:
            base = totals.get(eligible_key, 0)

        if question.majority_type == 'einfach':
            passed = ja > nein
        elif question.majority_type == 'einstimmig':
            passed = nein == 0 and ja > 0 and (
                base == 0 or _fraction_ok(ja, base, (1, 1)))
        else:
            fraction = MAJORITY_FRACTIONS.get(question.majority_type, (1, 2))
            passed = base > 0 and _fraction_ok(ja, base, fraction)

        result[mode] = {'ja': ja, 'nein': nein, 'enthaltung': enth,
                        'basis': base, 'angenommen': passed}
    return result


def compute_results(election):
    """Zählt die Urne aus. Liefert ein vollständiges Ergebnisdictionary."""
    ballots = Ballot.query.filter_by(election_id=election.id).all()
    voters = Voter.query.filter_by(election_id=election.id, eligible=True).all()

    eligible_heads = len(voters)
    eligible_weight = round(sum(v.weight for v in voters), 6)
    cast_heads = len(ballots)
    cast_weight = round(sum(b.weight for b in ballots), 6)

    totals = {'heads': cast_heads, 'weight': cast_weight,
              'eligible_heads': eligible_heads, 'eligible_weight': eligible_weight}

    turnout_heads = (cast_heads / eligible_heads * 100) if eligible_heads else 0.0
    turnout_weight = (cast_weight / eligible_weight * 100) if eligible_weight else 0.0

    questions = []
    for question in election.questions:
        tallies = {opt['value']: {'heads': 0, 'weight': 0.0} for opt in question.options}
        invalid = {'heads': 0, 'weight': 0.0}
        for ballot in ballots:
            answer = ballot.answers.get(str(question.id))
            values = answer if isinstance(answer, list) else ([answer] if answer else [])
            counted = False
            for value in values:
                if value in tallies:
                    tallies[value]['heads'] += 1
                    tallies[value]['weight'] = round(
                        tallies[value]['weight'] + ballot.weight, 6)
                    counted = True
            if not counted:
                invalid['heads'] += 1
                invalid['weight'] = round(invalid['weight'] + ballot.weight, 6)

        entry = {'question': question, 'tallies': tallies, 'invalid': invalid,
                 'evaluation': None}
        if question.qtype == 'janein':
            entry['evaluation'] = evaluate_question(question, tallies, totals)
        questions.append(entry)

    quorum_heads_ok = turnout_heads >= (election.quorum_heads or 0)
    quorum_weight_ok = turnout_weight >= (election.quorum_weight or 0)

    return {
        'eligible_heads': eligible_heads,
        'eligible_weight': eligible_weight,
        'cast_heads': cast_heads,
        'cast_weight': cast_weight,
        'turnout_heads': turnout_heads,
        'turnout_weight': turnout_weight,
        'quorum_heads_ok': quorum_heads_ok,
        'quorum_weight_ok': quorum_weight_ok,
        'quorum_ok': quorum_heads_ok and quorum_weight_ok,
        'questions': questions,
        'fingerprint': election.urn_fingerprint or compute_urn_fingerprint(election),
    }


# ─── Öffentliche Routen: Stimmabgabe ─────────────────────────────────────────

def _info(headline, message, tone='info', election=None):
    return render_template('voting/info.html', headline=headline, message=message,
                           tone=tone, election=election)


def _collect_answers(questions, form):
    """Liest die Stimmzettel-Eingaben aus. Gibt (answers, fehler) zurück."""
    answers, errors = {}, []
    for question in questions:
        key = f'q_{question.id}'
        valid = {opt['value'] for opt in question.options}
        if question.qtype == 'mehrfachauswahl':
            chosen = [v for v in form.getlist(key) if v in valid]
            answers[str(question.id)] = chosen
            if not chosen:
                errors.append(question.id)
        else:
            value = form.get(key, '')
            if value not in valid:
                errors.append(question.id)
                answers[str(question.id)] = ''
            else:
                answers[str(question.id)] = value
    return answers, errors


@voting_bp.route('/stimme/', methods=['GET', 'POST'])
def vote_entry():
    """Codeeingabe für alle, die den Zugangscode auf Papier erhalten haben."""
    error = None
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if code:
            token = VotingToken.query.filter_by(token_hash=_hash_token(code)).first()
            if token:
                return redirect(url_for('voting.vote', token=code.strip().upper()))
        error = 'Dieser Zugangscode ist unbekannt. Bitte prüfen Sie Ihre Eingabe.'
    return render_template('voting/enter_code.html', error=error)


@voting_bp.route('/stimme/<token>', methods=['GET', 'POST'])
def vote(token):
    record = VotingToken.query.filter_by(token_hash=_hash_token(token)).first()
    if not record:
        return _info('Zugangscode ungültig',
                     'Dieser Zugangscode ist unbekannt. Bitte prüfen Sie den Link '
                     'aus Ihrer Einladung oder wenden Sie sich an die Verwaltung.',
                     'danger'), 404

    election = Election.query.get(record.election_id)
    voter = Voter.query.get(record.voter_id)
    refresh_status(election)

    if record.revoked:
        return _info('Zugangscode nicht mehr gültig',
                     'Für dieses Stimmrecht wurde ein neuer Zugangscode ausgestellt. '
                     'Bitte verwenden Sie den zuletzt zugesandten Code.', 'warning',
                     election)
    if not voter.eligible:
        return _info('Kein Stimmrecht',
                     'Für dieses Stimmrecht ist im Stimmregister keine Berechtigung '
                     'hinterlegt. Bitte wenden Sie sich an die Verwaltung.', 'warning',
                     election)
    if voter.voted or record.used_on:
        return _info('Stimme bereits abgegeben',
                     'Für dieses Stimmrecht wurde bereits abgestimmt. Eine zweite '
                     'Stimmabgabe ist nicht möglich.', 'warning', election)
    if election.status == 'draft':
        return _info('Abstimmung noch nicht eröffnet',
                     'Die Abstimmung wurde noch nicht freigegeben.', 'info', election)
    if election.status in ('closed', 'published') or (
            election.closes_at and _now() >= election.closes_at):
        return _info('Abstimmung beendet',
                     'Die Abstimmungsfrist ist abgelaufen. Es können keine Stimmen '
                     'mehr abgegeben werden.', 'warning', election)
    if election.opens_at and _now() < election.opens_at:
        return _info('Abstimmung noch nicht geöffnet',
                     f'Die Stimmabgabe ist ab {fmt_local(election.opens_at, election)} '
                     'möglich.', 'info', election)

    questions = list(election.questions)
    errors = []

    if request.method == 'POST':
        if not _check_csrf():
            return _info('Sitzung abgelaufen',
                         'Bitte öffnen Sie den Link aus Ihrer Einladung erneut und '
                         'geben Sie Ihre Stimme noch einmal ab.', 'warning', election)

        answers, errors = _collect_answers(questions, request.form)
        if not errors:
            today = date.today()
            # Zwei atomare Sperren – beide müssen genau eine Zeile treffen.
            used = (db.session.query(VotingToken)
                    .filter(VotingToken.id == record.id,
                            VotingToken.used_on.is_(None),
                            VotingToken.revoked.is_(False))
                    .update({'used_on': today}, synchronize_session=False))
            marked = (db.session.query(Voter)
                      .filter(Voter.id == voter.id, Voter.voted.is_(False))
                      .update({'voted': True, 'voted_on': today},
                              synchronize_session=False))
            if used != 1 or marked != 1:
                db.session.rollback()
                return _info('Stimme bereits abgegeben',
                             'Für dieses Stimmrecht wurde bereits abgestimmt.',
                             'warning', election)

            receipt = _new_receipt_code()
            weight = voter.weight if election.weighted else 1.0
            ballot = Ballot(election_id=election.id, receipt_code=receipt,
                            weight=weight, cast_on=today,
                            answers_json=json.dumps(answers, ensure_ascii=False,
                                                    sort_keys=True))
            ballot.ballot_hash = _ballot_hash(election, receipt, answers, weight)
            db.session.add(ballot)
            # Protokolleintrag bewusst ohne Person, ohne Quittungscode, ohne Uhrzeit
            _audit(election.id, 'stimmabgabe',
                   f'Anonyme Stimmabgabe am {today.strftime("%d.%m.%Y")}',
                   actor='urne')
            db.session.commit()

            if election.send_vote_confirmation and voter.email:
                _send_vote_confirmation(election, voter)

            session['receipt'] = {'code': receipt, 'election': election.public_id,
                                  'hash': ballot.ballot_hash}
            return redirect(url_for('voting.receipt'))

    return render_template('voting/ballot.html', election=election, voter=voter,
                           questions=questions, token=token, errors=errors,
                           form=request.form)


@voting_bp.route('/quittung')
def receipt():
    # Bewusst nicht aus der Sitzung entfernt: die Quittung muss ein Neuladen der
    # Seite überstehen, sonst geht der einzige Beleg der Person verloren. Sie
    # verfällt mit der Sitzung bzw. über „Quittung schliessen".
    data = session.get('receipt')
    if not data:
        return redirect(url_for('voting.vote_entry'))
    election = Election.query.filter_by(public_id=data['election']).first()
    return render_template('voting/receipt.html', election=election,
                           code=data['code'], ballot_hash=data['hash'])


@voting_bp.route('/quittung/schliessen', methods=['POST'])
def receipt_close():
    session.pop('receipt', None)
    return redirect(url_for('voting.vote_entry'))


@voting_bp.route('/abstimmung/<public_id>/verifikation')
def public_verification(public_id):
    election = Election.query.filter_by(public_id=public_id).first_or_404()
    refresh_status(election)
    if election.status not in ('closed', 'published'):
        return _info('Noch keine Ergebnisse',
                     'Die Abstimmung läuft noch. Die Urnenliste wird nach dem '
                     'Schliessen der Abstimmung veröffentlicht.', 'info', election)
    if election.status != 'published':
        return _info('Ergebnis noch nicht freigegeben',
                     'Die Abstimmung ist geschlossen. Das Ergebnis wird nach der '
                     'Feststellung durch die Versammlungsleitung veröffentlicht.',
                     'info', election)

    ballots = (Ballot.query.filter_by(election_id=election.id)
               .order_by(Ballot.receipt_code.asc()).all())
    results = compute_results(election)
    return render_template('voting/verification.html', election=election,
                           ballots=ballots, results=results,
                           show_answers=election.verification_mode == 'voll',
                           mode=election.verification_mode)


# ─── E-Mail-Versand ──────────────────────────────────────────────────────────

def _vote_link(token):
    base = app.config.get('BASE_URL') or request.url_root.rstrip('/')
    return f"{base}{url_for('voting.vote', token=token)}"


def _render_invitation(election, voter, token):
    body = election.invitation_body or (
        'Guten Tag {name},\n\n'
        'für die Abstimmung "{titel}" erhalten Sie hiermit Ihre persönlichen '
        'Stimmunterlagen.\n\n'
        'Einheit: {einheit}\n'
        'Ihr persönlicher Zugangscode: {code}\n\n'
        'Direkt abstimmen:\n{link}\n\n'
        'Die Abstimmung endet am {frist}.\n\n'
        'Ihre Stimme wird anonym gezählt: Der Zugangscode wird beim Abstimmen '
        'entwertet, der Stimmzettel selbst enthält keinen Bezug zu Ihrer Person.\n\n'
        'Bitte geben Sie diesen Code nicht weiter – er kann nur einmal verwendet '
        'werden.\n')
    values = {
        '{name}': voter.name or '',
        '{einheit}': voter.unit or '',
        '{titel}': election.title or '',
        '{code}': token,
        '{link}': _vote_link(token),
        '{frist}': fmt_local(election.closes_at, election) if election.closes_at
                   else 'dem in der Einladung genannten Termin',
        '{gewicht}': f'{voter.weight:g}',
    }
    subject = election.invitation_subject or 'Ihre Stimmunterlagen: {titel}'
    for key, value in values.items():
        body = body.replace(key, value)
        subject = subject.replace(key, value)
    return subject, body


def send_invitations(election, pairs):
    """pairs: Liste von (Voter, Klartext-Token). Gibt (gesendet, fehler) zurück."""
    cfg = MailConfig.query.first()
    if not cfg or not cfg.enabled or not cfg.from_email:
        return 0, ['E-Mail-Versand ist nicht konfiguriert '
                   '(Admin → E-Mail-Einstellungen).']
    sent, errors = 0, []
    for voter, token in pairs:
        if not voter.email or '@' not in voter.email:
            continue
        subject, body = _render_invitation(election, voter, token)
        try:
            _send_raw_email(cfg, [voter.email], subject, body)
            record = voter.active_token
            if record:
                record.sent_at = _now()
            sent += 1
        except Exception as exc:                       # pragma: no cover
            app.logger.error('Stimmunterlagen an %s fehlgeschlagen: %s',
                             voter.email, exc)
            errors.append(f'{voter.name} <{voter.email}>: {exc}')
    return sent, errors


def _send_vote_confirmation(election, voter):
    """Bestätigung OHNE Quittungscode – der Code darf die Anonymität nicht brechen."""
    cfg = MailConfig.query.first()
    if not cfg or not cfg.enabled or not cfg.from_email:
        return
    try:
        _send_raw_email(
            cfg, [voter.email], f'Ihre Stimme wurde gezählt: {election.title}',
            f'Guten Tag {voter.name},\n\n'
            f'Ihre Stimme zur Abstimmung "{election.title}" ist eingegangen und '
            f'wurde gezählt.\n\n'
            f'Aus Gründen des Stimmgeheimnisses enthält diese Nachricht weder Ihren '
            f'Quittungscode noch Ihre Stimme. Den Quittungscode haben Sie nach der '
            f'Stimmabgabe im Browser erhalten.\n')
    except Exception as exc:                           # pragma: no cover
        app.logger.error('Bestätigungsmail fehlgeschlagen: %s', exc)


# ─── Admin: Hilfen ───────────────────────────────────────────────────────────

def csrf_protect(view):
    """Schützt Adminaktionen gegen Cross-Site-Request-Forgery."""
    from functools import wraps

    @wraps(view)
    def wrapper(*args, **kwargs):
        if request.method == 'POST' and not _check_csrf():
            flash('Sicherheitsprüfung fehlgeschlagen. Bitte erneut versuchen.', 'error')
            return redirect(url_for('voting.admin_elections'))
        return view(*args, **kwargs)
    return wrapper


def _get_election(eid):
    election = Election.query.get_or_404(eid)
    refresh_status(election)
    return election


def _issue_tokens(election, voters):
    """Erzeugt neue Einmal-Codes und entwertet vorhandene. Klartext nur hier."""
    issued = []
    for voter in voters:
        for old in voter.tokens:
            if not old.revoked and old.used_on is None:
                old.revoked = True
        raw = _new_token()
        db.session.add(VotingToken(election_id=election.id, voter_id=voter.id,
                                   token_hash=_hash_token(raw)))
        issued.append((voter, raw))
    return issued


def _parse_voter_rows(text):
    """Liest 'Name;E-Mail;Einheit;Stimmgewicht' aus eingefügtem Text/CSV."""
    rows, errors = [], []
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        delimiter = ';' if ';' in line else ('\t' if '\t' in line else ',')
        parts = [p.strip().strip('"') for p in line.split(delimiter)]
        if number == 1 and parts[0].lower() in ('name', 'nachname', 'eigentümer'):
            continue                                   # Kopfzeile überspringen
        name = parts[0] if parts else ''
        if not name:
            continue
        email = parts[1] if len(parts) > 1 else ''
        unit = parts[2] if len(parts) > 2 else ''
        weight = 1.0
        if len(parts) > 3 and parts[3]:
            try:
                weight = float(parts[3].replace(',', '.'))
            except ValueError:
                errors.append(f'Zeile {number}: Stimmgewicht "{parts[3]}" '
                              f'ist keine Zahl – 1,0 verwendet.')
        rows.append({'name': name, 'email': email, 'unit': unit, 'weight': weight})
    return rows, errors


# ─── Admin: Übersicht und Stammdaten ─────────────────────────────────────────

@voting_bp.route('/admin/abstimmungen')
@login_required
def admin_elections():
    elections = Election.query.order_by(Election.created_at.desc()).all()
    for election in elections:
        refresh_status(election)
    stats = {}
    for election in elections:
        stats[election.id] = {
            'voters': Voter.query.filter_by(election_id=election.id, eligible=True).count(),
            'voted': Voter.query.filter_by(election_id=election.id, voted=True).count(),
        }
    return render_template('admin/voting/list.html', elections=elections, stats=stats)


@voting_bp.route('/admin/abstimmungen/neu', methods=['POST'])
@login_required
@csrf_protect
def admin_election_new():
    election = Election(title=request.form.get('title', '').strip() or 'Neue Abstimmung')
    db.session.add(election)
    db.session.flush()
    _audit(election.id, 'abstimmung_angelegt', f'Titel: {election.title}')
    db.session.commit()
    flash('Abstimmung angelegt.', 'success')
    return redirect(url_for('voting.admin_election', eid=election.id))


@voting_bp.route('/admin/abstimmungen/<int:eid>', methods=['GET', 'POST'])
@login_required
@csrf_protect
def admin_election(eid):
    election = _get_election(eid)

    if request.method == 'POST':
        election.title = request.form.get('title', '').strip() or election.title
        election.description = request.form.get('description', '').strip()
        election.timezone_name = request.form.get('timezone_name', '').strip() or 'Europe/Madrid'
        election.opens_at = parse_local_datetime(request.form.get('opens_at'), election)
        election.closes_at = parse_local_datetime(request.form.get('closes_at'), election)
        election.weighted = 'weighted' in request.form
        election.double_majority = 'double_majority' in request.form
        election.verification_mode = request.form.get('verification_mode', 'codes')
        election.send_vote_confirmation = 'send_vote_confirmation' in request.form
        election.invitation_subject = request.form.get('invitation_subject', '').strip()
        election.invitation_body = request.form.get('invitation_body', '').strip()
        for field in ('quorum_heads', 'quorum_weight'):
            try:
                setattr(election, field,
                        float((request.form.get(field) or '0').replace(',', '.')))
            except ValueError:
                setattr(election, field, 0.0)
        _audit(election.id, 'einstellungen_geaendert', 'Rahmendaten aktualisiert')
        db.session.commit()
        flash('Einstellungen gespeichert.', 'success')
        return redirect(url_for('voting.admin_election', eid=eid))

    voters = Voter.query.filter_by(election_id=eid).order_by(Voter.unit, Voter.name).all()
    eligible = [v for v in voters if v.eligible]
    ballots = Ballot.query.filter_by(election_id=eid).count()
    return render_template(
        'admin/voting/detail.html', election=election, voters=voters,
        eligible_count=len(eligible),
        eligible_weight=round(sum(v.weight for v in eligible), 4),
        voted_count=sum(1 for v in eligible if v.voted),
        ballots=ballots, majority_types=MAJORITY_TYPES,
        majority_bases=MAJORITY_BASES, verification_modes=VERIFICATION_MODES,
        live=voting_is_live(election))


@voting_bp.route('/admin/abstimmungen/<int:eid>/loeschen', methods=['POST'])
@login_required
@csrf_protect
def admin_election_delete(eid):
    election = Election.query.get_or_404(eid)
    if election.status in ('open', 'closed', 'published') and \
            request.form.get('confirm') != election.title:
        flash('Zum Löschen einer durchgeführten Abstimmung muss der Titel exakt '
              'bestätigt werden.', 'error')
        return redirect(url_for('voting.admin_election', eid=eid))
    Ballot.query.filter_by(election_id=eid).delete()
    VotingToken.query.filter_by(election_id=eid).delete()
    AuditLog.query.filter_by(election_id=eid).delete()
    db.session.delete(election)
    db.session.commit()
    flash('Abstimmung gelöscht.', 'success')
    return redirect(url_for('voting.admin_elections'))


# ─── Admin: Beschlussanträge ─────────────────────────────────────────────────

@voting_bp.route('/admin/abstimmungen/<int:eid>/fragen', methods=['GET', 'POST'])
@login_required
@csrf_protect
def admin_questions(eid):
    election = _get_election(eid)

    if request.method == 'POST':
        if not election.is_editable:
            flash('Die Anträge können nach der Eröffnung nicht mehr geändert werden.',
                  'error')
            return redirect(url_for('voting.admin_questions', eid=eid))
        try:
            payload = json.loads(request.form.get('questions_json', '[]'))
        except (json.JSONDecodeError, ValueError):
            flash('Die Anträge konnten nicht gelesen werden.', 'error')
            return redirect(url_for('voting.admin_questions', eid=eid))

        Question.query.filter_by(election_id=eid).delete()
        for index, item in enumerate(payload):
            text = (item.get('text') or '').strip()
            if not text:
                continue
            question = Question(
                election_id=eid, order_index=index, text=text,
                description=(item.get('description') or '').strip(),
                qtype=item.get('qtype', 'janein'),
                majority_type=item.get('majority_type', 'einfach'),
                majority_base=item.get('majority_base', 'gueltige'))
            options = []
            for opt in item.get('options', []):
                label = (opt.get('label') or '').strip()
                if label:
                    # Stabile, ASCII-sichere Werte – der Text darf sich später
                    # nicht auf die gespeicherten Stimmzettel auswirken.
                    options.append({'value': opt.get('value') or f'opt{len(options) + 1}',
                                    'label': label})
            question.options = options
            db.session.add(question)
        _audit(eid, 'antraege_geaendert', f'{len(payload)} Anträge gespeichert')
        db.session.commit()
        flash('Anträge gespeichert.', 'success')
        return redirect(url_for('voting.admin_questions', eid=eid))

    return render_template('admin/voting/questions.html', election=election,
                           majority_types=MAJORITY_TYPES, majority_bases=MAJORITY_BASES)


# ─── Admin: Stimmregister ────────────────────────────────────────────────────

@voting_bp.route('/admin/abstimmungen/<int:eid>/stimmregister', methods=['GET', 'POST'])
@login_required
@csrf_protect
def admin_voters(eid):
    election = _get_election(eid)

    if request.method == 'POST':
        action = request.form.get('action', '')

        if action == 'add':
            weight = (request.form.get('weight') or '1').replace(',', '.')
            try:
                weight = float(weight)
            except ValueError:
                weight = 1.0
            voter = Voter(election_id=eid,
                          name=request.form.get('name', '').strip(),
                          email=request.form.get('email', '').strip(),
                          unit=request.form.get('unit', '').strip(),
                          proxy_name=request.form.get('proxy_name', '').strip(),
                          note=request.form.get('note', '').strip(),
                          weight=weight)
            if not voter.name:
                flash('Bitte einen Namen angeben.', 'error')
            else:
                db.session.add(voter)
                _audit(eid, 'stimmrecht_aufgenommen',
                       f'{voter.name} / Einheit {voter.unit or "–"} / '
                       f'Gewicht {voter.weight:g}')
                db.session.commit()
                flash(f'{voter.name} ins Stimmregister aufgenommen.', 'success')

        elif action == 'import':
            if not election.is_editable:
                flash('Nach der Eröffnung kann das Stimmregister nur noch einzeln '
                      'ergänzt werden.', 'error')
                return redirect(url_for('voting.admin_voters', eid=eid))
            rows, errors = _parse_voter_rows(request.form.get('import_text', ''))
            replace = 'replace' in request.form
            if replace:
                Voter.query.filter_by(election_id=eid).delete()
            for row in rows:
                db.session.add(Voter(election_id=eid, **row))
            _audit(eid, 'stimmregister_import',
                   f'{len(rows)} Stimmrechte importiert'
                   f'{" (vorheriges Register ersetzt)" if replace else ""}')
            db.session.commit()
            for message in errors:
                flash(message, 'error')
            flash(f'{len(rows)} Einträge importiert.', 'success')

    voters = Voter.query.filter_by(election_id=eid).order_by(Voter.unit, Voter.name).all()
    eligible = [v for v in voters if v.eligible]
    return render_template('admin/voting/voters.html', election=election, voters=voters,
                           total_weight=round(sum(v.weight for v in eligible), 4),
                           eligible_count=len(eligible))


@voting_bp.route('/admin/abstimmungen/<int:eid>/stimmregister/<int:vid>',
                 methods=['POST'])
@login_required
@csrf_protect
def admin_voter_update(eid, vid):
    election = _get_election(eid)
    voter = Voter.query.filter_by(id=vid, election_id=eid).first_or_404()
    action = request.form.get('action', '')

    if action == 'delete':
        if voter.voted:
            flash('Dieser Eintrag hat bereits abgestimmt und darf aus '
                  'Beweisgründen nicht gelöscht werden.', 'error')
        else:
            _audit(eid, 'stimmrecht_entfernt', f'{voter.name} / {voter.unit or "–"}')
            db.session.delete(voter)
            db.session.commit()
            flash('Eintrag gelöscht.', 'success')

    elif action == 'toggle_eligible':
        if voter.voted:
            flash('Nach abgegebener Stimme kann das Stimmrecht nicht mehr '
                  'geändert werden.', 'error')
        else:
            voter.eligible = not voter.eligible
            _audit(eid, 'stimmrecht_geaendert',
                   f'{voter.name}: {"berechtigt" if voter.eligible else "gesperrt"}')
            db.session.commit()

    elif action == 'edit':
        voter.name = request.form.get('name', '').strip() or voter.name
        voter.email = request.form.get('email', '').strip()
        voter.unit = request.form.get('unit', '').strip()
        voter.proxy_name = request.form.get('proxy_name', '').strip()
        voter.note = request.form.get('note', '').strip()
        try:
            voter.weight = float((request.form.get('weight') or '1').replace(',', '.'))
        except ValueError:
            pass
        _audit(eid, 'stimmrecht_geaendert',
               f'{voter.name} / Einheit {voter.unit or "–"} / '
               f'Gewicht {voter.weight:g}')
        db.session.commit()
        flash('Eintrag aktualisiert.', 'success')

    elif action == 'reissue':
        if voter.voted:
            flash('Für dieses Stimmrecht wurde bereits abgestimmt – ein neuer '
                  'Code würde die Abstimmung verfälschen.', 'error')
            return redirect(url_for('voting.admin_voters', eid=eid))
        issued = _issue_tokens(election, [voter])
        _audit(eid, 'code_neu_ausgestellt',
               f'{voter.name} / {voter.unit or "–"} – alter Code entwertet')
        db.session.commit()
        sent, errors = 0, []
        if 'send' in request.form:
            sent, errors = send_invitations(election, issued)
            db.session.commit()
            for message in errors:
                flash(message, 'error')
        return render_template('admin/voting/codes.html', election=election,
                               issued=issued, sent=sent, vote_link=_vote_link,
                               headline='Neuer Zugangscode')

    return redirect(url_for('voting.admin_voters', eid=eid))


# ─── Admin: Durchführung ─────────────────────────────────────────────────────

@voting_bp.route('/admin/abstimmungen/<int:eid>/oeffnen', methods=['POST'])
@login_required
@csrf_protect
def admin_open(eid):
    election = _get_election(eid)
    if election.status != 'draft':
        flash('Die Abstimmung wurde bereits eröffnet.', 'error')
        return redirect(url_for('voting.admin_election', eid=eid))

    voters = Voter.query.filter_by(election_id=eid, eligible=True).all()
    if not election.questions:
        flash('Bitte zuerst mindestens einen Beschlussantrag anlegen.', 'error')
        return redirect(url_for('voting.admin_questions', eid=eid))
    if not voters:
        flash('Das Stimmregister ist leer.', 'error')
        return redirect(url_for('voting.admin_voters', eid=eid))

    issued = _issue_tokens(election, voters)
    election.status = 'open'
    if not election.opens_at:
        election.opens_at = _now()
    _audit(eid, 'abstimmung_eroeffnet',
           f'{len(voters)} Stimmrechte, Summe Stimmgewicht '
           f'{sum(v.weight for v in voters):g}. '
           f'Frist bis {fmt_local(election.closes_at, election)}. '
           f'{len(election.questions)} Anträge.')
    db.session.commit()

    sent, errors = 0, []
    if 'send_mails' in request.form:
        sent, errors = send_invitations(election, issued)
        _audit(eid, 'unterlagen_versendet', f'{sent} Einladungen per E-Mail versendet')
        db.session.commit()
        for message in errors:
            flash(message, 'error')

    return render_template('admin/voting/codes.html', election=election,
                           issued=issued, sent=sent, vote_link=_vote_link,
                           headline='Abstimmung eröffnet – Zugangscodes')


@voting_bp.route('/admin/abstimmungen/<int:eid>/codes-erneuern', methods=['POST'])
@login_required
@csrf_protect
def admin_reissue(eid):
    election = _get_election(eid)
    if election.status != 'open':
        flash('Codes können nur bei laufender Abstimmung neu ausgestellt werden.',
              'error')
        return redirect(url_for('voting.admin_election', eid=eid))

    voters = Voter.query.filter_by(election_id=eid, eligible=True, voted=False).all()
    if not voters:
        flash('Alle Stimmberechtigten haben bereits abgestimmt.', 'success')
        return redirect(url_for('voting.admin_election', eid=eid))

    issued = _issue_tokens(election, voters)
    _audit(eid, 'codes_neu_ausgestellt',
           f'{len(voters)} neue Zugangscodes; die bisherigen wurden entwertet')
    db.session.commit()

    sent, errors = 0, []
    if 'send_mails' in request.form:
        sent, errors = send_invitations(election, issued)
        _audit(eid, 'erinnerung_versendet', f'{sent} Erinnerungen per E-Mail versendet')
        db.session.commit()
        for message in errors:
            flash(message, 'error')

    return render_template('admin/voting/codes.html', election=election,
                           issued=issued, sent=sent, vote_link=_vote_link,
                           headline='Neue Zugangscodes (Erinnerung)')


@voting_bp.route('/admin/abstimmungen/<int:eid>/schliessen', methods=['POST'])
@login_required
@csrf_protect
def admin_close(eid):
    election = _get_election(eid)
    if election.status != 'open':
        flash('Die Abstimmung ist nicht geöffnet.', 'error')
        return redirect(url_for('voting.admin_election', eid=eid))
    close_election(election)
    flash('Abstimmung geschlossen. Die Urne ist versiegelt.', 'success')
    return redirect(url_for('voting.admin_results', eid=eid))


@voting_bp.route('/admin/abstimmungen/<int:eid>/veroeffentlichen', methods=['POST'])
@login_required
@csrf_protect
def admin_publish(eid):
    election = _get_election(eid)
    if election.status != 'closed':
        flash('Nur eine geschlossene Abstimmung kann veröffentlicht werden.', 'error')
        return redirect(url_for('voting.admin_election', eid=eid))
    election.status = 'published'
    election.published_at = _now()
    _audit(eid, 'ergebnis_veroeffentlicht',
           f'Ergebnis freigegeben. Urnen-Fingerabdruck: {election.urn_fingerprint}')
    db.session.commit()
    flash('Ergebnis veröffentlicht. Die Verifikationsseite ist jetzt erreichbar.',
          'success')
    return redirect(url_for('voting.admin_results', eid=eid))


@voting_bp.route('/admin/abstimmungen/<int:eid>/ergebnis')
@login_required
def admin_results(eid):
    election = _get_election(eid)
    if election.status == 'draft':
        flash('Die Abstimmung wurde noch nicht durchgeführt.', 'error')
        return redirect(url_for('voting.admin_election', eid=eid))
    results = compute_results(election)
    chain_ok, chain_error = verify_audit_chain(eid)
    fingerprint_ok = (not election.urn_fingerprint or
                      election.urn_fingerprint == compute_urn_fingerprint(election))
    return render_template('admin/voting/results.html', election=election,
                           results=results, chain_ok=chain_ok,
                           chain_error=chain_error, fingerprint_ok=fingerprint_ok,
                           live=voting_is_live(election))


@voting_bp.route('/admin/abstimmungen/<int:eid>/protokoll')
@login_required
def admin_audit(eid):
    election = _get_election(eid)
    entries = (AuditLog.query.filter_by(election_id=eid)
               .order_by(AuditLog.id.asc()).all())
    chain_ok, chain_error = verify_audit_chain(eid)
    return render_template('admin/voting/audit.html', election=election,
                           entries=entries, chain_ok=chain_ok, chain_error=chain_error)


# ─── Admin: Exporte ──────────────────────────────────────────────────────────

def _csv_response(rows, filename):
    output = io.StringIO()
    output.write('﻿')                       # BOM, damit Excel UTF-8 erkennt
    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
    writer.writerows(rows)
    return Response(output.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={filename}'})


@voting_bp.route('/admin/abstimmungen/<int:eid>/export/urne.csv')
@login_required
def admin_export_ballots(eid):
    """Urnenliste für das Protokoll – nach Quittungscode sortiert, ohne Personen."""
    election = _get_election(eid)
    if election.status == 'open':
        flash('Die Urnenliste ist erst nach dem Schliessen der Abstimmung abrufbar.',
              'error')
        return redirect(url_for('voting.admin_election', eid=eid))

    questions = list(election.questions)
    header = ['Quittungscode', 'Stimmgewicht', 'Datum']
    header += [f'TOP {i}: {q.text[:60]}' for i, q in enumerate(questions, start=1)]
    header.append('Stimmzettel-Hash')

    rows = [header]
    ballots = (Ballot.query.filter_by(election_id=eid)
               .order_by(Ballot.receipt_code.asc()).all())
    for ballot in ballots:
        answers = ballot.answers
        row = [ballot.receipt_code, f'{ballot.weight:g}',
               ballot.cast_on.strftime('%d.%m.%Y') if ballot.cast_on else '']
        for question in questions:
            value = answers.get(str(question.id), '')
            labels = {opt['value']: opt['label'] for opt in question.options}
            if isinstance(value, list):
                row.append(', '.join(labels.get(v, v) for v in value))
            else:
                row.append(labels.get(value, value))
        row.append(ballot.ballot_hash)
        rows.append(row)
    rows.append([])
    rows.append(['Urnen-Fingerabdruck', election.urn_fingerprint or
                 compute_urn_fingerprint(election)])
    return _csv_response(rows, f'urne_{election.public_id}.csv')


@voting_bp.route('/admin/abstimmungen/<int:eid>/export/praesenz.csv')
@login_required
def admin_export_attendance(eid):
    """Präsenzliste: wer war stimmberechtigt und wer hat abgestimmt – ohne Inhalte."""
    election = _get_election(eid)
    rows = [['Einheit', 'Name', 'E-Mail', 'Bevollmächtigt', 'Stimmgewicht',
             'Stimmberechtigt', 'Abgestimmt', 'Datum', 'Code versendet am']]
    voters = (Voter.query.filter_by(election_id=eid)
              .order_by(Voter.unit, Voter.name).all())
    for voter in voters:
        token = voter.active_token
        rows.append([
            voter.unit, voter.name, voter.email, voter.proxy_name,
            f'{voter.weight:g}',
            'ja' if voter.eligible else 'nein',
            'ja' if voter.voted else 'nein',
            voter.voted_on.strftime('%d.%m.%Y') if voter.voted_on else '',
            fmt_local(token.sent_at, election) if token and token.sent_at else '',
        ])
    return _csv_response(rows, f'praesenzliste_{election.public_id}.csv')


@voting_bp.route('/admin/abstimmungen/<int:eid>/export/protokoll.csv')
@login_required
def admin_export_audit(eid):
    election = _get_election(eid)
    rows = [['Nr.', 'Zeitpunkt', 'Benutzer', 'Vorgang', 'Details',
             'Vorgänger-Hash', 'Eintrags-Hash']]
    entries = (AuditLog.query.filter_by(election_id=eid)
               .order_by(AuditLog.id.asc()).all())
    for number, entry in enumerate(entries, start=1):
        rows.append([number, fmt_local(entry.at, election), entry.actor,
                     entry.action, entry.details, entry.prev_hash, entry.entry_hash])
    return _csv_response(rows, f'protokoll_{election.public_id}.csv')
