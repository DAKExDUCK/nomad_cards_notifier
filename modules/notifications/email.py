from __future__ import annotations

import asyncio
import os
import smtplib
import socket
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from email.utils import format_datetime


@dataclass(frozen=True)
class EmailSettings:
    host: str
    port: int
    username: str
    password: str
    sender: str
    recipients: tuple[str, ...]
    use_tls: bool = True
    send_enabled: bool = True

    @property
    def enabled(self) -> bool:
        return self.send_enabled and bool(self.host and self.sender and self.recipients)

    @classmethod
    def from_env(cls) -> "EmailSettings":
        recipients = tuple(
            address.strip()
            for address in os.getenv("SMTP_TO", "").split(",")
            if address.strip()
        )
        return cls(
            host=os.getenv("SMTP_HOST", ""),
            port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USERNAME", ""),
            password=os.getenv("SMTP_PASSWORD", ""),
            sender=os.getenv("SMTP_FROM") or os.getenv("SMTP_USERNAME", ""),
            recipients=recipients,
            use_tls=os.getenv("SMTP_USE_TLS", "true").lower() == "true",
            send_enabled=os.getenv("SMTP_ENABLED", "false").lower() == "true",
        )


class EmailNotifier:
    """Reusable SMTP notifier for operational error reports."""

    def __init__(self, settings: EmailSettings) -> None:
        self.settings = settings

    async def report_exception(self, context: str, error: BaseException) -> None:
        if not self.settings.enabled:
            return
        message = self._build_exception_message(context, error)
        await asyncio.to_thread(self._send, message)

    def _build_exception_message(self, context: str, error: BaseException) -> EmailMessage:
        occurred_at = datetime.now(timezone.utc)
        traceback_text = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        message = EmailMessage()
        message["Subject"] = f"Application error: {context}"
        message["From"] = self.settings.sender
        message["To"] = ", ".join(self.settings.recipients)
        message["Date"] = format_datetime(occurred_at)
        message.set_content(
            "Application error report\n"
            f"Context: {context}\n"
            f"Host: {socket.gethostname()}\n"
            f"UTC time: {occurred_at.isoformat()}\n\n"
            f"{traceback_text}"
        )
        return message

    def _send(self, message: EmailMessage) -> None:
        with smtplib.SMTP(self.settings.host, self.settings.port, timeout=30) as client:
            client.ehlo()
            if self.settings.use_tls:
                client.starttls()
                client.ehlo()
            if self.settings.username:
                client.login(self.settings.username, self.settings.password)
            client.send_message(message)