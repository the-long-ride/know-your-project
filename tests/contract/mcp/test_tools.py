import inspect

from know_your_project.mcp.tools import KnowledgeTools


def test_public_tool_methods_are_exact_allowlist() -> None:
    public = {
        name for name, fn in inspect.getmembers(KnowledgeTools, inspect.iscoroutinefunction)
        if not name.startswith("_")
    }
    assert public == {
        "search_project_knowledge", "get_feature", "get_component",
        "get_release_changes", "compare_releases", "trace_work_item", "get_screen_spec",
    }


def test_no_source_or_graph_admin_tool_name_exists() -> None:
    names = " ".join(dir(KnowledgeTools)).lower()
    for forbidden in ["cypher", "source_file", "raw_episode", "graph_dump", "mutate"]:
        assert forbidden not in names
