from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from mcp.types import ToolAnnotations

from know_your_project.mcp.tools import KnowledgeTools


def create_mcp(*, tools: KnowledgeTools, jwks_uri: str, issuer: str, audience: str) -> FastMCP:
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
    return mcp
