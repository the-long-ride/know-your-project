from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azdo_organization: AnyHttpUrl
    azdo_project: str
    azdo_token: str
    azdo_webhook_secret: str
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
