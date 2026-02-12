Email Automation for cPanel
=================================

Simple Python project to send templated emails through a cPanel-hosted SMTP server.

Quick start
----------

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Copy and edit `.env.example` to `.env` with your SMTP credentials.

3. Run a dry-run to verify template rendering:

```bash
PYTHONPATH=. python -m email_sender.scripts.send_example
```

4. Use the CLI to send an email (use `--dry-run` while testing):

```bash
PYTHONPATH=. python -m email_sender.cli --to recipient@example.com --subject "Test" --template welcome.html --context "name=Alice" --dry-run
```

Notes
-----

- This package uses STARTTLS on port 587 by default. If your host requires implicit SSL, set `SMTP_SSL=true` and `SMTP_PORT=465`.
- Do not commit `.env` to version control. Use a secrets manager for production.
- For higher-volume sending consider switching to an async client or a queued worker.
