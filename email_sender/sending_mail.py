import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from email_sender.templates import render_template
from email.utils import formataddr, make_msgid, formatdate
from email.header import Header
import csv

load_dotenv()

email_user = os.getenv("SMTP_USER")
email_password = os.getenv("SMTP_PASS")
email_host = os.getenv("SMTP_HOST")
email_port = int(os.getenv("SMTP_PORT", "587"))
# prefer implicit SSL if explicitly set or commonly-used SSL port
use_ssl = (
    os.getenv("SMTP_SSL", "false").lower() in ("1", "true", "yes") or email_port == 465
)
use_starttls = (
    os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes") and not use_ssl
)

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

server = None
try:
    # choose correct connection method
    if use_ssl:
        server = smtplib.SMTP_SSL(email_host, email_port, timeout=10)
    else:
        server = smtplib.SMTP(email_host, email_port, timeout=10)
        if use_starttls:
            server.ehlo()
            server.starttls()
            server.ehlo()

    server.login(email_user, email_password)

    for to_addr in emails:
        msg = MIMEMultipart()
        msg["From"] = formataddr((os.getenv("FROM_NAME", ""), email_user))
        msg["To"] = to_addr
        msg["Subject"] = Header("Test subject", "utf-8")
        msg["Date"] = formatdate(localtime=True)
        msg["Message-ID"] = make_msgid()
        msg["List-Unsubscribe"] = f"<mailto:unsubscribe@{os.getenv('FROM_DOMAIN')}>"

        body = render_template("email.txt")
        msg.attach(MIMEText(body, "plain"))

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
