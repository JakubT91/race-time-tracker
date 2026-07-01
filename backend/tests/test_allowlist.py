from app.config import Settings


def test_empty_allowlist_allows_everyone():
    s = Settings(allowed_emails="")
    assert s.is_email_allowed("anyone@example.com")
    assert s.allowlist == set()


def test_nonempty_allowlist_restricts():
    s = Settings(allowed_emails="a@x.com, B@X.com")
    assert s.is_email_allowed("a@x.com")
    assert s.is_email_allowed("b@x.com")  # case-insensitive
    assert s.is_email_allowed("  A@x.com ")  # trim + case
    assert not s.is_email_allowed("intruder@x.com")


def test_allowlist_parsing_ignores_blanks():
    s = Settings(allowed_emails="a@x.com,, ,b@x.com,")
    assert s.allowlist == {"a@x.com", "b@x.com"}
