# CLAUDE.md

Guidance for Claude Code (and other AI assistants) working in this repository.

## What this is

A small, self-contained Flask web app for building a custom contact/lead-capture
form, collecting submissions, and emailing notifications. German is the
application's UI language (labels, flash messages, admin copy) — keep new
user-facing strings in German unless told otherwise.

There is no separate frontend build: server-rendered Jinja templates,
Bootstrap 5 via CDN, and small inline `<script>` blocks for interactivity
(e.g. drag-and-drop field ordering via SortableJS, also via CDN). No npm,
no bundler, no transpilation step.

## Repository layout

```
app.py              Entire backend: Flask app, SQLAlchemy models, routes, email helpers
wsgi.py              Production entrypoint (gunicorn target: wsgi:application); calls init_db() on import
start.sh             Dev/prod launcher: loads .env, runs init_db(), then gunicorn (falls back to `python app.py`)
requirements.txt     Flask, Flask-SQLAlchemy, Werkzeug — that's the whole dependency list
.env.example         Documents supported env vars (copy to .env, not committed)
templates/
  base.html            Public-site layout (Bootstrap CDN + custom.css)
  form.html            The public-facing form (renders fields from FormConfig.fields)
  success.html         Post-submission thank-you page
  admin/
    base.html          Admin layout with sidebar + flashed messages
    _sidebar.html       Nav partial, active-link highlighting via request.endpoint
    login.html          Admin login
    dashboard.html       Submission count + recent list
    form_builder.html    Drag/drop field editor (largest template; vanilla JS + SortableJS)
    mail_settings.html   SMTP config + test-send UI
    submissions.html     Paginated submission list with search/export/delete
static/css/custom.css  All custom CSS (everything else is Bootstrap utility classes)
instance/              Created at runtime: SQLite DB + generated SECRET_KEY (gitignored)
```

There are no automated tests, no CI config, and no linter config in this repo.

## Architecture (app.py, single file)

**Models** (SQLAlchemy, table names in parens):
- `AdminUser` (`admin_users`) — username + werkzeug password hash.
- `FormConfig` (`form_config`) — form copy (name, description, success message,
  submit button text) plus `fields_json`, exposed as a Python list via the
  `.fields` property/setter. Each field dict has keys: `id, name, label, type,
  placeholder, required, help_text, options`. `type` is one of: text, textarea,
  number, email, tel, date, time, url, select, radio, checkbox, checkbox_group.
  Treated as a singleton — code does `FormConfig.query.first()`.
- `MailConfig` (`mail_config`) — SMTP settings + notification/confirmation
  email templates. Also a singleton.
- `Submission` (`submissions`) — timestamp, IP, and `data_json` (raw form
  values keyed by field name), exposed via the `.data` property/setter.

**Routes**:
- Public: `/` (render form), `/submit` (POST, honeypot-checked, persists
  `Submission`, fires notification/confirmation email), `/success`.
- Admin (all gated by `@login_required`, session-cookie based — see
  `login_required` decorator near the top of the auth section):
  `/admin/dashboard`, `/admin/form-builder` (GET+POST), `/admin/submissions`
  (paginated, `?search=`, `?page=`), `/admin/submissions/<id>/delete`,
  `/admin/submissions/delete-all`, `/admin/export` (`?format=csv|json`),
  `/admin/mail-settings` (GET+POST), `/admin/mail-test`,
  `/admin/change-password`.
- `/admin/login`, `/admin/logout` are unauthenticated entry/exit points.

**Email**: plain `smtplib` (no Flask-Mail). `_get_smtp` handles
SSL/STARTTLS/plain based on `MailConfig.use_ssl`/`use_tls`. Notification and
confirmation bodies support `{field_name}` placeholder substitution via
`_render_template_str` (naive string `.replace`, not Jinja) when a custom
template is set, else fall back to `_format_submission_text`.

**Submission data**: form fields are dynamic and stored as JSON
(`fields_json` on `FormConfig`, `data_json` on `Submission`), not as fixed
columns. When adding a feature that touches submitted data, go through the
`.fields` / `.data` properties rather than parsing the `_json` columns
directly.

## Conventions to follow

- **No ORM migrations** — schema changes happen via `db.create_all()` in
  `init_db()`. There's no Alembic/Flask-Migrate. If you change a model's
  columns, existing SQLite databases in `instance/` won't get the new column
  automatically; mention this when making schema changes (a user with an
  existing `instance/formapp.db` will need to delete it or migrate by hand).
- **Singleton config rows** — `FormConfig` and `MailConfig` are queried with
  `.query.first()`, not by id. Don't introduce multi-tenancy assumptions.
- **Honeypot anti-spam** — `/submit` checks `_hp_email` (hidden field in
  `form.html`); keep this when touching the public form/submit flow.
- **CSV export** — UTF-8 BOM + `;` delimiter (Excel/German-locale friendly).
  Don't change the delimiter without checking this is intentional.
- **Secrets**: `SECRET_KEY` is read from `SECRET_KEY` env var, else
  auto-generated and persisted to `instance/.secret_key` on first run.
  `ADMIN_USERNAME`/`ADMIN_PASSWORD` (default `admin`/`admin123`) only seed the
  first admin user on a fresh DB — the seeded password is **not safe for
  production** and is meant to be changed via `/admin/change-password`. Don't
  weaken this default-credential warning or remove the console print in
  `init_db()` that surfaces it.
- **Routes return `redirect(url_for(...))` after POST** (no JSON API
  responses except `/admin/export`), and use Flask `flash()` for user
  feedback. Follow this pattern for new admin actions rather than introducing
  JSON/AJAX endpoints unless there's a specific reason.
- **Templates**: public pages extend `templates/base.html`; all admin pages
  extend `templates/admin/base.html` and rely on `_sidebar.html` for nav
  (active state via `request.endpoint`). Add new admin pages to the sidebar
  when adding new admin routes.
- **JS**: vanilla JS in `extra_scripts` blocks, no framework, no build step.
  Keep new interactive admin UI consistent with `form_builder.html`'s style
  (small top-level functions, manual DOM string templating with the local
  `esc()` HTML-escaping helper — always escape user data interpolated into
  `innerHTML`).
- **CSS**: Bootstrap 5 utility classes first; only add rules to
  `static/css/custom.css` for things Bootstrap can't do directly, and keep
  the file's section-comment-banner style (`/* ── Section ── */`).

## Running locally

```bash
cp .env.example .env        # edit as needed (admin creds, SMTP, SECRET_KEY)
pip install -r requirements.txt
./start.sh                  # inits DB, then runs gunicorn (falls back to `python app.py`)
```

Or directly: `python app.py` (uses Flask's dev server, honors `HOST`/`PORT`/
`FLASK_DEBUG` env vars). The app auto-creates `instance/formapp.db` (SQLite)
and a default admin user + default form fields on first run — check
stdout for the generated admin credentials when `ADMIN_USERNAME`/
`ADMIN_PASSWORD` aren't set.

There is no test suite to run. Verify changes manually: start the app,
exercise the public form at `/` and the admin panel at `/admin`
(default login `admin` / `admin123` unless overridden).
