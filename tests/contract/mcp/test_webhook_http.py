from unittest.mock import AsyncMock, Mock

from starlette.testclient import TestClient

from know_your_project.mcp.server import create_mcp
from know_your_project.mcp.tools import KnowledgeTools


def _app():
    server = create_mcp(
        tools=KnowledgeTools(revisions=Mock(), authorization=Mock()),
        jwks_uri="https://login.example/jwks",
        issuer="https://login.example/",
        audience="know-your-project",
        resource_server_url="https://knowledge.example/mcp",
        webhook_secret="expected",
        webhook_handler=AsyncMock(),
    )
    return server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        host="0.0.0.0",
    )


def test_invalid_webhook_secret_returns_401() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/hooks/azure-devops",
            headers={"x-kyp-webhook-secret": "wrong"},
            json={"eventType": "git.push"},
        )
    assert response.status_code == 401


def test_malformed_webhook_returns_400() -> None:
    with TestClient(_app(), raise_server_exceptions=False) as client:
        response = client.post(
            "/hooks/azure-devops",
            headers={"x-kyp-webhook-secret": "expected"},
            json={"eventType": "git.push", "resource": {}},
        )
    assert response.status_code == 400
