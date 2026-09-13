from typing import Any

import httpx
import jwt
from mcp.server.auth.provider import AccessToken


def _claim_scopes(claims: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for name in ("scope", "scp"):
        raw = claims.get(name)
        if isinstance(raw, str):
            values.extend(raw.split())
        elif isinstance(raw, list):
            values.extend(str(item) for item in raw if item)
    roles = claims.get("roles")
    if isinstance(roles, list):
        values.extend(str(item) for item in roles if item)
    return list(dict.fromkeys(values))


class JwksJwtVerifier:
    """Verify RS256 bearer tokens against a cached JWKS document."""

    def __init__(
        self,
        *,
        jwks_uri: str,
        issuer: str,
        audience: str,
    ) -> None:
        self._jwks_uri = jwks_uri
        self._issuer = issuer
        self._audience = audience
        self._keys: dict[str, Any] = {}
        self._client: httpx.AsyncClient | None = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10)
        return self._client

    async def _refresh_keys(self) -> None:
        response = await self._http().get(self._jwks_uri)
        response.raise_for_status()
        payload = response.json()
        keys: dict[str, Any] = {}
        for item in payload.get("keys", []):
            kid = item.get("kid")
            alg = item.get("alg", "RS256")
            if kid and alg == "RS256":
                keys[str(kid)] = jwt.PyJWK.from_dict(item).key
        self._keys = keys

    async def _decode(self, token: str, kid: str) -> dict[str, Any]:
        key = self._keys.get(kid)
        if key is None:
            await self._refresh_keys()
            key = self._keys.get(kid)
        if key is None:
            raise jwt.InvalidKeyError("unknown signing key")
        return dict(
            jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256" or not header.get("kid"):
                return None
            kid = str(header["kid"])
            try:
                claims = await self._decode(token, kid)
            except jwt.InvalidSignatureError:
                self._keys.pop(kid, None)
                claims = await self._decode(token, kid)

            client_id = str(
                claims.get("azp")
                or claims.get("client_id")
                or claims.get("appid")
                or claims["sub"]
            )
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=_claim_scopes(claims),
                expires_at=int(claims["exp"]),
                subject=str(claims["sub"]),
                claims=claims,
            )
        except (jwt.PyJWTError, httpx.HTTPError, KeyError, TypeError, ValueError):
            return None

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
