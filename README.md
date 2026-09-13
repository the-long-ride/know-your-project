# Know Your Project

Self-hosted, release-aware project knowledge for Claude, Codex, and other MCP clients. The service synchronizes Azure DevOps code, work items, repository documents, and HTML mockups; derives semantic facts locally; stores temporal knowledge through Graphiti; and exposes only a restricted read-only MCP interface.

## Security boundary

MCP exposes semantic project knowledge only. It does not expose source files, source snippets,
raw Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials, raw parser output,
or internal source paths/IDs. Public provenance uses opaque reference IDs plus safe release metadata.

Graphiti and Neo4j are private infrastructure. MCP clients connect only to the Know Your Project
HTTP MCP endpoint. Semantic extraction and embeddings can run entirely on self-hosted model services.

The extraction boundary treats source/PBI/document content as untrusted data, rejects instructions embedded in artifacts, and rejects verbatim source or internal-path echoes across all public fact fields. Treat the semantic projection as the external security boundary: anything returned through MCP may be visible to the connected model/client.

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

## MCP protocol and tools

The service uses the official Model Context Protocol Python SDK v2 (`mcp>=2.2,<3`) and negotiates the current `2026-07-28` protocol. Streamable HTTP is served at `/mcp` in stateless JSON-response mode.

The public MCP surface is intentionally limited to exactly seven read-only tools:

- `search_project_knowledge`
- `get_feature`
- `get_component`
- `get_release_changes`
- `compare_releases`
- `trace_work_item`
- `get_screen_spec`

Project-wide work-item knowledge and release-scoped software facts are searched together at the selected release timestamp. Live branch facts remain excluded from the public release query path.

## Authentication

HTTP MCP requests use bearer JWTs verified against the configured JWKS endpoint. The verifier checks:

- RS256 signature and signing-key ID
- issuer
- audience
- expiration
- subject
- optional required scopes configured by `MCP_REQUIRED_SCOPES`

Project authorization is then derived from the token's `projects` claim. The MCP resource-server URL is published as resource metadata, while JWT audience validation remains explicit in the verifier.

## Supported project inputs

Repository synchronization currently recognizes:

- source: `.cs`, `.py`, `.ts`, `.tsx`, `.js`, `.java`, `.go`, `.rs`
- documents: `.md`, `.txt`, `.rst`
- mockups/templates: `.html`, `.htm`
- Azure DevOps work items: PBIs, user stories, bugs, and configured work-item types routed through the same semantic extraction pipeline

Source is deterministically parsed before the local LLM receives bounded internal context. Source-extension matching is case-insensitive. HTML is converted to screen/action/field semantics rather than exposed as markup through MCP.

## Release and reconciliation semantics

A release is an explicit project object with a tag, exact commit SHA, and effective timestamp. Historical facts are invalidated rather than overwritten, allowing release-time queries to apply:

```text
valid_at <= release_time
AND (invalid_at > release_time OR invalid_at IS NULL)
```

Live branch state and release identity are separate concepts. Azure DevOps remains the source of truth. New tracked refs are fully backfilled; later updates process changed files only. Release tags are synchronized separately and create immutable release identities while semantic fact history remains temporal.

Work-item reconciliation stores revision checkpoints independently from Git refs. It also retires locally known work items that disappear from Azure DevOps, so missed deletion service-hook events are recovered during periodic reconciliation.

## Graphiti and local models

The project pins `graphiti-core>=0.30.2,<0.31`, the Graphiti minor line exercised by CI. Because the project intentionally does not commit a generated `uv.lock`, keeping the pre-1 Graphiti dependency within the tested minor line avoids silent API jumps during builds. Graphiti and Neo4j remain private services.

Semantic extraction uses an OpenAI-compatible self-hosted endpoint such as Ollama or vLLM. For a lightweight local setup, the recommended models are:

```bash
ollama pull granite4:3b
ollama pull granite-embedding:30m
```

Configure them with:

```env
LOCAL_LLM_MODEL=granite4:3b
LOCAL_EMBEDDING_MODEL=granite-embedding:30m
```

`granite4:3b` is the recommended lightweight default for semantic extraction when `gpt-oss:20b` is too large. `granite-embedding:30m` is the recommended lightweight embedding model. The previous examples, `gpt-oss:20b` and `nomic-embed-text`, remain valid alternatives.

No external model provider is required for proprietary source processing. Azure DevOps and local LLM clients reuse long-lived HTTP transports rather than creating a new connection pool per request.

## Configuration

```bash
cp .env.example .env
```

At minimum configure Azure DevOps access, Neo4j credentials, local model endpoints, JWT verification, and `AZDO_WEBHOOK_SECRET`.

Synchronization settings:

- `AZDO_REPOSITORIES`: comma-separated Azure DevOps repository IDs or names to reconcile.
- `AZDO_TRACKED_REFS`: comma-separated branch refs, for example `refs/heads/main,refs/heads/develop`.
- `AZDO_RELEASE_TAG_PREFIX`: tag prefix treated as software releases; defaults to `refs/tags/`.
- `AZDO_WORK_ITEM_TYPES`: comma-separated work-item types to reconcile; defaults to Product Backlog Item, User Story, and Bug.
- `RECONCILIATION_INTERVAL_SECONDS`: periodic reconciliation interval; defaults to 300 seconds.

MCP authentication settings:

- `MCP_JWT_JWKS_URI`: JWKS URL used to verify bearer-token signatures.
- `MCP_JWT_ISSUER`: exact expected issuer.
- `MCP_JWT_AUDIENCE`: exact expected audience.
- `MCP_RESOURCE_SERVER_URL`: public MCP resource URL, for example `https://knowledge.example/mcp`.
- `MCP_REQUIRED_SCOPES`: optional comma-separated scopes enforced by the MCP server.

Azure DevOps service hooks call:

```text
POST /hooks/azure-devops
x-kyp-webhook-secret: <AZDO_WEBHOOK_SECRET>
```

The webhook is an HTTP route, not an MCP tool. It accepts Git push events and Azure DevOps `workitem.*` events. Invalid webhook secrets return `401`; malformed or unsupported payloads return `400`. Periodic reconciliation remains required so missed service-hook events are recovered.

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
docker compose config
```

Graphiti/Neo4j integration:

```bash
RUN_GRAPHITI_INTEGRATION=1 uv run pytest tests/integration/knowledge -v
```

CI runs the Graphiti/Neo4j integration against a real Neo4j service container in addition to the unit/contract suite, Ruff, mypy, and Compose validation.