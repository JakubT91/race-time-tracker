from app.auth.security import (
    create_session_token,
    decode_session_token,
    generate_magic_token,
    hash_token,
)


def test_session_token_roundtrip():
    token = create_session_token(42)
    assert decode_session_token(token) == 42


def test_decode_rejects_garbage():
    assert decode_session_token("not-a-jwt") is None
    assert decode_session_token("") is None


def test_decode_rejects_wrong_signature():
    import jwt

    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "jiny-klic", algorithm="HS256")
    assert decode_session_token(forged) is None


def test_magic_token_hash_stored_not_raw():
    raw, token_hash = generate_magic_token()
    assert raw != token_hash
    assert hash_token(raw) == token_hash
    assert len(token_hash) == 64  # sha256 hex
