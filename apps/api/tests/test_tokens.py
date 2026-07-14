import datetime as dt
import uuid

import pytest

from app.auth.tokens import (
    TokenError,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    verify_access_token,
)

SECRET = "test-secret"
AUD = "polyglot-api"
ISS = "polyglot-web"


def _token(now=None, secret=SECRET, aud=AUD, iss=ISS):
    return create_access_token(
        user_id=uuid.uuid4(), role="user", session_id=uuid.uuid4(),
        secret=secret, audience=aud, issuer=iss, now=now,
    )


def test_valid_token_roundtrip():
    uid = uuid.uuid4(); sid = uuid.uuid4()
    tok = create_access_token(user_id=uid, role="admin", session_id=sid,
                              secret=SECRET, audience=AUD, issuer=ISS)
    claims = verify_access_token(tok, secret=SECRET, audience=AUD, issuer=ISS)
    assert claims.sub == uid
    assert claims.sid == sid
    assert claims.role == "admin"


def test_expired_token_rejected():
    past = dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(hours=1)
    tok = _token(now=past)
    with pytest.raises(TokenError):
        verify_access_token(tok, secret=SECRET, audience=AUD, issuer=ISS)


def test_wrong_secret_rejected():
    tok = _token()
    with pytest.raises(TokenError):
        verify_access_token(tok, secret="other-secret", audience=AUD, issuer=ISS)


def test_wrong_audience_rejected():
    tok = _token()
    with pytest.raises(TokenError):
        verify_access_token(tok, secret=SECRET, audience="someone-else", issuer=ISS)


def test_refresh_token_hash_is_deterministic_and_hides_value():
    raw = generate_refresh_token()
    assert hash_refresh_token(raw) == hash_refresh_token(raw)
    assert raw not in hash_refresh_token(raw)
    assert len(generate_refresh_token()) > 20
