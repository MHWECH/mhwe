from flask import (Flask, render_template, request, redirect, url_for,
                   session, jsonify, Response, flash, abort, send_from_directory)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime, timedelta
import json, csv, io, smtplib, ssl, os, secrets, shutil, mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formatdate
from concurrent.futures import ThreadPoolExecutor
from cryptography.fernet import Fernet, InvalidToken

# ─── App Setup ───────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(INSTANCE_DIR, exist_ok=True)
UPLOAD_DIR = os.environ.get('UPLOAD_DIR', os.path.join(INSTANCE_DIR, 'uploads'))
MAIL_ARCHIVE_DIR = os.environ.get('MAIL_ARCHIVE_DIR', os.path.join(INSTANCE_DIR, 'mail_archive'))
ALLOWED_UPLOAD_EXTENSIONS = {
    'pdf', 'jpg', 'jpeg', 'png', 'gif', 'webp', 'heic', 'txt', 'csv',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'zip',
}


def _get_or_create_secret_key():
    key_file = os.path.join(INSTANCE_DIR, '.secret_key')
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    key = secrets.token_hex(32)
    with open(key_file, 'w') as f:
        f.write(key)
    return key


def _get_or_create_mail_key():
    key_file = os.path.join(INSTANCE_DIR, '.mail_key')
    if os.path.exists(key_file):
        with open(key_file) as f:
            return f.read().strip()
    key = Fernet.generate_key().decode()
    with open(key_file, 'w') as f:
        f.write(key)
    os.chmod(key_file, 0o600)
    return key


app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', _get_or_create_secret_key())
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL', f'sqlite:///{os.path.join(INSTANCE_DIR, "formapp.db")}')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_UPLOAD_MB', 20)) * 1024 * 1024

db = SQLAlchemy(app)
_fernet = Fernet(os.environ.get('MAIL_ENCRYPTION_KEY') or _get_or_create_mail_key())
# Mails are sent in the background so a slow SMTP server doesn't block the form
_mail_executor = ThreadPoolExecutor(max_workers=2)

ENC_PREFIX = 'enc:'


def _encrypt_secret(value):
    if not value:
        return ''
    return ENC_PREFIX + _fernet.encrypt(value.encode()).decode()


def _decrypt_secret(value):
    if not value or not value.startswith(ENC_PREFIX):
        return value or ''  # legacy plaintext
    try:
        return _fernet.decrypt(value[len(ENC_PREFIX):].encode()).decode()
    except InvalidToken:
        raise RuntimeError('SMTP-Passwort kann nicht entschlüsselt werden '
                           '(Schlüssel geändert?). Bitte Passwort neu eingeben.')

# ─── Models ──────────────────────────────────────────────────────────────────

class AdminUser(db.Model):
    __tablename__ = 'admin_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)


class FormConfig(db.Model):
    __tablename__ = 'form_config'
    id = db.Column(db.Integer, primary_key=True)
    form_name = db.Column(db.String(200), nullable=False, default='Kontaktformular')
    form_description = db.Column(db.Text, default='')
    success_message = db.Column(db.Text, default='Vielen Dank! Ihre Einsendung wurde gespeichert.')
    submit_button_text = db.Column(db.String(100), default='Absenden')
    fields_json = db.Column(db.Text, default='[]')

    @property
    def fields(self):
        return json.loads(self.fields_json or '[]')

    @fields.setter
    def fields(self, value):
        self.fields_json = json.dumps(value, ensure_ascii=False)


class MailConfig(db.Model):
    __tablename__ = 'mail_config'
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=False)
    smtp_host = db.Column(db.String(200), default='')
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(200), default='')
    smtp_password = db.Column(db.String(500), default='')  # encrypted, see password
    use_tls = db.Column(db.Boolean, default=True)
    use_ssl = db.Column(db.Boolean, default=False)
    from_email = db.Column(db.String(200), default='')
    from_name = db.Column(db.String(200), default='')
    notification_email = db.Column(db.String(500), default='')
    send_confirmation = db.Column(db.Boolean, default=False)
    confirmation_email_field = db.Column(db.String(200), default='')
    notification_subject = db.Column(db.String(500), default='Neue Formulareinsendung')
    notification_body = db.Column(db.Text, default='')
    confirmation_subject = db.Column(db.String(500), default='Bestätigung Ihrer Einsendung')
    confirmation_body = db.Column(db.Text, default='')

    @property
    def password(self):
        return _decrypt_secret(self.smtp_password)

    @password.setter
    def password(self, value):
        self.smtp_password = _encrypt_secret(value)


