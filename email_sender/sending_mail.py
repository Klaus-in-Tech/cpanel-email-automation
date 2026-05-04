import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import socket
from dotenv import load_dotenv
from email_sender.templates import render_template
from email.utils import formataddr, make_msgid, formatdate
from email.header import Header
from email.mime.base import MIMEBase
from email import encoders
import mimetypes


import csv

load_dotenv()


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in ("1", "true", "yes", "on")


def _normalized_host(value: str | None) -> str:
    host = (value or "").strip()
    if "://" in host:
        host = host.split("://", 1)[1]
    return host.strip("/")

email_user = os.getenv("SMTP_USER")
email_password = os.getenv("SMTP_PASS")
email_host = _normalized_host(os.getenv("SMTP_HOST"))
email_port = int(os.getenv("SMTP_PORT", "587"))
use_ssl = _as_bool(os.getenv("SMTP_SSL"), default=(email_port == 465))
use_starttls = _as_bool(os.getenv("SMTP_STARTTLS"), default=(email_port == 587)) and not use_ssl
email_subject = os.getenv("EMAIL_SUBJECT")

# Single attachment setting (optional)
attachment_path = os.getenv("ATTACHMENT_PATH", "").strip()
if attachment_path:
    if not os.path.exists(attachment_path):
        raise RuntimeError(f"Attachment file not found: {attachment_path}")
    if not os.path.isfile(attachment_path):
        raise RuntimeError(f"Attachment path is not a file: {attachment_path}")


if not email_host:
    raise RuntimeError("SMTP_HOST is missing or empty.")
if not email_user or not email_password:
    raise RuntimeError("SMTP_USER and SMTP_PASS must be set.")
if not email_subject:
    raise RuntimeError("EMAIL_SUBJECT must be set.")

# CSV recipients settings
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
default_recipients = os.path.join(project_root, "templates", "recipients.csv")
recipients_file = os.getenv("RECIPIENTS_FILE", default_recipients)
recipients_column = os.getenv("RECIPIENTS_COLUMN", "email")

# read recipients from CSV
if not os.path.exists(recipients_file):
    raise RuntimeError(f"Recipients file not found: {recipients_file}")

with open(recipients_file, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    headers = reader.fieldnames or []
    if recipients_column not in headers:
        candidates = [h for h in headers if "email" in h.lower() or "to" in h.lower()]
        if candidates:
            recipients_column = candidates[0]
        else:
            raise RuntimeError(f"No recipients column found in {recipients_file}. Expected '{recipients_column}' or a column containing 'email' or 'to'.")
    recipients = []
    for row in reader:
        addr = row.get(recipients_column)
        if addr:
            addr = addr.strip()
            if addr:
                recipients.append(addr)

# deduplicate while preserving order
seen = set()
emails = []
for e in recipients:
    if e not in seen:
        seen.add(e)
        emails.append(e)

if not emails:
    raise RuntimeError(f"No recipient addresses found in column '{recipients_column}' of {recipients_file}.")


def connect_smtp(host: str, port: int, prefer_ssl: bool, prefer_starttls: bool):
    attempts = []

    if prefer_ssl:
        attempts.append(("ssl", port))
    elif prefer_starttls:
        attempts.append(("starttls", port))
    else:
        attempts.append(("plain", port))

    for candidate in (("starttls", 587), ("ssl", 465), ("plain", 25)):
        if candidate not in attempts:
            attempts.append(candidate)

    last_err = None
    for mode, candidate_port in attempts:
        try:
            socket.create_connection((host, candidate_port), timeout=8).close()
            print(f"[SMTP] TCP reachable: {host}:{candidate_port} ({mode})")

            if mode == "ssl":
                server = smtplib.SMTP_SSL(host, candidate_port, timeout=30)
            else:
                server = smtplib.SMTP(host, candidate_port, timeout=30)
                server.ehlo()
                if mode == "starttls":
                    server.starttls()
                    server.ehlo()

            server.login(email_user, email_password)
            print(f"[SMTP] Connected/login successful via {mode} on port {candidate_port}")
            return server
        except Exception as err:
            last_err = err
            print(f"[SMTP] Failed via {mode} on {host}:{candidate_port} -> {type(err).__name__}: {err}")

    raise RuntimeError(f"Could not connect/login to SMTP server {host}.") from last_err

def _attach_file(msg: MIMEMultipart, path: str) -> None:
    ctype, encoding = mimetypes.guess_type(path)
    if ctype is None or encoding is not None:
        ctype = "application/octet-stream"
    maintype, subtype = ctype.split("/", 1)

    with open(path, "rb") as f:
        part = MIMEBase(maintype, subtype)
        part.set_payload(f.read())

    encoders.encode_base64(part)
    part.add_header(
        "Content-Disposition",
        f'attachment; filename="{os.path.basename(path)}"'
    )
    msg.attach(part)

server = None
try:
    server = connect_smtp(email_host, email_port, use_ssl, use_starttls)

    for to_addr in emails:
        msg = MIMEMultipart()
        msg["From"] = formataddr((os.getenv("FROM_NAME", ""), email_user))
        msg["To"] = to_addr
        msg["Subject"] = Header(email_subject, "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{os.getenv('FROM_DOMAIN')}>"

        body = render_template("email.txt")
        msg.attach(MIMEText(body, "plain"))

        # Attach single file to every outgoing email (if configured)
        if attachment_path:
            _attach_file(msg, attachment_path)

        try:
            server.sendmail(email_user, to_addr, msg.as_string())
            print(f"Email sent to {to_addr}")
        except Exception as send_err:
            print(f"Failed to send to {to_addr}: {send_err}")

finally:
    try:
        if server:
            server.quit()
    except Exception:
        pass
