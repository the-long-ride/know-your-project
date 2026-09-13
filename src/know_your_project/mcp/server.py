from typing import Any

from mcp.server import MCPServer
from mcp.server.auth.provider import TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from starlette.requests import Request
from starlette.responses import JSONResponse

from know_your_project.ingestion.webhooks import (
    AzureDevOpsWebhookHandler,
    parse_push_event,
    parse_work_item_event,
    verify_webhook_secret,
)
from know_your_project.mcp.auth import JwksJwtVerifier
from know_your_project.mcp.tools import KnowledgeTools


def create_mcp(
    *,
    tools: KnowledgeTools,
    jwks_uri: str,
    issuer: str,
    audience: str,
    resource_server_url: str,
    required_scopes: tuple[str, ...] = (),
    token_verifier: TokenVerifier | None = None,
    webhook_secret: str | None = None,
    webhook_handler: AzureDevOpsWebhookHandler | None = None,
) -> MCPServer[Any]:
    verifier = token_verifier or JwksJwtVerifier(
        jwks_uri=jwks_uri,
        issuer=issuer,
        audience=audience,
    )
    mcp: MCPServer[Any] = MCPServer(
        name="Know Your Project",
        token_verifier=verifier,
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(issuer),
            resource_server_url=AnyHttpUrl(resource_server_url),
            required_scopes=list(required_scopes),
            # The verifier validates the JWT `aud` claim itself. Do not fabricate
            # RFC 8707 resource binding when the authorization server did not issue one.
            validate_token_resource=False,
        ),
    )
    ro = ToolAnnotations(
        read_only_hint=True,
        destructive_hint=False,
        open_world_hint=False,
    )
    mcp.tool(annotations=ro)(tools.search_project_knowledge)
    mcp.tool(annotations=ro)(tools.get_feature)
    mcp.tool(annotations=ro)(tools.get_component)
    mcp.tool(annotations=ro)(tools.get_release_changes)
    mcp.tool(annotations=ro)(tools.compare_releases)
    mcp.tool(annotations=ro)(tools.trace_work_item)
    mcp.tool(annotations=ro)(tools.get_screen_spec)

    @mcp.custom_route("/health", methods=["GET"])  # type: ignore[untyped-decorator]
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "know-your-project"})

    if webhook_secret is not None and webhook_handler is not None:

        @mcp.custom_route(  # type: ignore[untyped-decorator]
            "/hooks/azure-devops", methods=["POST"]
        )
        async def azure_devops_hook(request: Request) -> JSONResponse:
            try:
                verify_webhook_secret(
                    request.headers.get("x-kyp-webhook-secret"), webhook_secret
                )
            except PermissionError:
                return JSONResponse({"accepted": False, "error": "unauthorized"}, status_code=401)

            try:
                payload = await request.json()
                if not isinstance(payload, dict):
                    raise TypeError("payload must be an object")
                event_type = str(payload.get("eventType", "")).casefold()
                if event_type == "git.push":
                    await webhook_handler.handle_push(parse_push_event(payload))
                elif event_type.startswith("workitem."):
                    await webhook_handler.handle_work_item(parse_work_item_event(payload))
                else:
                    return JSONResponse(
                        {"accepted": False, "error": "unsupported Azure DevOps event"},
                        status_code=400,
                    )
            except (KeyError, TypeError, ValueError):
                return JSONResponse(
                    {"accepted": False, "error": "malformed Azure DevOps event"},
                    status_code=400,
                )
            return JSONResponse({"accepted": True}, status_code=202)

    return mcp