class Submission(db.Model):
    __tablename__ = 'submissions'
    id = db.Column(db.Integer, primary_key=True)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(50), default='')
    data_json = db.Column(db.Text, default='{}')

    @property
    def data(self):
        return json.loads(self.data_json or '{}')

    @data.setter
    def data(self, value):
        self.data_json = json.dumps(value, ensure_ascii=False)


class MailLog(db.Model):
    __tablename__ = 'mail_log'
    id = db.Column(db.Integer, primary_key=True)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    kind = db.Column(db.String(20), default='')  # notification | confirmation | test
    recipients = db.Column(db.String(500), default='')
    subject = db.Column(db.String(500), default='')
    success = db.Column(db.Boolean, default=True)
    error = db.Column(db.Text, default='')
    eml_path = db.Column(db.String(500), default='')  # relative to MAIL_ARCHIVE_DIR


# ─── Auth ────────────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'admin_id' not in session:
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ─── Public Routes ───────────────────────────────────────────────────────────

@app.route('/')
def index():
    config = _get_or_create_form_config()
    return render_template('form.html', config=config)


@app.route('/submit', methods=['POST'])
def submit():
    config = FormConfig.query.first()
    if not config:
        abort(404)

    # Honeypot field — bots fill this, humans don't
    if request.form.get('_hp_email', ''):
        return redirect(url_for('success'))

    data = {}
    for field in config.fields:
        name = field.get('name', '')
        if not name:
            continue
        ftype = field.get('type', 'text')
        if ftype == 'file':
            continue  # saved below, once the submission has an id
        if ftype == 'checkbox':
            data[name] = 'Ja' if name in request.form else 'Nein'
        elif ftype in ('checkbox_group',):
            data[name] = request.form.getlist(name)
        else:
            data[name] = request.form.get(name, '')

    submission = Submission(ip_address=request.remote_addr or '')
    submission.data = data
    db.session.add(submission)
    db.session.commit()

    file_fields = [f.get('name') for f in config.fields if f.get('type') == 'file' and f.get('name')]
    if file_fields:
        for name in file_fields:
            data[name] = _save_uploads(submission.id, request.files.getlist(name))
        submission.data = data
        db.session.commit()

    mail_cfg = MailConfig.query.first()
    if mail_cfg and mail_cfg.enabled:
        _mail_executor.submit(_send_submission_mails, submission.id)

    return redirect(url_for('success'))


@app.errorhandler(413)
def upload_too_large(_exc):
    mb = app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)
    return f'Die hochgeladenen Dateien sind zu gross (maximal {mb} MB).', 413


@app.route('/success')
def success():
    config = FormConfig.query.first()
    return render_template('success.html', config=config)


# ─── Admin Routes ────────────────────────────────────────────────────────────

@app.route('/admin')
def admin_index():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if 'admin_id' in session:
        return redirect(url_for('admin_dashboard'))
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = AdminUser.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session.permanent = True
            session['admin_id'] = user.id
            session['admin_username'] = user.username
            return redirect(url_for('admin_dashboard'))
        error = 'Ungültige Anmeldedaten.'
    return render_template('admin/login.html', error=error)


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('admin_login'))


@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    total = Submission.query.count()
    recent = Submission.query.order_by(Submission.submitted_at.desc()).limit(5).all()
    config = FormConfig.query.first()
    mail_failures = MailLog.query.filter(
        MailLog.success.is_(False),
        MailLog.sent_at >= datetime.utcnow() - timedelta(days=7)).count()
    return render_template('admin/dashboard.html', total=total, recent=recent, config=config,
                           mail_failures=mail_failures)


