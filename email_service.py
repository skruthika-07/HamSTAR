"""Outgoing email over SMTP (Gmail with an app password works). Used for password reset codes."""
import smtplib
import ssl
from email.message import EmailMessage

from ..core.config import get_settings
from ..core.errors import ApiError
from ..core.logging import log


def configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.smtp_user and s.smtp_password)


def send(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Send one message. The message body is never logged: it may carry a reset code."""
    s = get_settings()
    if not configured():
        raise ApiError("EMAIL_NOT_CONFIGURED", "Email is not set up on this server yet, so reset codes cannot be sent. Add the SMTP settings to backend/.env.", 503)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, s.smtp_from or s.smtp_user, to
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    try:
        context = ssl.create_default_context()
        if s.smtp_port == 465:
            with smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=20, context=context) as smtp:
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=20) as smtp:
                smtp.starttls(context=context)
                smtp.login(s.smtp_user, s.smtp_password)
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log.error("Email could not be sent: %s", type(e).__name__)
        raise ApiError("EMAIL_FAILED", "The email could not be sent just now. Please try again in a moment.", 502)


def reset_email(name: str, code: str, link: str, minutes: int) -> tuple[str, str, str]:
    """Subject, plain text and HTML for a password reset."""
    subject = "Your HamSTAR secret squeak reset code"
    text = (
        f"Hi {name},\n\nSomeone asked to reset the Secret Squeak for your HamSTAR account.\n\n"
        f"Your code is: {code}\n\nIt works once and expires in {minutes} minutes.\n"
        f"Or open this link: {link}\n\nIf this was not you, ignore this email: your Secret Squeak stays as it is.\n\nThink · Explain · Grow\nHamSTAR"
    )
    html = f"""<div style="font-family:Segoe UI,Arial,sans-serif;max-width:480px;margin:auto;padding:24px;background:#fdf6e3;border-radius:16px;color:#46291b">
<h2 style="margin:0 0 8px">Forgot your secret squeak?</h2>
<p>Hi {name}, no worries. Here is your reset code:</p>
<p style="font-size:32px;font-weight:800;letter-spacing:8px;background:#fbe3a1;border-radius:12px;padding:12px;text-align:center">{code}</p>
<p>It works once and expires in {minutes} minutes.</p>
<p><a href="{link}" style="display:inline-block;background:#f0b93a;color:#46291b;font-weight:700;padding:10px 18px;border-radius:999px;text-decoration:none">Choose a new Secret Squeak</a></p>
<p style="color:#8a7560;font-size:13px">If this was not you, ignore this email: your Secret Squeak stays as it is.</p>
<p style="color:#8a7560;font-size:13px">Think · Explain · Grow — HamSTAR</p></div>"""
    return subject, text, html
