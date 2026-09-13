from unittest.mock import Mock

from mcp import Client
from mcp.server import MCPServer

from know_your_project.mcp.server import create_mcp
from know_your_project.mcp.tools import KnowledgeTools


async def test_server_negotiates_current_mcp_protocol() -> None:
    server = create_mcp(
        tools=KnowledgeTools(revisions=Mock(), authorization=Mock()),
        jwks_uri="https://login.example/jwks",
        issuer="https://login.example/",
        audience="know-your-project",
        resource_server_url="https://knowledge.example/mcp",
    )

    assert isinstance(server, MCPServer)
    async with Client(server) as client:
        assert str(client.protocol_version) == "2026-07-28"
        listed = await client.list_tools()

    assert {tool.name for tool in listed.tools} == {
        "search_project_knowledge",
        "get_feature",
        "get_component",
        "get_release_changes",
        "compare_releases",
        "trace_work_item",
        "get_screen_spec",
    }
