import asyncio

from modules.notifications import EmailNotifier, EmailSettings


def test_email_settings_read_recipients_from_environment(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "sender@example.test")
    monkeypatch.setenv("SMTP_TO", "first@example.test, second@example.test")
    monkeypatch.setenv("SMTP_ENABLED", "true")

    settings = EmailSettings.from_env()

    assert settings.enabled is True
    assert settings.recipients == ("first@example.test", "second@example.test")


def test_email_is_disabled_by_default_from_environment(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_FROM", "sender@example.test")
    monkeypatch.setenv("SMTP_TO", "admin@example.test")
    monkeypatch.delenv("SMTP_ENABLED", raising=False)

    assert EmailSettings.from_env().enabled is False


def test_email_report_contains_context_and_traceback():
    settings = EmailSettings(
        host="smtp.example.test",
        port=587,
        username="sender@example.test",
        password="secret",
        sender="sender@example.test",
        recipients=("admin@example.test",),
    )
    notifier = EmailNotifier(settings)

    try:
        raise RuntimeError("database is unavailable")
    except RuntimeError as error:
        message = notifier._build_exception_message("database", error)

    body = message.get_content()
    assert message["Subject"] == "Application error: database"
    assert "database is unavailable" in body
    assert "Context: database" in body


def test_disabled_email_does_not_attempt_smtp(monkeypatch):
    notifier = EmailNotifier(EmailSettings("", 587, "", "", "", ()))
    monkeypatch.setattr(notifier, "_send", lambda message: (_ for _ in ()).throw(AssertionError()))

    asyncio.run(notifier.report_exception("test", RuntimeError("ignored")))