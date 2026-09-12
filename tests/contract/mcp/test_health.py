from unittest.mock import Mock

from know_your_project.mcp.server import create_mcp
from know_your_project.mcp.tools import KnowledgeTools


def test_health_route_is_registered_without_becoming_tool() -> None:
    tools = KnowledgeTools(revisions=Mock(), authorization=Mock())
    mcp = create_mcp(
        tools=tools,
        jwks_uri="https://login.example/jwks",
        issuer="https://login.example/",
        audience="know-your-project",
    )
    assert any(path == "/health" for path, _, _ in mcp.routes)
    assert {name for name, _, _ in mcp.tools} == {
        "search_project_knowledge", "get_feature", "get_component",
        "get_release_changes", "compare_releases", "trace_work_item", "get_screen_spec",
    }
