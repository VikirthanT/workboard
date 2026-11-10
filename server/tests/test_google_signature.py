"""`google.verify_signature`: the ID token must be signed by Google. Real RSA keys stand in for Google's; nothing is
sent anywhere. The sign-in flow tests (test_google_auth.py) switch this check off because they use unsigned fake tokens;
here it is on, and every way of faking a token must fail."""
import base64
import hashlib
import hmac
import json
import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth import states
from auth.services import google
from core.config import settings
from core.exceptions import AppError

CLIENT_ID = "test-client.apps.googleusercontent.com"
NONCE = "n" * 24
ISSUER = "https://accounts.google.com"


def _new_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(scope="module")
def googles_key():
    return _new_key()


@pytest.fixture(scope="module")
def another_key():
    return _new_key()


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeGoogleKeys:
    """Stands in for jwt.PyJWKClient: hands back Google's public key, or fails the way the real client does."""

    def __init__(self, public_key=None, error=None):
        self.public_key, self.error = public_key, error

    def get_signing_key_from_jwt(self, token):
        if self.error:
            raise self.error
        return FakeSigningKey(self.public_key)


@pytest.fixture(autouse=True)
def configured(monkeypatch, googles_key):
    monkeypatch.setattr(settings, "google_client_id", CLIENT_ID)
    monkeypatch.setattr(google, "_google_keys", FakeGoogleKeys(googles_key.public_key()))


def claims(**over):
    base = {
        "iss": ISSUER, "aud": CLIENT_ID, "exp": time.time() + 300, "nonce": NONCE,
        "email": "asha@atimotors.com", "email_verified": True,
    }
    base.update(over)
    return {k: v for k, v in base.items() if v is not None}  # None removes a claim


def signed(key, **over):
    return jwt.encode(claims(**over), key, algorithm="RS256", headers={"kid": "google-key-1"})


def refused(token):
    with pytest.raises(AppError) as err:
        google.verify_signature(token)
    assert (err.value.code, err.value.status_code) == (states.ERR_PROFILE, 400)


def test_a_token_signed_by_google_is_accepted_and_gives_the_email(googles_key):
    token = signed(googles_key)

    google.verify_signature(token)
    assert google.verified_email(token, NONCE) == "asha@atimotors.com"


def test_a_token_signed_with_anyone_elses_key_is_refused(another_key):
    refused(signed(another_key))


def test_a_token_whose_contents_were_changed_after_signing_is_refused(googles_key):
    header, payload, signature = signed(googles_key).split(".")
    forged = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    forged["email"] = "admin@atimotors.com"
    new_payload = base64.urlsafe_b64encode(json.dumps(forged).encode()).rstrip(b"=").decode()

    refused(f"{header}.{new_payload}.{signature}")


def test_an_unsigned_token_is_refused():
    refused(jwt.encode(claims(), None, algorithm="none"))
    refused("header.payload.signature")  # what the flow tests use as a fake token


def test_a_token_signed_with_a_shared_secret_using_googles_public_key_is_refused(googles_key):
    """The classic algorithm-confusion attack: sign with HS256, using the public key as the secret."""
    public_pem = googles_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    signing_input = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "google-key-1"}).encode()) + "." + b64(
        json.dumps(claims()).encode()
    )
    mac = hmac.new(public_pem, signing_input.encode(), hashlib.sha256).digest()

    refused(f"{signing_input}.{b64(mac)}")


@pytest.mark.parametrize("over", [
    dict(exp=time.time() - 300),  # expired, beyond the clock-difference allowance
    dict(exp=None),  # no expiry at all
    dict(aud="someone-elses-client"),
    dict(aud=None),
    dict(iss="https://evil.example.com"),
    dict(iss=None),
])
def test_a_genuinely_signed_token_for_the_wrong_audience_issuer_or_time_is_refused(googles_key, over):
    refused(signed(googles_key, **over))


def test_the_flow_fails_closed_when_googles_keys_cannot_be_fetched(monkeypatch, googles_key):
    token = signed(googles_key)
    for problem in (jwt.PyJWKClientConnectionError("Google is unreachable"), jwt.PyJWKClientError("no such key")):
        monkeypatch.setattr(google, "_google_keys", FakeGoogleKeys(error=problem))
        refused(token)
        with pytest.raises(AppError):
            google.verified_email(token, NONCE)


def test_a_signed_token_for_another_sign_in_is_still_refused_by_the_nonce_check(googles_key):
    token = signed(googles_key, nonce="a-nonce-from-another-sign-in")

    google.verify_signature(token)  # the signature is fine...
    with pytest.raises(AppError):  # ...but it is not the token for this sign-in
        google.verified_email(token, NONCE)
