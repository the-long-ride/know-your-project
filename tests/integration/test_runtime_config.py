from pathlib import Path


def test_compose_keeps_neo4j_private() -> None:
    text = Path("docker-compose.yml").read_text()
    neo4j = text.split("  app:", 1)[0]
    assert "ports:" not in neo4j
    assert '      - "7687"' in neo4j


def test_readme_states_security_boundary() -> None:
    text = Path("README.md").read_text()
    required = """## Security boundary

MCP exposes semantic project knowledge only. It does not expose source files, source snippets,
raw Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials, or raw parser output.

Graphiti and Neo4j are private infrastructure. MCP clients connect only to the Know Your Project
HTTP MCP endpoint. Semantic extraction and embeddings can run entirely on self-hosted model services.
"""
    assert required in text


def test_dockerfile_does_not_assume_uncommitted_lockfile() -> None:
    text = Path("Dockerfile").read_text()
    if not Path("uv.lock").exists():
        assert "--frozen" not in text
