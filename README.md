# Know Your Project

Self-hosted, release-aware project knowledge for Claude, Codex, and other MCP clients. The service synchronizes Azure DevOps code, work items, repository documents, and HTML mockups; derives semantic facts locally; stores temporal knowledge through Graphiti; and exposes only a restricted read-only MCP interface.

## Security boundary

MCP exposes semantic project knowledge only. It does not expose source files, source snippets,
raw Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials, or raw parser output.

Graphiti and Neo4j are private infrastructure. MCP clients connect only to the Know Your Project
HTTP MCP endpoint. Semantic extraction and embeddings can run entirely on self-hosted model services.

## Architecture

```text
Azure DevOps
  -> deterministic parsers
  -> self-hosted semantic extraction LLM
  -> deterministic revision engine
  -> private Graphiti + Neo4j
  -> project authorization + safe projection
  -> read-only MCP
  -> Claude / Codex
```

Graphiti is an internal module behind the project knowledge interface. The application owns release identity and exact fact invalidation; canonical facts do not use Graphiti's automatic `add_episode` or `add_triplet` contradiction path.

## MCP tools

The public MCP surface is intentionally limited to exactly seven read-only tools:

- `search_project_knowledge`
- `get_feature`
- `get_component`
- `get_release_changes`
- `compare_releases`
- `trace_work_item`
- `get_screen_spec`

## Supported project inputs

Repository synchronization currently recognizes:

- source: `.cs`, `.py`, `.ts`, `.tsx`, `.js`, `.java`, `.go`, `.rs`
- documents: `.md`, `.txt`, `.rst`
- mockups/templates: `.html`, `.htm`
- Azure DevOps work items: PBIs/user stories and other work-item payloads routed through the same semantic extraction pipeline

Source is deterministically parsed before the local LLM receives bounded internal context. HTML is converted to screen/action/field semantics rather than exposed as markup through MCP.

## Release semantics

A release is an explicit project object with a tag, exact commit SHA, and effective timestamp. Historical facts are invalidated rather than overwritten, allowing release-time queries to apply:

```text
valid_at <= release_time
AND (invalid_at > release_time OR invalid_at IS NULL)
```

Live branch state and release identity are separate concepts. Azure DevOps remains the source of truth.

## Graphiti and local models

The project pins `graphiti-core>=0.28.2,<1`. Graphiti and Neo4j remain private services.

Semantic extraction uses an OpenAI-compatible self-hosted endpoint such as Ollama or vLLM. The default example model is `gpt-oss:20b`; the embedding model is configured independently through `LOCAL_EMBEDDING_MODEL`.

No external model provider is required for proprietary source processing.

## Configuration

```bash
cp .env.example .env
```

At minimum configure Azure DevOps access, Neo4j credentials, local model endpoints, JWT verification, and `AZDO_WEBHOOK_SECRET`.

Azure DevOps service hooks call:

```text
POST /hooks/azure-devops
x-kyp-webhook-secret: <AZDO_WEBHOOK_SECRET>
```

The webhook is an HTTP route, not an MCP tool.

## Run locally

```bash
uv sync --all-groups
docker compose up -d neo4j
uv run pytest
uv run python -m know_your_project.app
```

MCP is served on port `8000`. The Neo4j Bolt port is exposed only inside the Compose network.

## Containers

```bash
docker compose up --build
```

The application image performs dependency resolution during image build because this repository does not yet commit a generated `uv.lock`.

## Verification

Unit and contract suite:

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
```

Graphiti/Neo4j integration, when Neo4j and local model services are configured:

```bash
RUN_GRAPHITI_INTEGRATION=1 uv run pytest tests/integration/knowledge -v
```
