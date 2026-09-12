from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azdo_organization: AnyHttpUrl
    azdo_project: str
    azdo_token: str
    azdo_webhook_secret: str
    azdo_repositories: str = ""
    azdo_tracked_refs: str = "refs/heads/main"
    azdo_release_tag_prefix: str = "refs/tags/"
    azdo_work_item_types: str = "Product Backlog Item,User Story,Bug"
    reconciliation_interval_seconds: int = Field(default=300, ge=30)
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    local_llm_base_url: AnyHttpUrl
    local_llm_api_key: str
    local_llm_model: str
    local_embedding_model: str
    mcp_jwt_jwks_uri: AnyHttpUrl
    mcp_jwt_issuer: str
    mcp_jwt_audience: str
    checkpoint_db: str = "./data/state.db"

    @staticmethod
    def _csv(value: str) -> tuple[str, ...]:
        return tuple(part.strip() for part in value.split(",") if part.strip())

    @property
    def repositories(self) -> tuple[str, ...]:
        return self._csv(self.azdo_repositories)

    @property
    def tracked_refs(self) -> tuple[str, ...]:
        return self._csv(self.azdo_tracked_refs)

    @property
    def work_item_types(self) -> tuple[str, ...]:
        return self._csv(self.azdo_work_item_types)
