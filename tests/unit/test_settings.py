import pytest

from know_your_project.settings import Settings
from know_your_project.infrastructure.logging import audit


def test_settings_accept_explicit_self_hosted_configuration() -> None:
    settings = Settings(
        azdo_organization="https://dev.azure.com/acme",
        azdo_project="Project",
        azdo_token="token",
        azdo_webhook_secret="hook",
        neo4j_uri="bolt://neo4j:7687",
        neo4j_user="neo4j",
        neo4j_password="password",
        local_llm_base_url="http://llm:11434/v1",
        local_llm_api_key="local",
        local_llm_model="gpt-oss:20b",
        local_embedding_model="embedding",
        mcp_jwt_jwks_uri="https://login.example/jwks",
        mcp_jwt_issuer="https://login.example/",
        mcp_jwt_audience="know-your-project",
    )
    assert settings.checkpoint_db == "./data/state.db"
    assert str(settings.local_llm_base_url).startswith("http://llm:11434")


def test_audit_rejects_sensitive_payload_fields() -> None:
    with pytest.raises(ValueError, match="sensitive audit fields"):
        audit("sync", content="private code")
