import asyncio
import smtplib
from email import policy
from email.parser import BytesParser

import pytest

from trolley.config import Settings
from trolley.email import EmailService, EmailUnavailableError
from trolley.invitation import invitation


def test_invitation_multipart(monkeypatch):
    service = EmailService(Settings(smtp_host="smtp.example.com"))
    messages = []
    monkeypatch.setattr(service, "_send_sync", messages.append)
    subject, body, html = invitation("test-key<&>", "https://example.com/onboarding.md?a=1&b=2")
    asyncio.run(service.send("user@example.com", subject, body, html=html))
    message = BytesParser(policy=policy.default).parsebytes(messages[0].as_bytes())
    assert message.get_content_type() == "multipart/alternative"
    assert [p.get_content_type() for p in message.iter_parts()] == ["text/plain", "text/html"]
    assert message["Date"] and message["Message-ID"]
    assert "test-key<&>" in message.get_body(preferencelist=("plain",)).get_content()
    rendered = message.get_body(preferencelist=("html",)).get_content()
    assert "test-key&lt;&amp;&gt;" in rendered
    assert "a=1&amp;b=2" in rendered
    assert "Enter this key in your client’s secret settings—not in chat." in rendered
    assert "Enter this key in your client’s secret settings—not in chat." in body
    assert len(body.splitlines()) <= 20
    assert service.available


def test_send_failure_raises(monkeypatch):
    service = EmailService(Settings(smtp_host="smtp.example.com"))

    def fail(message):
        raise smtplib.SMTPException("failure")

    monkeypatch.setattr(service, "_send_sync", fail)
    with pytest.raises(EmailUnavailableError):
        asyncio.run(service.send("user@example.com", "subject", "body", html="<p>body</p>"))
    assert not service.available


def test_plain_email_still_supported(monkeypatch):
    service = EmailService(Settings(smtp_host="smtp.example.com"))
    messages = []
    monkeypatch.setattr(service, "_send_sync", messages.append)
    asyncio.run(service.send("user@example.com", "subject", "body"))
    assert messages[0].get_content_type() == "text/plain"
