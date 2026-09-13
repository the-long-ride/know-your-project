from datetime import UTC, datetime, timedelta

import jwt
import respx
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import Response

from know_your_project.mcp.auth import JwksJwtVerifier


def _signing_material() -> tuple[rsa.RSAPrivateKey, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": "key-1", "alg": "RS256", "use": "sig"})
    return private_key, jwk


def _token(private_key: rsa.RSAPrivateKey, **claims: object) -> str:
    payload = {
        "sub": "alice",
        "iss": "https://login.example/",
        "aud": "know-your-project",
        "exp": datetime.now(UTC) + timedelta(minutes=5),
        **claims,
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "key-1"},
    )


async def test_jwks_verifier_validates_and_caches_signing_key() -> None:
    private_key, jwk = _signing_material()
    token = _token(
        private_key,
        azp="claude",
        projects=["payments"],
        scope="knowledge.read profile",
    )

    with respx.mock(assert_all_called=True) as router:
        route = router.get("https://login.example/jwks").mock(
            return_value=Response(200, json={"keys": [jwk]})
        )
        verifier = JwksJwtVerifier(
            jwks_uri="https://login.example/jwks",
            issuer="https://login.example/",
            audience="know-your-project",
        )
        first = await verifier.verify_token(token)
        second = await verifier.verify_token(token)
        await verifier.aclose()

    assert first is not None
    assert second is not None
    assert first.subject == "alice"
    assert first.client_id == "claude"
    assert first.scopes == ["knowledge.read", "profile"]
    assert first.claims is not None
    assert first.claims["projects"] == ["payments"]
    assert first.resource is None
    assert route.call_count == 1


async def test_jwks_verifier_supports_entra_scp_claim() -> None:
    private_key, jwk = _signing_material()
    token = _token(private_key, azp="claude", scp="knowledge.read profile")

    with respx.mock:
        respx.get("https://login.example/jwks").mock(
            return_value=Response(200, json={"keys": [jwk]})
        )
        verifier = JwksJwtVerifier(
            jwks_uri="https://login.example/jwks",
            issuer="https://login.example/",
            audience="know-your-project",
        )
        result = await verifier.verify_token(token)
        await verifier.aclose()

    assert result is not None
    assert result.scopes == ["knowledge.read", "profile"]


async def test_jwks_verifier_rejects_wrong_audience() -> None:
    private_key, jwk = _signing_material()
    token = _token(private_key, aud="different-service")

    with respx.mock:
        respx.get("https://login.example/jwks").mock(
            return_value=Response(200, json={"keys": [jwk]})
        )
        verifier = JwksJwtVerifier(
            jwks_uri="https://login.example/jwks",
            issuer="https://login.example/",
            audience="know-your-project",
        )
        result = await verifier.verify_token(token)
        await verifier.aclose()

    assert result is None