@app.route('/admin/form-builder', methods=['GET', 'POST'])
@login_required
def admin_form_builder():
    config = _get_or_create_form_config()
    if request.method == 'POST':
        config.form_name = request.form.get('form_name', '').strip() or 'Formular'
        config.form_description = request.form.get('form_description', '').strip()
        config.success_message = request.form.get('success_message', '').strip()
        config.submit_button_text = request.form.get('submit_button_text', 'Absenden').strip()
        raw = request.form.get('fields_json', '[]')
        try:
            config.fields = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            flash('Fehler beim Speichern der Felder.', 'error')
            return redirect(url_for('admin_form_builder'))
        db.session.commit()
        flash('Formular erfolgreich gespeichert!', 'success')
        return redirect(url_for('admin_form_builder'))
    return render_template('admin/form_builder.html', config=config)


@app.route('/admin/submissions')
@login_required
def admin_submissions():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    query = Submission.query.order_by(Submission.submitted_at.desc())
    if search:
        query = query.filter(Submission.data_json.ilike(f'%{search}%'))
    submissions = query.paginate(page=page, per_page=25, error_out=False)
    config = FormConfig.query.first()
    return render_template('admin/submissions.html',
                           submissions=submissions, config=config, search=search)


@app.route('/admin/submissions/<int:sid>/delete', methods=['POST'])
@login_required
def admin_delete_submission(sid):
    sub = Submission.query.get_or_404(sid)
    db.session.delete(sub)
    db.session.commit()
    shutil.rmtree(_submission_upload_dir(sid), ignore_errors=True)
    flash('Einsendung gelöscht.', 'success')
    return redirect(url_for('admin_submissions'))


@app.route('/admin/submissions/delete-all', methods=['POST'])
@login_required
def admin_delete_all_submissions():
    Submission.query.delete()
    db.session.commit()
    shutil.rmtree(UPLOAD_DIR, ignore_errors=True)
    flash('Alle Einsendungen gelöscht.', 'success')
    return redirect(url_for('admin_submissions'))


