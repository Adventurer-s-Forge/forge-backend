"""Caller identity: Firebase ID-token verification.

The ONLY place a uid enters the application. Tokens are checked against Google's
published JWKS, so this needs no service-account credential -- only the Firebase
project id, which is public.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, Final

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from forge_backend import config

logger = logging.getLogger(__name__)

_JWKS_URL: Final = (
    "https://www.googleapis.com/service_accounts/v1/jwk/securetoken@system.gserviceaccount.com"
)

# Caches fetched keys and re-fetches on an unknown kid, so Google's key rotation
# is handlded without restart.
_jwk_client: Final = PyJWKClient(_JWKS_URL, cache_keys=True)

# auto_error=False so a missing header is our 401 rather than HTTPBearer's 403.
_bearer: Final = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"}
    )


def verify_token(token: str) -> dict[str, Any]:
    """Decoded claims of a valid Firebase ID token; raises on anything else"""
    project = config.FIREBASE_PROJECT_ID
    signing_key = _jwk_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],
        audience=project,
        issuer=f"https://securetoken.google.com/{project}",
        options={"require": ["exp", "iat", "aud", "iss", "sub"]},
    )


def current_uid(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """The caller's Firebase uid, taken only from a verified token"""
    if cred is None:
        raise _unauthorized("missing bearer token")
    try:
        claims = verify_token(cred.credentials)
    except jwt.exceptions.PyJWKClientConnectionError:
        logger.exception("JWKS fetch failed")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "auth temporarily unavailable")
    except jwt.PyJWTError as exc:
        logger.info("token rejected: %s", exc)
        raise _unauthorized("invalid or expired token") from None
    except Exception:
        # JWKS fetch failed -- not the caller's fault, but no authorization
        logger.exception("token verification unavailable")
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "auth temporary unavailable"
        ) from None
    uid = claims.get("sub")
    if not isinstance(uid, str) or not uid:
        raise _unauthorized("token has no subject")
    return uid
