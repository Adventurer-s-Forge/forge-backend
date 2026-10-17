"""Token handling in auth.current_uid

`api_client` overrides this dependecy, so these tests exercise it directly. Real Firebase
tokens cannot be minted here, so the cases covered are the rejection paths plus the claim
extraction.
"""

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from forge_backend import auth


def cred(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def test_missing_credentials_is_401():
    with pytest.raises(HTTPException) as exc:
        auth.current_uid(None)
    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_malformed_token_is_401(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        auth.current_uid(cred("not-a-jwt"))
    assert exc.value.status_code == 401


def test_jwks_outage_is_503_not_401(monkeypatch):
    """A Google outage must not look like a bad token --  a 401 would sign the yser
    out over a transient network failure.
    """

    def boom(token):
        raise jwt.exceptions.PyJWKClientConnectionError("JWKS unreachable")

    monkeypatch.setattr(auth._jwk_client, "get_signing_key_from_jwt", boom)
    with pytest.raises(HTTPException) as exc:
        auth.current_uid(cred("a.b.c"))
    assert exc.value.status_code == 503


def test_verified_claims_yield_the_sub(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: {"sub": "firebaseUid123"})
    assert auth.current_uid(cred("a.b.c")) == "firebaseUid123"


def test_token_without_subject_is_401(monkeypatch):
    monkeypatch.setattr(auth, "verify_token", lambda token: {"aud": "adv-forge"})
    with pytest.raises(HTTPException) as exc:
        auth.current_uid(cred("a.b.c"))
    assert exc.value.status_code == 401


def test_jwks_url_is_the_google_endpoint():
    """A missing slash here fetches a 404 and every token looks invalid."""
    assert auth._JWKS_URL == (
        "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
    )