@app.route('/admin/export')
@login_required
def admin_export():
    fmt = request.args.get('format', 'csv')
    config = FormConfig.query.first()
    submissions = Submission.query.order_by(Submission.submitted_at.asc()).all()

    if fmt == 'json':
        data = []
        for s in submissions:
            row = {'id': s.id,
                   'submitted_at': s.submitted_at.strftime('%Y-%m-%d %H:%M:%S'),
                   'ip_address': s.ip_address}
            row.update(s.data)
            data.append(row)
        filename = f'einsendungen_{datetime.now().strftime("%Y%m%d")}.json'
        return Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )

    # CSV
    output = io.StringIO()
    output.write('﻿')  # BOM for Excel UTF-8

    field_names = ['ID', 'Datum', 'IP-Adresse']
    field_map = {}
    if config:
        for f in config.fields:
            if f.get('name'):
                field_map[f['name']] = f.get('label', f['name'])
                field_names.append(f.get('label', f['name']))

    writer = csv.writer(output, delimiter=';', quoting=csv.QUOTE_ALL)
    writer.writerow(field_names)

    for s in submissions:
        row = [s.id, s.submitted_at.strftime('%d.%m.%Y %H:%M'), s.ip_address]
        for fname, flabel in field_map.items():
            val = s.data.get(fname, '')
            row.append(', '.join(val) if isinstance(val, list) else val)
        writer.writerow(row)

    filename = f'einsendungen_{datetime.now().strftime("%Y%m%d")}.csv'
    return Response(
        output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@app.route('/admin/mail-settings', methods=['GET', 'POST'])
@login_required
def admin_mail_settings():
    cfg = MailConfig.query.first()
    if not cfg:
        cfg = MailConfig()
        db.session.add(cfg)
        db.session.commit()

    if request.method == 'POST':
        cfg.enabled = 'enabled' in request.form
        cfg.smtp_host = request.form.get('smtp_host', '').strip()
        cfg.smtp_port = int(request.form.get('smtp_port') or 587)
        cfg.smtp_user = request.form.get('smtp_user', '').strip()
        new_pw = request.form.get('smtp_password', '')
        if new_pw:
            cfg.password = new_pw
        cfg.use_tls = 'use_tls' in request.form
        cfg.use_ssl = 'use_ssl' in request.form
        cfg.from_email = request.form.get('from_email', '').strip()
        cfg.from_name = request.form.get('from_name', '').strip()
        cfg.notification_email = request.form.get('notification_email', '').strip()
        cfg.send_confirmation = 'send_confirmation' in request.form
        cfg.confirmation_email_field = request.form.get('confirmation_email_field', '').strip()
        cfg.notification_subject = request.form.get('notification_subject', '').strip()
        cfg.notification_body = request.form.get('notification_body', '').strip()
        cfg.confirmation_subject = request.form.get('confirmation_subject', '').strip()
        cfg.confirmation_body = request.form.get('confirmation_body', '').strip()
        db.session.commit()
        flash('E-Mail-Einstellungen gespeichert!', 'success')
        return redirect(url_for('admin_mail_settings'))

    form_config = FormConfig.query.first()
    mail_logs = MailLog.query.order_by(MailLog.sent_at.desc()).limit(20).all()
    return render_template('admin/mail_settings.html', cfg=cfg, form_config=form_config,
                           mail_logs=mail_logs)


@app.route('/admin/mail-test', methods=['POST'])
@login_required
def admin_mail_test():
    cfg = MailConfig.query.first()
    test_email = request.form.get('test_email', '').strip()
    if not cfg or not test_email:
        flash('Bitte zuerst Einstellungen speichern und Test-Adresse eingeben.', 'error')
        return redirect(url_for('admin_mail_settings'))
    try:
        _send_raw_email(cfg, [test_email], 'Test-E-Mail',
                        'Dies ist eine Test-E-Mail von Ihrem Formular-System.\n\nWenn Sie diese E-Mail erhalten, funktioniert der Mail-Versand korrekt.',
                        kind='test')
        flash(f'Test-E-Mail erfolgreich an {test_email} gesendet!', 'success')
    except Exception as exc:
        flash(f'Fehler beim Senden: {exc}', 'error')
    return redirect(url_for('admin_mail_settings'))


@app.route('/admin/uploads/<int:sid>/<path:filename>')
@login_required
def admin_download_upload(sid, filename):
    return send_from_directory(_submission_upload_dir(sid), filename, as_attachment=True)


@app.route('/admin/mail-archive')
@login_required
def admin_mail_archive():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()
    kind = request.args.get('kind', '')
    status = request.args.get('status', '')
    query = MailLog.query.order_by(MailLog.sent_at.desc())
    if search:
        like = f'%{search}%'
        query = query.filter(db.or_(MailLog.recipients.ilike(like), MailLog.subject.ilike(like)))
    if kind:
        query = query.filter(MailLog.kind == kind)
    if status in ('ok', 'error'):
        query = query.filter(MailLog.success.is_(status == 'ok'))
    logs = query.paginate(page=page, per_page=50, error_out=False)
    return render_template('admin/mail_archive.html', logs=logs, search=search,
                           kind=kind, status=status)


@app.route('/admin/mail-log/<int:log_id>/eml')
@login_required
def admin_download_eml(log_id):
    log = MailLog.query.get_or_404(log_id)
    if not log.eml_path:
        abort(404)
    return send_from_directory(MAIL_ARCHIVE_DIR, log.eml_path, as_attachment=True,
                               mimetype='message/rfc822')


@app.route('/admin/change-password', methods=['POST'])
@login_required
def admin_change_password():
    user = AdminUser.query.get(session['admin_id'])
    current = request.form.get('current_password', '')
    new_pw = request.form.get('new_password', '')
    confirm = request.form.get('confirm_password', '')
    if not user.check_password(current):
        flash('Aktuelles Passwort ist falsch.', 'error')
    elif new_pw != confirm:
        flash('Neue Passwörter stimmen nicht überein.', 'error')
    elif len(new_pw) < 6:
        flash('Passwort muss mindestens 6 Zeichen lang sein.', 'error')
    else:
        user.set_password(new_pw)
        db.session.commit()
        flash('Passwort erfolgreich geändert!', 'success')
    return redirect(url_for('admin_dashboard'))


# ─── Email Helpers ───────────────────────────────────────────────────────────

def _get_smtp(cfg):
    # Verified context: checks the server certificate and hostname
    context = ssl.create_default_context()
    if cfg.use_ssl:
        conn = smtplib.SMTP_SSL(cfg.smtp_host, cfg.smtp_port, timeout=15, context=context)
    else:
        conn = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port, timeout=15)
        if cfg.use_tls:
            conn.starttls(context=context)
    if cfg.smtp_user:
        conn.login(cfg.smtp_user, cfg.password)
    return conn


