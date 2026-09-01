import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from trolley.config import Settings, SmtpSecurity


class EmailUnavailableError(RuntimeError):
    pass


class EmailService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.available = False

    async def check(self) -> bool:
        if not self.settings.smtp_host:
            self.available = False
            return False
        try:
            await asyncio.to_thread(self._check_sync)
        except (OSError, smtplib.SMTPException) as error:
            self.available = False
            raise EmailUnavailableError("SMTP connection check failed") from error
        self.available = True
        return True

    async def send(self, recipient: str, subject: str, body: str) -> None:
        if not self.settings.smtp_host:
            raise EmailUnavailableError("Email delivery is not configured")
        message = EmailMessage()
        message["From"] = self.settings.email_from
        message["To"] = recipient
        message["Subject"] = subject
        message.set_content(body)
        try:
            await asyncio.to_thread(self._send_sync, message)
        except (OSError, smtplib.SMTPException) as error:
            self.available = False
            raise EmailUnavailableError("Email delivery failed") from error
        self.available = True

    def _connect(self) -> smtplib.SMTP:
        host = self.settings.smtp_host or ""
        if self.settings.smtp_security == SmtpSecurity.TLS:
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout,
                context=ssl.create_default_context(),
            )
        else:
            client = smtplib.SMTP(host, self.settings.smtp_port, timeout=self.settings.smtp_timeout)
            client.ehlo()
            if self.settings.smtp_security == SmtpSecurity.STARTTLS:
                client.starttls(context=ssl.create_default_context())
                client.ehlo()
        if self.settings.smtp_username:
            password = self.settings.smtp_password
            client.login(
                self.settings.smtp_username,
                password.get_secret_value() if password else "",
            )
        return client

    def _check_sync(self) -> None:
        with self._connect() as client:
            client.noop()

    def _send_sync(self, message: EmailMessage) -> None:
        with self._connect() as client:
            client.send_message(message)
