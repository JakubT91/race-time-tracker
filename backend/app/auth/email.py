"""Odesílání magic-link e-mailu.

Priorita: SMTP (např. Gmail) -> Resend -> jen log (vývoj).
Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USER=<gmail>,
SMTP_PASSWORD=<app password> (heslo aplikace, ne běžné heslo).
"""

import asyncio
import logging
import smtplib
from email.message import EmailMessage

import httpx

from app.config import settings

log = logging.getLogger(__name__)

RESEND_URL = "https://api.resend.com/emails"


def _build_html(link: str) -> str:
    return (
        f"<p>Ahoj,</p><p>klikni pro přihlášení do Race tracker:</p>"
        f'<p><a href="{link}">Přihlásit se</a></p>'
        f"<p>Odkaz platí omezenou dobu. Pokud jsi o přihlášení nežádal, ignoruj tento e-mail.</p>"
    )


async def send_magic_link(email: str, link: str) -> None:
    subject = "Přihlášení do Race tracker"
    html = _build_html(link)

    if settings.smtp_host and settings.smtp_user and settings.smtp_password:
        await asyncio.to_thread(_send_smtp, email, subject, html, link)
        return

    if settings.resend_api_key:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": settings.mail_from, "to": [email], "subject": subject, "html": html},
            )
            resp.raise_for_status()
        return

    log.warning("Žádná e-mailová služba nenastavena — magic link pro %s: %s", email, link)


def _send_smtp(to: str, subject: str, html: str, link: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    # Gmail vyžaduje From = ověřený odesílatel (přihlášený účet)
    msg["From"] = f"Race tracker <{settings.smtp_user}>"
    msg["To"] = to
    msg.set_content(f"Přihlas se do Race tracker tímto odkazem:\n{link}")
    msg.add_alternative(html, subtype="html")

    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.send_message(msg)