def _send_raw_email(cfg, recipients, subject, body_text, body_html=None, kind='',
                    attachments=None):
    msg = _build_message(cfg, recipients, subject, body_text, body_html, attachments)
    eml_path = _archive_message(msg, kind)
    try:
        with _get_smtp(cfg) as conn:
            conn.sendmail(cfg.from_email, recipients, msg.as_string())
    except Exception as exc:
        _log_mail(kind, recipients, subject, error=exc, eml_path=eml_path)
        raise
    _log_mail(kind, recipients, subject, eml_path=eml_path)


def _archive_message(msg, kind):
    """Store the complete mail (incl. attachments) as .eml; returns the relative path."""
    try:
        now = datetime.utcnow()
        rel = os.path.join(now.strftime('%Y'), now.strftime('%m'),
                           f'{now.strftime("%Y%m%d-%H%M%S")}_{kind or "mail"}_{secrets.token_hex(4)}.eml')
        full = os.path.join(MAIL_ARCHIVE_DIR, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, 'wb') as f:
            f.write(msg.as_bytes())
        return rel
    except Exception as exc:
        app.logger.error('Mail archive write failed: %s', exc)
        return ''


def _log_mail(kind, recipients, subject, error=None, eml_path=''):
    try:
        db.session.add(MailLog(kind=kind, recipients=', '.join(recipients)[:500],
                               subject=subject[:500], success=error is None,
                               error=str(error or ''), eml_path=eml_path))
        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        app.logger.error('Mail log write failed: %s', exc)


def _build_message(cfg, recipients, subject, body_text, body_html=None, attachments=None):
    body = MIMEMultipart('alternative')
    body.attach(MIMEText(body_text, 'plain', 'utf-8'))
    if body_html:
        body.attach(MIMEText(body_html, 'html', 'utf-8'))
    if attachments:
        msg = MIMEMultipart('mixed')
        msg.attach(body)
        for path in attachments:
            ctype = mimetypes.guess_type(path)[0] or 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            part = MIMEBase(maintype, subtype)
            with open(path, 'rb') as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', 'attachment',
                            filename=os.path.basename(path))
            msg.attach(part)
    else:
        msg = body
    msg['From'] = f"{cfg.from_name} <{cfg.from_email}>" if cfg.from_name else cfg.from_email
    msg['To'] = ', '.join(recipients)
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    return msg


def _submission_upload_dir(submission_id):
    return os.path.join(UPLOAD_DIR, str(submission_id))


def _save_uploads(submission_id, files):
    saved = []
    for file in files:
        if not file or not file.filename:
            continue
        name = secure_filename(file.filename)
        ext = name.rsplit('.', 1)[-1].lower() if '.' in name else ''
        if ext not in ALLOWED_UPLOAD_EXTENSIONS:
            app.logger.warning('Upload rejected (type): %s', file.filename)
            continue
        target_dir = _submission_upload_dir(submission_id)
        os.makedirs(target_dir, exist_ok=True)
        base, n = name, 1
        while os.path.exists(os.path.join(target_dir, name)):
            stem, dot, e = base.rpartition('.')
            name = f'{stem}_{n}{dot}{e}'
            n += 1
        file.save(os.path.join(target_dir, name))
        saved.append(name)
    return saved


def _submission_attachments(form_config, submission):
    paths = []
    for field in form_config.fields:
        if field.get('type') != 'file':
            continue
        for name in submission.data.get(field.get('name', ''), []) or []:
            path = os.path.join(_submission_upload_dir(submission.id), name)
            if os.path.isfile(path):
                paths.append(path)
    return paths


def _format_submission_text(form_config, submission):
    lines = [f'Formular: {form_config.form_name}',
             f'Datum: {submission.submitted_at.strftime("%d.%m.%Y %H:%M")}',
             f'IP-Adresse: {submission.ip_address}', '']
    for field in form_config.fields:
        name = field.get('name', '')
        label = field.get('label', name)
        val = submission.data.get(name, '')
        if isinstance(val, list):
            val = ', '.join(val)
        lines.append(f'{label}: {val}')
    return '\n'.join(lines)


