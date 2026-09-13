import tomllib
from pathlib import Path


def test_compose_keeps_neo4j_private() -> None:
    text = Path("docker-compose.yml").read_text()
    neo4j = text.split("  app:", 1)[0]
    assert "ports:" not in neo4j
    assert '      - "7687"' in neo4j


def test_readme_states_security_boundary() -> None:
    text = Path("README.md").read_text()
    required_claims = (
        "## Security boundary",
        "MCP exposes semantic project knowledge only.",
        "It does not expose source files, source snippets,",
        "raw Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials",
        "Graphiti and Neo4j are private infrastructure.",
        "MCP clients connect only to the Know Your Project",
        "Semantic extraction and embeddings can run entirely on self-hosted model services.",
    )
    for claim in required_claims:
        assert claim in text


def test_dockerfile_does_not_assume_uncommitted_lockfile() -> None:
    text = Path("Dockerfile").read_text()
    if not Path("uv.lock").exists():
        assert "--frozen" not in text


def test_graphiti_dependency_is_pinned_to_tested_minor() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text())
    dependencies = project["project"]["dependencies"]
    assert "graphiti-core>=0.30.2,<0.31" in dependencies
