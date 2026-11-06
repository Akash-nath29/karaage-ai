"""Outgoing email (A19, D34): plain text over SMTP. Mailpit catches it in development."""

import logging
import smtplib
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger(__name__)


def send(to: str, subject: str, body: str) -> bool:
    """Best effort: returns False (and logs) if the server can't be reached. Callers offer a resend."""
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = settings.smtp_from, to, subject
    message.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password)
            smtp.send_message(message)
        return True
    except (OSError, smtplib.SMTPException):
        log.exception("could not send %r to %s", subject, to)
        return False