def _render_template_str(template, data):
    result = template
    for k, v in data.items():
        result = result.replace('{' + k + '}', ', '.join(v) if isinstance(v, list) else str(v))
    return result


def _send_submission_mails(submission_id):
    with app.app_context():
        try:
            mail_cfg = MailConfig.query.first()
            config = FormConfig.query.first()
            submission = db.session.get(Submission, submission_id)
            if not (mail_cfg and mail_cfg.enabled and config and submission):
                return
            try:
                _send_notification(mail_cfg, config, submission)
            except Exception as exc:
                app.logger.error('Notification mail failed: %s', exc)
            if mail_cfg.send_confirmation and mail_cfg.confirmation_email_field:
                recipient = submission.data.get(mail_cfg.confirmation_email_field, '')
                if isinstance(recipient, str) and '@' in recipient:
                    try:
                        _send_confirmation(mail_cfg, config, submission, recipient)
                    except Exception as exc:
                        app.logger.error('Confirmation mail failed: %s', exc)
        except Exception:
            app.logger.exception('Background mail job failed')


def _send_notification(mail_cfg, form_config, submission):
    recipients = [e.strip() for e in mail_cfg.notification_email.split(',') if e.strip()]
    if not recipients:
        return
    subject = mail_cfg.notification_subject or 'Neue Formulareinsendung'
    body = (_render_template_str(mail_cfg.notification_body, submission.data)
            if mail_cfg.notification_body
            else _format_submission_text(form_config, submission))
    _send_raw_email(mail_cfg, recipients, subject, body, kind='notification',
                    attachments=_submission_attachments(form_config, submission))


def _send_confirmation(mail_cfg, form_config, submission, recipient):
    subject = mail_cfg.confirmation_subject or 'Bestätigung Ihrer Einsendung'
    body = (_render_template_str(mail_cfg.confirmation_body, submission.data)
            if mail_cfg.confirmation_body
            else f'Vielen Dank für Ihre Einsendung!\n\n{_format_submission_text(form_config, submission)}')
    _send_raw_email(mail_cfg, [recipient], subject, body, kind='confirmation')


# ─── Init Helpers ────────────────────────────────────────────────────────────

def _get_or_create_form_config():
    config = FormConfig.query.first()
    if not config:
        config = FormConfig()
        config.fields = [
            {'id': 'f1', 'name': 'name', 'label': 'Name', 'type': 'text',
             'placeholder': 'Ihr vollständiger Name', 'required': True, 'help_text': '', 'options': []},
            {'id': 'f2', 'name': 'email', 'label': 'E-Mail-Adresse', 'type': 'email',
             'placeholder': 'ihre@email.de', 'required': True, 'help_text': '', 'options': []},
            {'id': 'f3', 'name': 'betreff', 'label': 'Betreff', 'type': 'text',
             'placeholder': 'Worum geht es?', 'required': False, 'help_text': '', 'options': []},
            {'id': 'f4', 'name': 'nachricht', 'label': 'Nachricht', 'type': 'textarea',
             'placeholder': 'Ihre Nachricht...', 'required': True, 'help_text': '', 'options': []},
        ]
        db.session.add(config)
        db.session.commit()
    return config


def init_db():
    db.create_all()
    cols = [c['name'] for c in db.inspect(db.engine).get_columns('mail_log')]
    if 'eml_path' not in cols:
        with db.engine.begin() as conn:
            conn.execute(db.text("ALTER TABLE mail_log ADD COLUMN eml_path VARCHAR(500) DEFAULT ''"))
    if not AdminUser.query.first():
        admin_user = os.environ.get('ADMIN_USERNAME', 'admin')
        admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123')
        user = AdminUser(username=admin_user)
        user.set_password(admin_pass)
        db.session.add(user)
        print(f'[INIT] Admin-Benutzer erstellt: {admin_user} / {admin_pass}')
        print('[INIT] Bitte Passwort nach dem ersten Login ändern!')
    _get_or_create_form_config()
    mail_cfg = MailConfig.query.first()
    if not mail_cfg:
        db.session.add(MailConfig())
    elif mail_cfg.smtp_password and not mail_cfg.smtp_password.startswith(ENC_PREFIX):
        mail_cfg.password = mail_cfg.smtp_password  # encrypt legacy plaintext
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        init_db()
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(debug=debug, host=host, port=port)
