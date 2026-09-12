from unittest.mock import Mock

from fastmcp import Client

from know_your_project.mcp.server import create_mcp
from know_your_project.mcp.tools import KnowledgeTools


async def test_health_route_is_registered_without_becoming_tool() -> None:
    tools = KnowledgeTools(revisions=Mock(), authorization=Mock())
    mcp = create_mcp(
        tools=tools,
        jwks_uri="https://login.example/jwks",
        issuer="https://login.example/",
        audience="know-your-project",
    )

    app = mcp.http_app()
    assert any(getattr(route, "path", None) == "/health" for route in app.routes)

    async with Client(mcp) as client:
        listed_tools = await client.list_tools()
    assert {tool.name for tool in listed_tools} == {
        "search_project_knowledge", "get_feature", "get_component",
        "get_release_changes", "compare_releases", "trace_work_item", "get_screen_spec",
    }
