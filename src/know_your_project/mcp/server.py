from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

from know_your_project.ingestion.webhooks import parse_push_event, verify_webhook_secret
from know_your_project.mcp.tools import KnowledgeTools


def create_mcp(
    *,
    tools: KnowledgeTools,
    jwks_uri: str,
    issuer: str,
    audience: str,
    webhook_secret: str | None = None,
    webhook_handler=None,
) -> FastMCP:
    auth = JWTVerifier(jwks_uri=jwks_uri, issuer=issuer, audience=audience)
    mcp = FastMCP(name="Know Your Project", auth=auth)
    ro = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    mcp.tool(annotations=ro)(tools.search_project_knowledge)
    mcp.tool(annotations=ro)(tools.get_feature)
    mcp.tool(annotations=ro)(tools.get_component)
    mcp.tool(annotations=ro)(tools.get_release_changes)
    mcp.tool(annotations=ro)(tools.compare_releases)
    mcp.tool(annotations=ro)(tools.trace_work_item)
    mcp.tool(annotations=ro)(tools.get_screen_spec)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_: Request) -> JSONResponse:
        return JSONResponse({"status": "healthy", "service": "know-your-project"})

    if webhook_secret is not None and webhook_handler is not None:
        @mcp.custom_route("/hooks/azure-devops", methods=["POST"])
        async def azure_devops_hook(request: Request) -> JSONResponse:
            verify_webhook_secret(
                request.headers.get("x-kyp-webhook-secret"), webhook_secret
            )
            event = parse_push_event(await request.json())
            await webhook_handler.handle_push(event)
            return JSONResponse({"accepted": True}, status_code=202)

    return mcp
