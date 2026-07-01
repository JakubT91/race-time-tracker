"""Odesílání e-mailů (přihlašovací odkaz, pozvánky).

Priorita transportu: SMTP (např. Gmail) -> Resend -> jen log (vývoj).
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


async def _send(to: str, subject: str, html: str, text: str) -> None:
    # SMTP (Gmail) funguje lokálně, ale hostingy jako Render zdarma blokují odchozí
    # SMTP. Když selže a je k dispozici Resend, spadneme na něj (jede přes HTTPS).
    if settings.smtp_host and settings.smtp_user and settings.smtp_password:
        try:
            await asyncio.to_thread(_send_smtp, to, subject, html, text)
            return
        except Exception as exc:  # noqa: BLE001
            if not settings.resend_api_key:
                raise
            log.warning("SMTP selhalo (%s: %s) — padám na Resend", type(exc).__name__, exc)

    if settings.resend_api_key:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json={"from": settings.mail_from, "to": [to], "subject": subject, "html": html},
            )
            resp.raise_for_status()
        return

    log.warning("Žádná e-mailová služba nenastavena — [%s] pro %s: %s", subject, to, text)


def _send_smtp(to: str, subject: str, html: str, text: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = subject
    # Gmail vyžaduje From = ověřený odesílatel (přihlášený účet)
    msg["From"] = f"Race tracker <{settings.smtp_user}>"
    msg["To"] = to
    msg.set_content(text)
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


async def send_magic_link(email: str, link: str) -> None:
    html = (
        f"<p>Ahoj,</p><p>klikni pro přihlášení do Race tracker:</p>"
        f'<p><a href="{link}">Přihlásit se</a></p>'
        f"<p>Odkaz platí omezenou dobu. Pokud jsi o přihlášení nežádal, ignoruj tento e-mail.</p>"
    )
    await _send(email, "Přihlášení do Race tracker", html, f"Přihlas se do Race tracker: {link}")


async def send_invite(email: str, link: str, race_name: str, runner_label: str) -> None:
    subject = f"Pozvánka do Race tracker — {race_name}"
    html = (
        f"<p>Ahoj,</p>"
        f"<p>byl jsi pozván ke sledování {runner_label} na závodě <strong>{race_name}</strong> "
        f"v aplikaci Race tracker.</p>"
        f'<p><a href="{link}">Otevřít závod a přihlásit se</a></p>'
        f"<p>Stačí kliknout — přihlášení je bez hesla.</p>"
    )
    text = f"Byl jsi pozván ke sledování {runner_label} na závodě {race_name}. Přihlas se: {link}"
    await _send(email, subject, html, text)
