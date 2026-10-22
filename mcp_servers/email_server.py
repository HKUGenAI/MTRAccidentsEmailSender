"""MCP server: send_email tool (to, subject, body) via SMTP.

Credentials come from environment variables only — never from tool arguments.
Set EMAIL_DRY_RUN=true (default) to return the proposed email without sending.
"""

from __future__ import annotations

import json
import logging
import os
import smtplib
import ssl
from email.message import EmailMessage

from mcp.server.mcpserver import MCPServer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("email_server")

mcp = MCPServer("mtr-email")


def _truthy(value: str | None, default: bool = True) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _smtp_send(to: str, subject: str, body: str) -> dict:
    host = (os.getenv("SMTP_HOST") or "").strip()
    port = int(os.getenv("SMTP_PORT") or "587")
    user = (os.getenv("SMTP_USER") or "").strip()
    password = (os.getenv("SMTP_PASSWORD") or "").strip()
    mail_from = (os.getenv("SMTP_FROM") or user).strip()

    missing = [
        name
        for name, val in [
            ("SMTP_HOST", host),
            ("SMTP_USER", user),
            ("SMTP_PASSWORD", password),
            ("SMTP_FROM", mail_from),
        ]
        if not val
    ]
    if missing:
        return {
            "ok": False,
            "sent": False,
            "dry_run": False,
            "error": f"Missing SMTP env vars: {', '.join(missing)}",
        }

    msg = EmailMessage()
    msg["From"] = mail_from
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(user, password)
        server.send_message(msg)

    return {
        "ok": True,
        "sent": True,
        "dry_run": False,
        "to": to,
        "subject": subject,
        "from": mail_from,
        "status": "Email accepted by SMTP server.",
    }


@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email via SMTP (or dry-run if EMAIL_DRY_RUN is enabled).

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body (include summary + source links).
    """
    dry_run = _truthy(os.getenv("EMAIL_DRY_RUN"), default=True)
    draft = {"to": to, "subject": subject, "body": body}

    if dry_run:
        logger.info("DRY RUN email to=%s subject=%s", to, subject)
        result = {
            "ok": True,
            "sent": False,
            "dry_run": True,
            **draft,
            "status": (
                "DRY RUN - email was NOT sent. "
                "Set EMAIL_DRY_RUN=false and configure SMTP_* to send for real."
            ),
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    try:
        result = _smtp_send(to=to, subject=subject, body=body)
    except Exception as exc:  # noqa: BLE001
        logger.exception("send_email failed")
        result = {
            "ok": False,
            "sent": False,
            "dry_run": False,
            **draft,
            "error": str(exc),
            "status": "SMTP send failed.",
        }
    else:
        logger.info("Sent email to=%s subject=%s", to, subject)

    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    mcp.run(transport="stdio")
