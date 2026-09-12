# Know Your Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted service that synchronizes Azure DevOps source/PBIs/docs/HTML, converts changes into release-aware semantic knowledge stored through Graphiti, and exposes only safe read-only knowledge through MCP.

**Architecture:** Start as a Python modular monolith. Azure DevOps ingestion, parsing/extraction, release semantics, Graphiti storage, authorization, and MCP are separated by explicit protocols. Graphiti is an internal adapter behind `KnowledgeRepository`; it is never exposed directly to end users.

**Tech Stack:** Python 3.12, uv, Pydantic 2, httpx, FastMCP, graphiti-core, Neo4j 5.26+, tree-sitter, BeautifulSoup4/lxml, SQLite via aiosqlite for MVP checkpoints, pytest/pytest-asyncio, respx, Ruff, mypy. Local model access uses an OpenAI-compatible endpoint (Ollama/vLLM) with a non-Chinese-origin model such as `gpt-oss:20b`; embedding model is configurable and local.

**Spec:** `docs/superpowers/specs/2026-09-12-know-your-project-design.md`

## Global Constraints

- Azure DevOps remains the authoritative source; this service does not replace it.
- Graphiti is an internal module and may only be imported by `src/know_your_project/knowledge/graphiti/` plus composition/bootstrap code.
- Public MCP tools are read-only and may not expose raw source code, source snippets, raw Graphiti episodes, arbitrary graph dumps, Cypher, credentials, parser AST bodies, or ingestion prompts.
- Source code must be deterministically parsed before LLM semantic extraction.
- The ingestion LLM is not the user-facing answer model; Claude/Codex performs final synthesis.
- Production must support a fully self-hosted non-Chinese-origin LLM and local embeddings.
- Historical facts are superseded/invalidated, not overwritten or silently deleted.
- Explicit `Release` entities remain separate from branch-head state.
- Synchronization checkpoints advance only after extraction and knowledge persistence succeed.
- Logs and audit events must not contain proprietary source payloads by default.
- One graph namespace (`group_id`) is used per project so project data is isolated in Graphiti.
- Graphiti ingestion must pass an explicit `reference_time`; never use wall-clock ingestion time as release truth when a release/deployment time is known.

---

## Target File Map

```text
pyproject.toml
README.md
.env.example
docker-compose.yml
src/know_your_project/
├── __init__.py
├── bootstrap.py
├── settings.py
├── domain/
│   ├── __init__.py
│   ├── ids.py
│   ├── models.py
│   └── queries.py
├── revisions/
│   ├── __init__.py
│   ├── models.py
│   ├── resolver.py
│   └── diff.py
├── knowledge/
│   ├── __init__.py
│   ├── dto.py
│   ├── interfaces.py
│   ├── memory.py
│   └── graphiti/
│       ├── __init__.py
│       ├── client.py
│       ├── mapper.py
│       └── repository.py
├── extraction/
│   ├── __init__.py
│   ├── models.py
│   ├── llm.py
│   ├── service.py
│   └── parsers/
│       ├── __init__.py
│       ├── base.py
│       ├── source.py
│       ├── html.py
│       └── document.py
├── ingestion/
│   ├── __init__.py
│   ├── models.py
│   ├── checkpoints.py
│   ├── service.py
│   └── azure_devops/
│       ├── __init__.py
│       ├── client.py
│       └── mapper.py
├── security/
│   ├── __init__.py
│   ├── principal.py
│   ├── authorization.py
│   └── projection.py
└── mcp/
    ├── __init__.py
    ├── server.py
    └── tools.py
tests/
├── unit/
├── contract/
└── integration/
```

The file structure intentionally keeps source-system adapters, Graphiti, and MCP isolated from domain types.

---

### Task 1: Bootstrap the Python package and quality gates

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/know_your_project/__init__.py`
- Create: `tests/unit/test_package.py`

**Interfaces:**
- Consumes: none.
- Produces: installable `know_your_project` package, pytest/async test environment, Ruff/mypy commands used by all later tasks.

- [ ] **Step 1: Write the failing package smoke test**

```python
# tests/unit/test_package.py
import know_your_project


def test_package_has_version() -> None:
    assert know_your_project.__version__ == "0.1.0"
```

- [ ] **Step 2: Create `pyproject.toml` and package metadata**

```toml
[project]
name = "know-your-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "aiosqlite>=0.20",
  "beautifulsoup4>=4.12",
  "fastmcp>=2.13",
  "graphiti-core>=0.18",
  "httpx>=0.28",
  "lxml>=5",
  "pydantic>=2.10",
  "pydantic-settings>=2.7",
  "tree-sitter>=0.24",
  "tree-sitter-language-pack>=0.7",
]

[dependency-groups]
dev = [
  "mypy>=1.14",
  "pytest>=8.3",
  "pytest-asyncio>=0.25",
  "respx>=0.22",
  "ruff>=0.9",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100

[tool.mypy]
python_version = "3.12"
strict = true
packages = ["know_your_project"]
```

```python
# src/know_your_project/__init__.py
__version__ = "0.1.0"
```

```dotenv
# .env.example
AZDO_ORGANIZATION=https://dev.azure.com/example
AZDO_PROJECT=ExampleProject
AZDO_TOKEN=replace-me
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=replace-me
LOCAL_LLM_BASE_URL=http://ollama:11434/v1
LOCAL_LLM_API_KEY=ollama
LOCAL_LLM_MODEL=gpt-oss:20b
LOCAL_EMBEDDING_MODEL=nomic-embed-text
MCP_JWT_JWKS_URI=https://login.example/.well-known/jwks.json
MCP_JWT_ISSUER=https://login.example/
MCP_JWT_AUDIENCE=know-your-project
GRAPHITI_TELEMETRY_ENABLED=false
```

- [ ] **Step 3: Install and verify the smoke test**

Run:

```bash
uv sync --all-groups
uv run pytest tests/unit/test_package.py -v
uv run ruff check .
uv run mypy src
```

Expected: all commands pass.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example src/know_your_project tests/unit/test_package.py
git commit -m "build: bootstrap Python service"
```

---

### Task 2: Define domain IDs, artifacts, facts, releases, and public queries

**Files:**
- Create: `src/know_your_project/domain/ids.py`
- Create: `src/know_your_project/domain/models.py`
- Create: `src/know_your_project/domain/queries.py`
- Create: `src/know_your_project/revisions/models.py`
- Test: `tests/unit/domain/test_models.py`

**Interfaces:**
- Consumes: Python/Pydantic only.
- Produces: canonical types `ProjectId`, `ArtifactId`, `ReleaseId`, `SourceArtifact`, `KnowledgeFact`, `Provenance`, `Release`, `BranchState`, `KnowledgeQuery`, `ReleaseComparisonQuery`.

- [ ] **Step 1: Write model invariants first**

```python
# tests/unit/domain/test_models.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.domain.models import KnowledgeFact, Provenance
from know_your_project.revisions.models import Release


def test_knowledge_fact_requires_non_empty_semantic_value() -> None:
    with pytest.raises(ValidationError):
        KnowledgeFact(
            subject="PaymentRetry",
            predicate="max_attempts",
            value="",
            provenance=Provenance(source_kind="git", source_id="abc"),
        )


def test_release_keeps_exact_source_commit() -> None:
    release = Release(
        project_id=ProjectId("payments"),
        release_id=ReleaseId("v3.8.0"),
        tag="v3.8.0",
        commit_sha="a" * 40,
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert release.commit_sha == "a" * 40
```

- [ ] **Step 2: Implement strongly typed IDs**

```python
# src/know_your_project/domain/ids.py
from typing import NewType

ProjectId = NewType("ProjectId", str)
ArtifactId = NewType("ArtifactId", str)
ReleaseId = NewType("ReleaseId", str)
WorkItemId = NewType("WorkItemId", int)
```

- [ ] **Step 3: Implement normalized artifact/fact models**

```python
# src/know_your_project/domain/models.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .ids import ArtifactId, ProjectId, ReleaseId


class Provenance(BaseModel):
    source_kind: Literal["git", "work_item", "document", "html"]
    source_id: str
    repository: str | None = None
    path: str | None = None
    commit_sha: str | None = None
    work_item_id: int | None = None
    release_id: ReleaseId | None = None
    observed_at: datetime | None = None


class SourceArtifact(BaseModel):
    project_id: ProjectId
    artifact_id: ArtifactId
    kind: Literal["source", "work_item", "document", "html"]
    revision: str
    content: str
    path: str | None = None
    commit_sha: str | None = None
    observed_at: datetime


class KnowledgeFact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    object_ref: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: Provenance
```

- [ ] **Step 4: Implement release/branch state and query contracts**

```python
# src/know_your_project/revisions/models.py
from datetime import datetime

from pydantic import BaseModel, Field

from know_your_project.domain.ids import ProjectId, ReleaseId


class Release(BaseModel):
    project_id: ProjectId
    release_id: ReleaseId
    tag: str = Field(min_length=1)
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    effective_at: datetime
    predecessor: ReleaseId | None = None


class BranchState(BaseModel):
    project_id: ProjectId
    branch: str
    commit_sha: str = Field(pattern=r"^[0-9a-fA-F]{40}$")
    observed_at: datetime
```

```python
# src/know_your_project/domain/queries.py
from pydantic import BaseModel, Field

from .ids import ProjectId, ReleaseId, WorkItemId


class KnowledgeQuery(BaseModel):
    project_id: ProjectId
    text: str = Field(min_length=1)
    release_id: ReleaseId | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ReleaseComparisonQuery(BaseModel):
    project_id: ProjectId
    from_release: ReleaseId
    to_release: ReleaseId
    component: str | None = None


class WorkItemTraceQuery(BaseModel):
    project_id: ProjectId
    work_item_id: WorkItemId
    release_id: ReleaseId | None = None
```

- [ ] **Step 5: Run the domain tests**

```bash
uv run pytest tests/unit/domain/test_models.py -v
uv run mypy src/know_your_project/domain src/know_your_project/revisions
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/know_your_project/domain src/know_your_project/revisions tests/unit/domain
git commit -m "feat: define project knowledge domain models"
```

---

### Task 3: Define the `KnowledgeRepository` contract and safe result DTOs

**Files:**
- Create: `src/know_your_project/knowledge/dto.py`
- Create: `src/know_your_project/knowledge/interfaces.py`
- Create: `src/know_your_project/knowledge/memory.py`
- Test: `tests/contract/knowledge/test_repository_contract.py`

**Interfaces:**
- Consumes: domain types from Task 2.
- Produces: `KnowledgeRepository`, `KnowledgeChangeSet`, `KnowledgeResult`, `ReleaseChangeSet`, `ReleaseComparison`, plus an in-memory implementation used by tests/MCP before Graphiti exists.

- [ ] **Step 1: Write repository contract tests**

```python
# tests/contract/knowledge/test_repository_contract.py
from know_your_project.domain.ids import ProjectId
from know_your_project.domain.models import KnowledgeFact, Provenance
from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.knowledge.dto import KnowledgeChangeSet
from know_your_project.knowledge.memory import InMemoryKnowledgeRepository


async def test_apply_then_search_returns_safe_semantic_fact() -> None:
    repo = InMemoryKnowledgeRepository()
    fact = KnowledgeFact(
        subject="PaymentRetry",
        predicate="behavior",
        value="Retries failed payments up to three times",
        provenance=Provenance(source_kind="git", source_id="abc"),
    )
    await repo.apply_changes(KnowledgeChangeSet(project_id=ProjectId("p"), facts=[fact]))

    results = await repo.search(KnowledgeQuery(project_id=ProjectId("p"), text="retry"))

    assert results[0].summary == "PaymentRetry behavior: Retries failed payments up to three times"
    assert not hasattr(results[0], "source_content")
```

- [ ] **Step 2: Implement safe DTOs**

```python
# src/know_your_project/knowledge/dto.py
from datetime import datetime

from pydantic import BaseModel, Field

from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.domain.models import KnowledgeFact


class KnowledgeChangeSet(BaseModel):
    project_id: ProjectId
    reference_time: datetime | None = None
    release_id: ReleaseId | None = None
    facts: list[KnowledgeFact]


class SafeProvenance(BaseModel):
    source_kind: str
    source_id: str
    release_id: ReleaseId | None = None


class KnowledgeResult(BaseModel):
    id: str
    kind: str
    summary: str
    score: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: list[SafeProvenance] = Field(default_factory=list)


class ReleaseChangeSet(BaseModel):
    release_id: ReleaseId
    changes: list[KnowledgeResult]


class ReleaseComparison(BaseModel):
    from_release: ReleaseId
    to_release: ReleaseId
    changes: list[KnowledgeResult]
```

- [ ] **Step 3: Define the storage protocol**

```python
# src/know_your_project/knowledge/interfaces.py
from typing import Protocol

from know_your_project.domain.ids import ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery
from .dto import KnowledgeChangeSet, KnowledgeResult, ReleaseChangeSet, ReleaseComparison


class KnowledgeRepository(Protocol):
    async def apply_changes(self, changes: KnowledgeChangeSet) -> None: ...
    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
    async def get_release_changes(self, release: ReleaseId) -> ReleaseChangeSet: ...
    async def compare_releases(self, query: ReleaseComparisonQuery) -> ReleaseComparison: ...
    async def trace_work_item(self, work_item_id: WorkItemId) -> list[KnowledgeResult]: ...
```

- [ ] **Step 4: Implement the in-memory contract double**

```python
# src/know_your_project/knowledge/memory.py
from know_your_project.domain.ids import ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery
from .dto import (
    KnowledgeChangeSet,
    KnowledgeResult,
    ReleaseChangeSet,
    ReleaseComparison,
    SafeProvenance,
)


class InMemoryKnowledgeRepository:
    def __init__(self) -> None:
        self._changes: list[KnowledgeChangeSet] = []

    async def apply_changes(self, changes: KnowledgeChangeSet) -> None:
        self._changes.append(changes)

    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        needle = query.text.casefold()
        output: list[KnowledgeResult] = []
        for batch in self._changes:
            if batch.project_id != query.project_id:
                continue
            if query.release_id is not None and batch.release_id != query.release_id:
                continue
            for index, fact in enumerate(batch.facts):
                summary = f"{fact.subject} {fact.predicate}: {fact.value}"
                if needle not in summary.casefold():
                    continue
                output.append(
                    KnowledgeResult(
                        id=f"memory:{len(output)}:{index}",
                        kind="fact",
                        summary=summary,
                        valid_from=fact.valid_from,
                        valid_to=fact.valid_to,
                        provenance=[SafeProvenance(
                            source_kind=fact.provenance.source_kind,
                            source_id=fact.provenance.source_id,
                            release_id=fact.provenance.release_id,
                        )],
                    )
                )
        return output[: query.limit]

    async def get_release_changes(self, release: ReleaseId) -> ReleaseChangeSet:
        return ReleaseChangeSet(release_id=release, changes=[])

    async def compare_releases(self, query: ReleaseComparisonQuery) -> ReleaseComparison:
        return ReleaseComparison(
            from_release=query.from_release,
            to_release=query.to_release,
            changes=[],
        )

    async def trace_work_item(self, work_item_id: WorkItemId) -> list[KnowledgeResult]:
        marker = str(int(work_item_id))
        return [r for batch in self._changes for r in await self.search(
            KnowledgeQuery(project_id=batch.project_id, text=marker)
        )]
```

- [ ] **Step 5: Run contract tests and type checks**

```bash
uv run pytest tests/contract/knowledge/test_repository_contract.py -v
uv run mypy src/know_your_project/knowledge
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/know_your_project/knowledge tests/contract/knowledge
git commit -m "feat: add knowledge repository contract"
```

---

### Task 4: Implement Graphiti as a private `KnowledgeRepository` adapter

**Files:**
- Create: `src/know_your_project/knowledge/graphiti/client.py`
- Create: `src/know_your_project/knowledge/graphiti/mapper.py`
- Create: `src/know_your_project/knowledge/graphiti/repository.py`
- Test: `tests/unit/knowledge/graphiti/test_repository.py`
- Test: `tests/integration/knowledge/test_graphiti_neo4j.py`

**Interfaces:**
- Consumes: `KnowledgeChangeSet`, `KnowledgeQuery`, Graphiti `Graphiti.add_episode`, `Graphiti.search`.
- Produces: `GraphitiKnowledgeRepository` implementing `KnowledgeRepository` without leaking Graphiti types.

**Implementation decision:** The first version writes sanitized structured semantic facts as `EpisodeType.json` episodes. Each project uses `group_id=str(project_id)`. This lets Graphiti maintain provenance and temporal invalidation while the public application remains decoupled. Deterministic direct triples can be added later behind the adapter without changing callers.

- [ ] **Step 1: Write a fake-Graphiti adapter test**

```python
# tests/unit/knowledge/graphiti/test_repository.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ProjectId
from know_your_project.domain.models import KnowledgeFact, Provenance
from know_your_project.knowledge.dto import KnowledgeChangeSet
from know_your_project.knowledge.graphiti.repository import GraphitiKnowledgeRepository


class FakeEdge:
    uuid = "edge-1"
    fact = "PaymentRetry behavior: retries failed payments"
    valid_at = datetime(2026, 9, 1, tzinfo=UTC)
    invalid_at = None


class FakeGraphiti:
    def __init__(self) -> None:
        self.added: list[dict[str, object]] = []

    async def add_episode(self, **kwargs: object) -> None:
        self.added.append(kwargs)

    async def search(self, query: str, *, group_id: str) -> list[FakeEdge]:
        assert group_id == "payments"
        return [FakeEdge()]


async def test_adapter_namespaces_project_and_uses_reference_time() -> None:
    graph = FakeGraphiti()
    repo = GraphitiKnowledgeRepository(graph)  # type: ignore[arg-type]
    reference = datetime(2026, 9, 1, tzinfo=UTC)
    await repo.apply_changes(KnowledgeChangeSet(
        project_id=ProjectId("payments"),
        reference_time=reference,
        facts=[KnowledgeFact(
            subject="PaymentRetry",
            predicate="behavior",
            value="retries failed payments",
            provenance=Provenance(source_kind="git", source_id="abc"),
        )],
    ))
    assert graph.added[0]["group_id"] == "payments"
    assert graph.added[0]["reference_time"] == reference
```

- [ ] **Step 2: Implement Graphiti local-client construction**

```python
# src/know_your_project/knowledge/graphiti/client.py
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient


def create_graphiti(
    *,
    neo4j_uri: str,
    neo4j_user: str,
    neo4j_password: str,
    llm_base_url: str,
    llm_api_key: str,
    llm_model: str,
    embedding_model: str,
) -> Graphiti:
    llm_config = LLMConfig(
        api_key=llm_api_key,
        model=llm_model,
        small_model=llm_model,
        base_url=llm_base_url,
    )
    llm_client = OpenAIGenericClient(config=llm_config)
    return Graphiti(
        neo4j_uri,
        neo4j_user,
        neo4j_password,
        llm_client=llm_client,
        embedder=OpenAIEmbedder(
            config=OpenAIEmbedderConfig(
                api_key=llm_api_key,
                embedding_model=embedding_model,
                base_url=llm_base_url,
            )
        ),
        cross_encoder=OpenAIRerankerClient(client=llm_client, config=llm_config),
    )
```

- [ ] **Step 3: Map changes to sanitized JSON episodes**

```python
# src/know_your_project/knowledge/graphiti/mapper.py
import json

from know_your_project.knowledge.dto import KnowledgeChangeSet


def to_episode_json(changes: KnowledgeChangeSet) -> str:
    return json.dumps({
        "release_id": str(changes.release_id) if changes.release_id else None,
        "facts": [
            {
                "subject": fact.subject,
                "predicate": fact.predicate,
                "value": fact.value,
                "object_ref": fact.object_ref,
                "confidence": fact.confidence,
                "provenance": {
                    "source_kind": fact.provenance.source_kind,
                    "source_id": fact.provenance.source_id,
                    "release_id": str(fact.provenance.release_id)
                    if fact.provenance.release_id else None,
                },
            }
            for fact in changes.facts
        ],
    }, sort_keys=True)
```

- [ ] **Step 4: Implement Graphiti repository write/search projection**

```python
# src/know_your_project/knowledge/graphiti/repository.py
from datetime import UTC, datetime
from typing import Any

from graphiti_core.nodes import EpisodeType

from know_your_project.domain.ids import ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery
from know_your_project.knowledge.dto import (
    KnowledgeChangeSet,
    KnowledgeResult,
    ReleaseChangeSet,
    ReleaseComparison,
)
from .mapper import to_episode_json


class GraphitiKnowledgeRepository:
    def __init__(self, graphiti: Any) -> None:
        self._graphiti = graphiti

    async def apply_changes(self, changes: KnowledgeChangeSet) -> None:
        reference_time = changes.reference_time or datetime.now(UTC)
        await self._graphiti.add_episode(
            name=f"knowledge:{changes.project_id}:{reference_time.isoformat()}",
            episode_body=to_episode_json(changes),
            source=EpisodeType.json,
            source_description="normalized project knowledge",
            reference_time=reference_time,
            group_id=str(changes.project_id),
        )

    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
        edges = await self._graphiti.search(query.text, group_id=str(query.project_id))
        output: list[KnowledgeResult] = []
        for edge in edges[: query.limit]:
            output.append(KnowledgeResult(
                id=edge.uuid,
                kind="fact",
                summary=edge.fact,
                score=getattr(edge, "score", None),
                valid_from=getattr(edge, "valid_at", None),
                valid_to=getattr(edge, "invalid_at", None),
            ))
        return output

    async def get_release_changes(self, release: ReleaseId) -> ReleaseChangeSet:
        raise NotImplementedError("implemented by release query service in Task 10")

    async def compare_releases(self, query: ReleaseComparisonQuery) -> ReleaseComparison:
        raise NotImplementedError("implemented by release query service in Task 10")

    async def trace_work_item(self, work_item_id: WorkItemId) -> list[KnowledgeResult]:
        raise NotImplementedError("implemented by release query service in Task 10")
```

The temporary `NotImplementedError` methods are removed in Task 10; do not expose this adapter through MCP before Task 10 is complete.

- [ ] **Step 5: Run unit test**

```bash
uv run pytest tests/unit/knowledge/graphiti/test_repository.py -v
```

Expected: PASS.

- [ ] **Step 6: Add a Neo4j integration test guarded by `RUN_INTEGRATION=1`**

```python
# tests/integration/knowledge/test_graphiti_neo4j.py
import os

import pytest

from know_your_project.knowledge.graphiti.client import create_graphiti


@pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="integration disabled")
async def test_graphiti_initializes_indices() -> None:
    graph = create_graphiti(
        neo4j_uri=os.environ["NEO4J_URI"],
        neo4j_user=os.environ["NEO4J_USER"],
        neo4j_password=os.environ["NEO4J_PASSWORD"],
        llm_base_url=os.environ["LOCAL_LLM_BASE_URL"],
        llm_api_key=os.environ["LOCAL_LLM_API_KEY"],
        llm_model=os.environ["LOCAL_LLM_MODEL"],
        embedding_model=os.environ["LOCAL_EMBEDDING_MODEL"],
    )
    try:
        await graph.build_indices_and_constraints()
    finally:
        await graph.close()
```

- [ ] **Step 7: Commit**

```bash
git add src/know_your_project/knowledge/graphiti tests/unit/knowledge tests/integration/knowledge
git commit -m "feat: add private Graphiti knowledge adapter"
```

---

### Task 5: Implement release resolution and temporal change classification

**Files:**
- Create: `src/know_your_project/revisions/resolver.py`
- Create: `src/know_your_project/revisions/diff.py`
- Test: `tests/unit/revisions/test_resolver.py`
- Test: `tests/unit/revisions/test_diff.py`

**Interfaces:**
- Consumes: Azure ref/tag observations and normalized `KnowledgeFact` lists.
- Produces: exact `Release`, plus `KnowledgeChangeSet` where replaced facts receive `valid_to` and new facts receive `valid_from`.

- [ ] **Step 1: Specify tag-to-release behavior**

```python
# tests/unit/revisions/test_resolver.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.revisions.resolver import resolve_release


def test_resolve_release_binds_tag_to_exact_sha() -> None:
    release = resolve_release(
        project_id=ProjectId("payments"),
        tag="v4.2.0",
        commit_sha="b" * 40,
        effective_at=datetime(2026, 9, 2, tzinfo=UTC),
        predecessor=ReleaseId("v4.1.0"),
    )
    assert release.release_id == ReleaseId("v4.2.0")
    assert release.commit_sha == "b" * 40
```

- [ ] **Step 2: Implement release resolver**

```python
# src/know_your_project/revisions/resolver.py
from datetime import datetime

from know_your_project.domain.ids import ProjectId, ReleaseId
from .models import Release


def resolve_release(
    *,
    project_id: ProjectId,
    tag: str,
    commit_sha: str,
    effective_at: datetime,
    predecessor: ReleaseId | None,
) -> Release:
    return Release(
        project_id=project_id,
        release_id=ReleaseId(tag),
        tag=tag,
        commit_sha=commit_sha,
        effective_at=effective_at,
        predecessor=predecessor,
    )
```

- [ ] **Step 3: Write the supersession test**

```python
# tests/unit/revisions/test_diff.py
from datetime import UTC, datetime

from know_your_project.domain.models import KnowledgeFact, Provenance
from know_your_project.revisions.diff import classify_fact_changes


def _fact(value: str) -> KnowledgeFact:
    return KnowledgeFact(
        subject="PaymentRetry",
        predicate="max_attempts",
        value=value,
        provenance=Provenance(source_kind="git", source_id=value),
    )


def test_changed_fact_expires_old_and_starts_new() -> None:
    at = datetime(2026, 9, 2, tzinfo=UTC)
    result = classify_fact_changes(previous=[_fact("3")], current=[_fact("5")], effective_at=at)
    assert result.superseded[0].valid_to == at
    assert result.added[0].valid_from == at
```

- [ ] **Step 4: Implement fact identity and supersession**

```python
# src/know_your_project/revisions/diff.py
from datetime import datetime

from pydantic import BaseModel

from know_your_project.domain.models import KnowledgeFact


class FactDelta(BaseModel):
    added: list[KnowledgeFact]
    unchanged: list[KnowledgeFact]
    superseded: list[KnowledgeFact]


def _key(fact: KnowledgeFact) -> tuple[str, str]:
    return fact.subject.casefold(), fact.predicate.casefold()


def classify_fact_changes(
    *, previous: list[KnowledgeFact], current: list[KnowledgeFact], effective_at: datetime
) -> FactDelta:
    old = {_key(f): f for f in previous}
    new = {_key(f): f for f in current}
    added: list[KnowledgeFact] = []
    unchanged: list[KnowledgeFact] = []
    superseded: list[KnowledgeFact] = []

    for key, old_fact in old.items():
        new_fact = new.get(key)
        if new_fact is None or new_fact.value != old_fact.value:
            superseded.append(old_fact.model_copy(update={"valid_to": effective_at}))

    for key, new_fact in new.items():
        old_fact = old.get(key)
        if old_fact is not None and old_fact.value == new_fact.value:
            unchanged.append(new_fact)
        else:
            added.append(new_fact.model_copy(update={"valid_from": effective_at}))

    return FactDelta(added=added, unchanged=unchanged, superseded=superseded)
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/revisions -v
uv run mypy src/know_your_project/revisions
git add src/know_your_project/revisions tests/unit/revisions
git commit -m "feat: add release and temporal revision semantics"
```

---

### Task 6: Add deterministic source, HTML, and document parsers

**Files:**
- Create: `src/know_your_project/extraction/models.py`
- Create: `src/know_your_project/extraction/parsers/base.py`
- Create: `src/know_your_project/extraction/parsers/source.py`
- Create: `src/know_your_project/extraction/parsers/html.py`
- Create: `src/know_your_project/extraction/parsers/document.py`
- Test: `tests/unit/extraction/parsers/test_source.py`
- Test: `tests/unit/extraction/parsers/test_html.py`
- Test: `tests/unit/extraction/parsers/test_document.py`

**Interfaces:**
- Consumes: `SourceArtifact`.
- Produces: `ParsedArtifact` containing deterministic symbols/relationships and minimized text suitable for semantic extraction.

- [ ] **Step 1: Define parser contract and parsed model**

```python
# src/know_your_project/extraction/models.py
from pydantic import BaseModel, Field

from know_your_project.domain.models import Provenance


class ParsedSymbol(BaseModel):
    kind: str
    name: str
    container: str | None = None


class ParsedArtifact(BaseModel):
    title: str
    semantic_text: str = Field(max_length=30000)
    symbols: list[ParsedSymbol] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    provenance: Provenance
```

```python
# src/know_your_project/extraction/parsers/base.py
from typing import Protocol

from know_your_project.domain.models import SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class ArtifactParser(Protocol):
    def supports(self, artifact: SourceArtifact) -> bool: ...
    def parse(self, artifact: SourceArtifact) -> ParsedArtifact: ...
```

- [ ] **Step 2: Write source parser test**

```python
# tests/unit/extraction/parsers/test_source.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.domain.models import SourceArtifact
from know_your_project.extraction.parsers.source import TreeSitterSourceParser


def test_source_parser_extracts_class_and_method_without_returning_ast() -> None:
    artifact = SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("src:a.cs"), kind="source",
        revision="abc", path="PaymentService.cs", commit_sha="a" * 40,
        observed_at=datetime.now(UTC),
        content="public class PaymentService { public void RetryPayment() {} }",
    )
    parsed = TreeSitterSourceParser().parse(artifact)
    assert {s.name for s in parsed.symbols} >= {"PaymentService", "RetryPayment"}
    assert "syntax_tree" not in parsed.model_dump()
```

- [ ] **Step 3: Implement Tree-sitter source parsing with language-by-extension**

```python
# src/know_your_project/extraction/parsers/source.py
from tree_sitter_language_pack import get_parser

from know_your_project.domain.models import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact, ParsedSymbol


_LANGUAGE_BY_SUFFIX = {
    ".cs": "c_sharp", ".py": "python", ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".java": "java", ".go": "go", ".rs": "rust",
}
_SYMBOL_NODE_TYPES = {
    "class_declaration": "class",
    "interface_declaration": "interface",
    "method_declaration": "method",
    "function_definition": "function",
    "function_declaration": "function",
}


class TreeSitterSourceParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.path is not None and any(artifact.path.endswith(s) for s in _LANGUAGE_BY_SUFFIX)

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        assert artifact.path is not None
        suffix = next(s for s in _LANGUAGE_BY_SUFFIX if artifact.path.endswith(s))
        tree = get_parser(_LANGUAGE_BY_SUFFIX[suffix]).parse(artifact.content.encode())
        symbols: list[ParsedSymbol] = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            kind = _SYMBOL_NODE_TYPES.get(node.type)
            if kind:
                name_node = node.child_by_field_name("name")
                if name_node:
                    symbols.append(ParsedSymbol(
                        kind=kind,
                        name=artifact.content[name_node.start_byte:name_node.end_byte],
                    ))
            stack.extend(node.children)
        symbol_lines = "\n".join(f"{s.kind}: {s.name}" for s in symbols)
        return ParsedArtifact(
            title=artifact.path,
            semantic_text=symbol_lines,
            symbols=symbols,
            provenance=Provenance(
                source_kind="git", source_id=str(artifact.artifact_id),
                path=artifact.path, commit_sha=artifact.commit_sha,
                observed_at=artifact.observed_at,
            ),
        )
```

- [ ] **Step 4: Write and implement HTML semantic extraction**

```python
# tests/unit/extraction/parsers/test_html.py
from datetime import UTC, datetime
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.domain.models import SourceArtifact
from know_your_project.extraction.parsers.html import HtmlParser


def test_html_parser_extracts_labels_fields_actions_not_markup() -> None:
    artifact = SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("html:retry"), kind="html",
        revision="1", path="retry.html", observed_at=datetime.now(UTC),
        content='<form><label>Amount</label><input name="amount"><button>Retry Payment</button></form>',
    )
    parsed = HtmlParser().parse(artifact)
    assert "Retry Payment" in parsed.semantic_text
    assert "Amount" in parsed.semantic_text
    assert "<form" not in parsed.semantic_text
```

```python
# src/know_your_project/extraction/parsers/html.py
from bs4 import BeautifulSoup

from know_your_project.domain.models import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class HtmlParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "html" or bool(artifact.path and artifact.path.endswith(('.html', '.htm')))

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        soup = BeautifulSoup(artifact.content, "lxml")
        labels = [x.get_text(" ", strip=True) for x in soup.find_all("label")]
        fields = [x.get("name") or x.get("id") for x in soup.find_all(["input", "select", "textarea"])]
        actions = [x.get_text(" ", strip=True) for x in soup.find_all(["button", "a"]) if x.get_text(" ", strip=True)]
        lines = [*(f"label: {x}" for x in labels), *(f"field: {x}" for x in fields if x), *(f"action: {x}" for x in actions)]
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id),
            semantic_text="\n".join(lines),
            provenance=Provenance(source_kind="html", source_id=str(artifact.artifact_id), path=artifact.path),
        )
```

- [ ] **Step 5: Implement plain text/Markdown document normalization**

```python
# src/know_your_project/extraction/parsers/document.py
import re

from know_your_project.domain.models import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class DocumentParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "document"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        normalized = re.sub(r"\n{3,}", "\n\n", artifact.content).strip()
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id),
            semantic_text=normalized[:30000],
            provenance=Provenance(source_kind="document", source_id=str(artifact.artifact_id), path=artifact.path),
        )
```

- [ ] **Step 6: Run parser tests and commit**

```bash
uv run pytest tests/unit/extraction/parsers -v
uv run mypy src/know_your_project/extraction
git add src/know_your_project/extraction tests/unit/extraction
git commit -m "feat: add deterministic artifact parsers"
```

---

### Task 7: Add local structured semantic extraction

**Files:**
- Create: `src/know_your_project/extraction/llm.py`
- Create: `src/know_your_project/extraction/service.py`
- Test: `tests/unit/extraction/test_llm.py`
- Test: `tests/unit/extraction/test_service.py`

**Interfaces:**
- Consumes: `ParsedArtifact`.
- Produces: validated `list[KnowledgeFact]` only; raw model prose is rejected.

- [ ] **Step 1: Write strict structured-output test**

```python
# tests/unit/extraction/test_llm.py
import httpx
import respx

from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.models import ParsedArtifact
from know_your_project.domain.models import Provenance


@respx.mock
async def test_local_extractor_returns_validated_facts() -> None:
    respx.post("http://llm/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content": '{"facts":[{"subject":"PaymentRetry","predicate":"behavior","value":"Retries failed payments","confidence":0.9}]}'}}]
    }))
    extractor = LocalKnowledgeExtractor(base_url="http://llm/v1", api_key="x", model="gpt-oss:20b")
    facts = await extractor.extract(ParsedArtifact(
        title="PaymentService.cs", semantic_text="class: PaymentService\nmethod: RetryPayment",
        provenance=Provenance(source_kind="git", source_id="abc"),
    ))
    assert facts[0].subject == "PaymentRetry"
```

- [ ] **Step 2: Implement extractor with Pydantic validation**

```python
# src/know_your_project/extraction/llm.py
import json

import httpx
from pydantic import BaseModel, Field

from know_your_project.domain.models import KnowledgeFact
from know_your_project.extraction.models import ParsedArtifact


class ExtractedFact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    object_ref: str | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


class ExtractionPayload(BaseModel):
    facts: list[ExtractedFact]


class LocalKnowledgeExtractor:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._api_key = api_key
        self._model = model

    async def extract(self, artifact: ParsedArtifact) -> list[KnowledgeFact]:
        prompt = (
            "Extract only semantic project knowledge. Do not reproduce source code. "
            "Return JSON with key 'facts'; each fact has subject, predicate, value, object_ref, confidence.\n\n"
            f"Artifact: {artifact.title}\n{artifact.semantic_text}"
        )
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "response_format": {"type": "json_object"},
                    "temperature": 0,
                },
            )
            response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        parsed = ExtractionPayload.model_validate(json.loads(raw))
        return [KnowledgeFact(
            subject=item.subject,
            predicate=item.predicate,
            value=item.value,
            object_ref=item.object_ref,
            confidence=item.confidence,
            provenance=artifact.provenance,
        ) for item in parsed.facts]
```

- [ ] **Step 3: Implement parser routing + extraction service**

```python
# src/know_your_project/extraction/service.py
from know_your_project.domain.models import KnowledgeFact, SourceArtifact
from .llm import LocalKnowledgeExtractor
from .parsers.base import ArtifactParser


class ExtractionService:
    def __init__(self, parsers: list[ArtifactParser], extractor: LocalKnowledgeExtractor) -> None:
        self._parsers = parsers
        self._extractor = extractor

    async def extract(self, artifact: SourceArtifact) -> list[KnowledgeFact]:
        parser = next((p for p in self._parsers if p.supports(artifact)), None)
        if parser is None:
            return []
        parsed = parser.parse(artifact)
        return await self._extractor.extract(parsed)
```

- [ ] **Step 4: Test unsupported files are skipped instead of sent raw to the LLM**

```python
# tests/unit/extraction/test_service.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.domain.models import SourceArtifact
from know_your_project.extraction.service import ExtractionService


async def test_unsupported_artifact_is_not_sent_to_llm() -> None:
    extractor = AsyncMock()
    service = ExtractionService([], extractor)
    facts = await service.extract(SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("binary"), kind="source",
        revision="1", path="asset.bin", observed_at=datetime.now(UTC), content="SECRET",
    ))
    assert facts == []
    extractor.extract.assert_not_called()
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/extraction -v
uv run mypy src/know_your_project/extraction
git add src/know_your_project/extraction tests/unit/extraction
git commit -m "feat: add local structured knowledge extraction"
```

---

### Task 8: Implement Azure DevOps read adapter

**Files:**
- Create: `src/know_your_project/ingestion/models.py`
- Create: `src/know_your_project/ingestion/azure_devops/client.py`
- Create: `src/know_your_project/ingestion/azure_devops/mapper.py`
- Test: `tests/unit/ingestion/azure_devops/test_client.py`
- Test: `tests/unit/ingestion/azure_devops/test_mapper.py`

**Interfaces:**
- Consumes: Azure DevOps REST API 7.1 responses.
- Produces: refs/commits/changed files/work item revisions as normalized ingestion models; no Graphiti dependency.

- [ ] **Step 1: Define transport-neutral ingestion models**

```python
# src/know_your_project/ingestion/models.py
from datetime import datetime
from pydantic import BaseModel


class GitRef(BaseModel):
    name: str
    object_id: str


class ChangedFile(BaseModel):
    path: str
    change_type: str
    object_id: str | None = None


class WorkItemRevision(BaseModel):
    id: int
    revision: int
    type: str
    title: str
    description: str = ""
    acceptance_criteria: str = ""
    state: str
    changed_at: datetime | None = None
```

- [ ] **Step 2: Write an HTTP contract test using `respx`**

```python
# tests/unit/ingestion/azure_devops/test_client.py
import httpx
import respx

from know_your_project.ingestion.azure_devops.client import AzureDevOpsClient


@respx.mock
async def test_list_refs_maps_azure_response() -> None:
    respx.get("https://dev.azure.com/acme/P/_apis/git/repositories/r/refs").mock(
        return_value=httpx.Response(200, json={"value": [{"name": "refs/heads/main", "objectId": "a" * 40}]})
    )
    client = AzureDevOpsClient(base_url="https://dev.azure.com/acme", project="P", token="t")
    refs = await client.list_refs("r")
    assert refs[0].name == "refs/heads/main"
```

- [ ] **Step 3: Implement Azure REST client with PAT Basic auth and API versioning**

```python
# src/know_your_project/ingestion/azure_devops/client.py
import base64

import httpx

from know_your_project.ingestion.models import ChangedFile, GitRef


class AzureDevOpsClient:
    def __init__(self, *, base_url: str, project: str, token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._project = project
        encoded = base64.b64encode(f":{token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def _get(self, path: str, params: dict[str, str] | None = None) -> dict:
        merged = {"api-version": "7.1", **(params or {})}
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(f"{self._base_url}/{self._project}/_apis/{path}", params=merged)
            response.raise_for_status()
            return response.json()

    async def list_refs(self, repository: str) -> list[GitRef]:
        body = await self._get(f"git/repositories/{repository}/refs")
        return [GitRef(name=item["name"], object_id=item["objectId"]) for item in body["value"]]

    async def changed_files(self, repository: str, base: str, target: str) -> list[ChangedFile]:
        body = await self._get(
            f"git/repositories/{repository}/diffs/commits",
            {"baseVersion": base, "targetVersion": target},
        )
        return [ChangedFile(
            path=item["item"]["path"],
            change_type=item["changeType"],
            object_id=item["item"].get("objectId"),
        ) for item in body.get("changes", [])]

    async def file_text(self, repository: str, path: str, version: str) -> str:
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(
                f"{self._base_url}/{self._project}/_apis/git/repositories/{repository}/items",
                params={"path": path, "versionDescriptor.version": version, "includeContent": "true", "api-version": "7.1"},
            )
            response.raise_for_status()
            return response.text
```

- [ ] **Step 4: Implement work item mapping**

```python
# src/know_your_project/ingestion/azure_devops/mapper.py
from know_your_project.ingestion.models import WorkItemRevision


def map_work_item(payload: dict) -> WorkItemRevision:
    fields = payload["fields"]
    return WorkItemRevision(
        id=payload["id"],
        revision=payload["rev"],
        type=fields["System.WorkItemType"],
        title=fields["System.Title"],
        description=fields.get("System.Description", ""),
        acceptance_criteria=fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", ""),
        state=fields["System.State"],
        changed_at=fields.get("System.ChangedDate"),
    )
```

- [ ] **Step 5: Run unit tests and commit**

```bash
uv run pytest tests/unit/ingestion/azure_devops -v
uv run mypy src/know_your_project/ingestion
git add src/know_your_project/ingestion tests/unit/ingestion
git commit -m "feat: add Azure DevOps ingestion adapter"
```

---

### Task 9: Add durable idempotent checkpoints and sync planning

**Files:**
- Create: `src/know_your_project/ingestion/checkpoints.py`
- Create: `src/know_your_project/ingestion/service.py`
- Test: `tests/unit/ingestion/test_checkpoints.py`
- Test: `tests/unit/ingestion/test_service.py`

**Interfaces:**
- Consumes: Azure DevOps refs/diffs from Task 8.
- Produces: stable `SourceArtifact` batches and commits checkpoints only after caller confirms persistence.

- [ ] **Step 1: Write checkpoint atomicity test**

```python
# tests/unit/ingestion/test_checkpoints.py
from know_your_project.ingestion.checkpoints import SqliteCheckpointStore


async def test_checkpoint_round_trip(tmp_path) -> None:
    store = SqliteCheckpointStore(str(tmp_path / "sync.db"))
    await store.initialize()
    await store.set("payments", "repo", "refs/heads/main", "a" * 40)
    assert await store.get("payments", "repo", "refs/heads/main") == "a" * 40
```

- [ ] **Step 2: Implement SQLite checkpoint store**

```python
# src/know_your_project/ingestion/checkpoints.py
import aiosqlite


class SqliteCheckpointStore:
    def __init__(self, path: str) -> None:
        self._path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    project TEXT NOT NULL,
                    repository TEXT NOT NULL,
                    ref TEXT NOT NULL,
                    sha TEXT NOT NULL,
                    PRIMARY KEY(project, repository, ref)
                )
            """)
            await db.commit()

    async def get(self, project: str, repository: str, ref: str) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            cursor = await db.execute(
                "SELECT sha FROM checkpoints WHERE project=? AND repository=? AND ref=?",
                (project, repository, ref),
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set(self, project: str, repository: str, ref: str, sha: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO checkpoints(project,repository,ref,sha) VALUES(?,?,?,?) "
                "ON CONFLICT(project,repository,ref) DO UPDATE SET sha=excluded.sha",
                (project, repository, ref, sha),
            )
            await db.commit()
```

- [ ] **Step 3: Implement sync planning without advancing checkpoint**

```python
# src/know_your_project/ingestion/service.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.domain.models import SourceArtifact
from .azure_devops.client import AzureDevOpsClient
from .checkpoints import SqliteCheckpointStore


class SyncService:
    def __init__(self, client: AzureDevOpsClient, checkpoints: SqliteCheckpointStore) -> None:
        self._client = client
        self._checkpoints = checkpoints

    async def plan_git_sync(
        self, *, project_id: ProjectId, repository: str, ref: str, new_sha: str
    ) -> list[SourceArtifact]:
        old_sha = await self._checkpoints.get(str(project_id), repository, ref)
        if old_sha == new_sha:
            return []
        changed = await self._client.changed_files(repository, old_sha or new_sha, new_sha)
        artifacts: list[SourceArtifact] = []
        for item in changed:
            if item.change_type.lower() == "delete":
                continue
            content = await self._client.file_text(repository, item.path, new_sha)
            kind = "html" if item.path.endswith((".html", ".htm")) else "source"
            artifacts.append(SourceArtifact(
                project_id=project_id,
                artifact_id=ArtifactId(f"git:{repository}:{item.path}"),
                kind=kind,
                revision=new_sha,
                content=content,
                path=item.path,
                commit_sha=new_sha,
                observed_at=datetime.now(UTC),
            ))
        return artifacts

    async def commit_checkpoint(self, *, project_id: ProjectId, repository: str, ref: str, sha: str) -> None:
        await self._checkpoints.set(str(project_id), repository, ref, sha)
```

- [ ] **Step 4: Verify no-op sync behavior and commit**

```bash
uv run pytest tests/unit/ingestion/test_checkpoints.py tests/unit/ingestion/test_service.py -v
git add src/know_your_project/ingestion tests/unit/ingestion
git commit -m "feat: add idempotent sync checkpoints"
```

---

### Task 10: Build the end-to-end ingestion pipeline and complete release-aware repository methods

**Files:**
- Create: `src/know_your_project/bootstrap.py`
- Modify: `src/know_your_project/knowledge/graphiti/repository.py`
- Create: `src/know_your_project/revisions/query_service.py`
- Test: `tests/integration/test_ingestion_pipeline.py`
- Test: `tests/unit/revisions/test_query_service.py`

**Interfaces:**
- Consumes: `SourceArtifact -> ExtractionService -> KnowledgeChangeSet -> KnowledgeRepository`.
- Produces: one transaction-like orchestration path where checkpoint advancement happens only after successful graph persistence; release query methods return safe DTOs.

- [ ] **Step 1: Write pipeline ordering test**

```python
# tests/integration/test_ingestion_pipeline.py
from unittest.mock import AsyncMock

from know_your_project.bootstrap import IngestionPipeline


async def test_checkpoint_advances_only_after_graph_write() -> None:
    extraction = AsyncMock()
    repository = AsyncMock()
    checkpoints = AsyncMock()
    pipeline = IngestionPipeline(extraction=extraction, repository=repository, checkpoints=checkpoints)
    extraction.extract.return_value = []

    await pipeline.persist_artifacts(
        project_id="p", repository_name="r", ref="refs/heads/main", sha="a" * 40,
        artifacts=[], release=None,
    )

    repository.apply_changes.assert_awaited_once()
    checkpoints.set.assert_awaited_once()
```

- [ ] **Step 2: Implement orchestration**

```python
# src/know_your_project/bootstrap.py
from know_your_project.domain.ids import ProjectId
from know_your_project.domain.models import SourceArtifact
from know_your_project.knowledge.dto import KnowledgeChangeSet
from know_your_project.knowledge.interfaces import KnowledgeRepository
from know_your_project.revisions.models import Release


class IngestionPipeline:
    def __init__(self, *, extraction, repository: KnowledgeRepository, checkpoints) -> None:
        self._extraction = extraction
        self._repository = repository
        self._checkpoints = checkpoints

    async def persist_artifacts(
        self,
        *,
        project_id: str,
        repository_name: str,
        ref: str,
        sha: str,
        artifacts: list[SourceArtifact],
        release: Release | None,
    ) -> None:
        facts = []
        for artifact in artifacts:
            facts.extend(await self._extraction.extract(artifact))
        if release:
            facts = [fact.model_copy(update={
                "valid_from": release.effective_at,
                "provenance": fact.provenance.model_copy(update={"release_id": release.release_id}),
            }) for fact in facts]
        await self._repository.apply_changes(KnowledgeChangeSet(
            project_id=ProjectId(project_id),
            reference_time=release.effective_at if release else None,
            release_id=release.release_id if release else None,
            facts=facts,
        ))
        await self._checkpoints.set(project_id, repository_name, ref, sha)
```

- [ ] **Step 3: Implement release query service using repository search as the only public retrieval primitive**

```python
# src/know_your_project/revisions/query_service.py
from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery
from know_your_project.knowledge.dto import KnowledgeResult, ReleaseChangeSet, ReleaseComparison
from know_your_project.knowledge.interfaces import KnowledgeRepository


class ReleaseQueryService:
    def __init__(self, repository: KnowledgeRepository) -> None:
        self._repository = repository

    async def get_release_changes(self, project_id: ProjectId, release: ReleaseId) -> ReleaseChangeSet:
        results = await self._repository.search(KnowledgeQuery(
            project_id=project_id, text="change", release_id=release, limit=50
        ))
        return ReleaseChangeSet(release_id=release, changes=results)

    async def compare(self, query: ReleaseComparisonQuery) -> ReleaseComparison:
        before = await self._repository.search(KnowledgeQuery(
            project_id=query.project_id,
            text=query.component or "behavior",
            release_id=query.from_release,
            limit=50,
        ))
        after = await self._repository.search(KnowledgeQuery(
            project_id=query.project_id,
            text=query.component or "behavior",
            release_id=query.to_release,
            limit=50,
        ))
        before_summary = {r.summary for r in before}
        changes = [r for r in after if r.summary not in before_summary]
        return ReleaseComparison(
            from_release=query.from_release,
            to_release=query.to_release,
            changes=changes,
        )

    async def trace_work_item(self, project_id: ProjectId, work_item_id: WorkItemId) -> list[KnowledgeResult]:
        return await self._repository.search(KnowledgeQuery(
            project_id=project_id, text=f"PBI-{int(work_item_id)}", limit=50
        ))
```

- [ ] **Step 4: Remove Task 4 temporary `NotImplementedError` methods**

Change `GraphitiKnowledgeRepository` to delegate release-specific public operations to query composition outside the adapter. Narrow `KnowledgeRepository` to `apply_changes()` and `search()` only, then update `InMemoryKnowledgeRepository` and all affected tests. This keeps release semantics in `revisions`, matching the approved architecture.

Exact final protocol:

```python
class KnowledgeRepository(Protocol):
    async def apply_changes(self, changes: KnowledgeChangeSet) -> None: ...
    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
```

- [ ] **Step 5: Run integration/unit tests and commit**

```bash
uv run pytest tests/unit/revisions tests/integration/test_ingestion_pipeline.py -v
uv run mypy src
git add src/know_your_project tests
git commit -m "feat: connect ingestion extraction revisions and graph storage"
```

---

### Task 11: Add project authorization and strict safe projection

**Files:**
- Create: `src/know_your_project/security/principal.py`
- Create: `src/know_your_project/security/authorization.py`
- Create: `src/know_your_project/security/projection.py`
- Test: `tests/unit/security/test_authorization.py`
- Test: `tests/unit/security/test_projection.py`

**Interfaces:**
- Consumes: authenticated subject/claims and internal `KnowledgeResult`.
- Produces: project-scoped authorization and MCP-safe output with deny-by-default raw-field detection.

- [ ] **Step 1: Write deny-by-default authorization test**

```python
# tests/unit/security/test_authorization.py
import pytest

from know_your_project.domain.ids import ProjectId
from know_your_project.security.authorization import AuthorizationError, AuthorizationService
from know_your_project.security.principal import Principal


def test_unknown_project_is_denied() -> None:
    authz = AuthorizationService()
    principal = Principal(subject="alice", projects={ProjectId("project-a")})
    with pytest.raises(AuthorizationError):
        authz.require_project(principal, ProjectId("project-b"))
```

- [ ] **Step 2: Implement principal and authorization**

```python
# src/know_your_project/security/principal.py
from pydantic import BaseModel
from know_your_project.domain.ids import ProjectId


class Principal(BaseModel):
    subject: str
    projects: set[ProjectId]
```

```python
# src/know_your_project/security/authorization.py
from know_your_project.domain.ids import ProjectId
from .principal import Principal


class AuthorizationError(PermissionError):
    pass


class AuthorizationService:
    def require_project(self, principal: Principal, project_id: ProjectId) -> None:
        if project_id not in principal.projects:
            raise AuthorizationError(f"project access denied: {project_id}")
```

- [ ] **Step 3: Write source-leak projection test**

```python
# tests/unit/security/test_projection.py
from know_your_project.knowledge.dto import KnowledgeResult
from know_your_project.security.projection import project_result


def test_project_result_contains_only_allowlisted_fields() -> None:
    projected = project_result(KnowledgeResult(id="x", kind="fact", summary="semantic behavior"))
    assert set(projected) == {"id", "kind", "summary", "score", "valid_from", "valid_to", "provenance"}
    assert "source_content" not in str(projected)
```

- [ ] **Step 4: Implement explicit allowlist projection**

```python
# src/know_your_project/security/projection.py
from know_your_project.knowledge.dto import KnowledgeResult


def project_result(result: KnowledgeResult) -> dict[str, object]:
    return {
        "id": result.id,
        "kind": result.kind,
        "summary": result.summary,
        "score": result.score,
        "valid_from": result.valid_from.isoformat() if result.valid_from else None,
        "valid_to": result.valid_to.isoformat() if result.valid_to else None,
        "provenance": [p.model_dump(mode="json") for p in result.provenance],
    }
```

- [ ] **Step 5: Run security tests and commit**

```bash
uv run pytest tests/unit/security -v
git add src/know_your_project/security tests/unit/security
git commit -m "feat: enforce project authorization and safe projection"
```

---

### Task 12: Expose only restricted read-only MCP tools

**Files:**
- Create: `src/know_your_project/mcp/tools.py`
- Create: `src/know_your_project/mcp/server.py`
- Test: `tests/contract/mcp/test_tools.py`

**Interfaces:**
- Consumes: `KnowledgeRepository`, `ReleaseQueryService`, `AuthorizationService`, authenticated principal.
- Produces: MCP tools `search_project_knowledge`, `get_feature`, `get_component`, `get_release_changes`, `compare_releases`, `trace_work_item`, `get_screen_spec`; all read-only.

- [ ] **Step 1: Write tool-level confidentiality test**

```python
# tests/contract/mcp/test_tools.py
from know_your_project.mcp.tools import KnowledgeTools


async def test_search_tool_projects_results_without_raw_source(fake_services) -> None:
    tools = KnowledgeTools(**fake_services)
    result = await tools.search_project_knowledge(
        query="payment retry", project="payments", release=None
    )
    assert "source_content" not in str(result)
    assert "cypher" not in str(result).lower()
```

- [ ] **Step 2: Implement application-facing tool service**

```python
# src/know_your_project/mcp/tools.py
from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery
from know_your_project.security.projection import project_result


class KnowledgeTools:
    def __init__(self, *, repository, revisions, authorization, principal_provider) -> None:
        self._repository = repository
        self._revisions = revisions
        self._authorization = authorization
        self._principal_provider = principal_provider

    async def search_project_knowledge(self, query: str, project: str, release: str | None = None):
        project_id = ProjectId(project)
        principal = self._principal_provider()
        self._authorization.require_project(principal, project_id)
        results = await self._repository.search(KnowledgeQuery(
            project_id=project_id,
            text=query,
            release_id=ReleaseId(release) if release else None,
        ))
        return [project_result(r) for r in results]

    async def compare_releases(self, project: str, from_release: str, to_release: str, component: str | None = None):
        project_id = ProjectId(project)
        principal = self._principal_provider()
        self._authorization.require_project(principal, project_id)
        result = await self._revisions.compare(ReleaseComparisonQuery(
            project_id=project_id,
            from_release=ReleaseId(from_release),
            to_release=ReleaseId(to_release),
            component=component,
        ))
        return {**result.model_dump(mode="json"), "changes": [project_result(r) for r in result.changes]}

    async def trace_work_item(self, project: str, work_item_id: int):
        project_id = ProjectId(project)
        principal = self._principal_provider()
        self._authorization.require_project(principal, project_id)
        results = await self._revisions.trace_work_item(project_id, WorkItemId(work_item_id))
        return [project_result(r) for r in results]
```

Implement `get_feature`, `get_component`, and `get_screen_spec` as thin calls to `search_project_knowledge` with prefixes `feature:`, `component:`, and `screen:` respectively; implement `get_release_changes` as `ReleaseQueryService.get_release_changes()` followed by `project_result()` for every change.

- [ ] **Step 3: Register only the allowed FastMCP tools and mark them read-only**

```python
# src/know_your_project/mcp/server.py
from fastmcp import FastMCP
from mcp.types import ToolAnnotations


def create_mcp(tools: KnowledgeTools, auth=None) -> FastMCP:
    mcp = FastMCP(name="Know Your Project", auth=auth)
    annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
    mcp.tool(annotations=annotations)(tools.search_project_knowledge)
    mcp.tool(annotations=annotations)(tools.get_feature)
    mcp.tool(annotations=annotations)(tools.get_component)
    mcp.tool(annotations=annotations)(tools.get_release_changes)
    mcp.tool(annotations=annotations)(tools.compare_releases)
    mcp.tool(annotations=annotations)(tools.trace_work_item)
    mcp.tool(annotations=annotations)(tools.get_screen_spec)
    return mcp
```

There must be no tool for raw episode retrieval, source retrieval, graph dump, arbitrary query, mutation, or Cypher.

- [ ] **Step 4: Configure JWT verification for HTTP deployment**

Use FastMCP `JWTVerifier` from environment-backed settings:

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier


auth = JWTVerifier(
    jwks_uri=settings.mcp_jwt_jwks_uri,
    issuer=settings.mcp_jwt_issuer,
    audience=settings.mcp_jwt_audience,
)
```

The `principal_provider` maps validated token claims to `Principal(subject=..., projects=...)`; project grants are derived from a configurable claim such as `projects` for MVP.

- [ ] **Step 5: Run contract tests and commit**

```bash
uv run pytest tests/contract/mcp -v
git add src/know_your_project/mcp tests/contract/mcp
git commit -m "feat: expose restricted read-only MCP knowledge tools"
```

---

### Task 13: Add configuration, health endpoint, structured logging, and audit events

**Files:**
- Create: `src/know_your_project/settings.py`
- Modify: `src/know_your_project/mcp/server.py`
- Create: `src/know_your_project/infrastructure/logging.py`
- Test: `tests/unit/test_settings.py`
- Test: `tests/contract/mcp/test_health.py`

**Interfaces:**
- Consumes: environment variables.
- Produces: typed configuration, `/health`, sanitized operational logs, MCP audit events with no semantic payload bodies.

- [ ] **Step 1: Implement typed settings**

```python
# src/know_your_project/settings.py
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azdo_organization: AnyHttpUrl
    azdo_project: str
    azdo_token: str
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    local_llm_base_url: AnyHttpUrl
    local_llm_api_key: str
    local_llm_model: str
    local_embedding_model: str
    mcp_jwt_jwks_uri: AnyHttpUrl
    mcp_jwt_issuer: str
    mcp_jwt_audience: str
    checkpoint_db: str = "./data/checkpoints.db"
```

- [ ] **Step 2: Add JSON logging helper that refuses raw content fields**

```python
# src/know_your_project/infrastructure/logging.py
import json
import logging

logger = logging.getLogger("know_your_project")

_FORBIDDEN = {"content", "source_content", "episode_body", "token", "password"}


def audit(event: str, **fields: object) -> None:
    if _FORBIDDEN.intersection(fields):
        raise ValueError("raw/sensitive fields are forbidden in audit logs")
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))
```

- [ ] **Step 3: Add FastMCP health route**

```python
from starlette.requests import Request
from starlette.responses import JSONResponse


@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "know-your-project"})
```

- [ ] **Step 4: Test health/config/logging and commit**

```bash
uv run pytest tests/unit/test_settings.py tests/contract/mcp/test_health.py -v
uv run ruff check .
uv run mypy src
git add src/know_your_project tests
git commit -m "feat: add runtime configuration health and audit logging"
```

---

### Task 14: Add self-hosted local development deployment

**Files:**
- Create: `docker-compose.yml`
- Create: `README.md`
- Modify: `.env.example`
- Test: `tests/integration/test_runtime_config.py`

**Interfaces:**
- Consumes: Docker, local OpenAI-compatible model endpoint, Neo4j.
- Produces: reproducible local stack and documented startup path.

- [ ] **Step 1: Add Neo4j and application services**

```yaml
# docker-compose.yml
services:
  neo4j:
    image: neo4j:5.26-community
    environment:
      NEO4J_AUTH: neo4j/local-development-password
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j-data:/data

  app:
    build: .
    env_file: .env
    depends_on:
      - neo4j
    ports:
      - "8000:8000"

volumes:
  neo4j-data:
```

Add a minimal `Dockerfile` in this task if containerized application startup is selected:

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install uv && uv sync --frozen --no-dev
CMD ["uv", "run", "python", "-m", "know_your_project.mcp.server"]
```

- [ ] **Step 2: Document the privacy boundary and startup**

`README.md` must include these explicit statements:

```markdown
## Security boundary

The public MCP server exposes semantic project knowledge only. It does not expose source files,
source snippets, Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials, or
raw parser output.

Graphiti and Neo4j must remain on a private network. MCP clients connect only to this project's
restricted HTTP MCP endpoint.
```

Also document:

```bash
cp .env.example .env
uv sync --all-groups
docker compose up -d neo4j
uv run pytest
uv run python -m know_your_project.mcp.server
```

Document the local model requirement separately: an OpenAI-compatible local endpoint must be available at `LOCAL_LLM_BASE_URL`; the default example model is `gpt-oss:20b`, not a hosted external API.

- [ ] **Step 3: Verify compose parsing and test suite**

```bash
docker compose config
uv run pytest -q
uv run ruff check .
uv run mypy src
```

Expected: compose is valid; all tests pass.

- [ ] **Step 4: Commit**

```bash
git add Dockerfile docker-compose.yml README.md .env.example tests/integration/test_runtime_config.py
git commit -m "docs: add self-hosted deployment and security guidance"
```

---

### Task 15: Add Azure DevOps webhook/reconciliation entrypoints and release indexing state

**Files:**
- Create: `src/know_your_project/ingestion/webhooks.py`
- Create: `src/know_your_project/ingestion/reconciliation.py`
- Modify: `src/know_your_project/ingestion/checkpoints.py`
- Modify: `src/know_your_project/mcp/server.py`
- Test: `tests/unit/ingestion/test_webhooks.py`
- Test: `tests/unit/ingestion/test_reconciliation.py`

**Interfaces:**
- Consumes: Azure DevOps service-hook push/work-item events plus scheduled ref reconciliation.
- Produces: deduplicated sync requests and release indexing status (`pending`, `indexing`, `ready`, `failed`).

- [ ] **Step 1: Define event parsing tests**

```python
# tests/unit/ingestion/test_webhooks.py
from know_your_project.ingestion.webhooks import parse_push_event


def test_push_event_extracts_repo_ref_and_commits() -> None:
    event = parse_push_event({
        "resource": {
            "repository": {"id": "repo-1"},
            "refUpdates": [{"name": "refs/heads/main", "oldObjectId": "a" * 40, "newObjectId": "b" * 40}],
        }
    })
    assert event.repository == "repo-1"
    assert event.ref == "refs/heads/main"
    assert event.new_sha == "b" * 40
```

- [ ] **Step 2: Implement event model/parser**

```python
# src/know_your_project/ingestion/webhooks.py
from pydantic import BaseModel


class PushEvent(BaseModel):
    repository: str
    ref: str
    old_sha: str
    new_sha: str


def parse_push_event(payload: dict) -> PushEvent:
    resource = payload["resource"]
    update = resource["refUpdates"][0]
    return PushEvent(
        repository=resource["repository"]["id"],
        ref=update["name"],
        old_sha=update["oldObjectId"],
        new_sha=update["newObjectId"],
    )
```

- [ ] **Step 3: Extend checkpoint DB with release indexing state**

Add table:

```sql
CREATE TABLE IF NOT EXISTS release_index_state (
  project TEXT NOT NULL,
  release_id TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','indexing','ready','failed')),
  error_code TEXT,
  PRIMARY KEY(project, release_id)
)
```

Expose methods:

```python
async def set_release_state(self, project: str, release_id: str, commit_sha: str, status: str, error_code: str | None = None) -> None: ...
async def get_release_state(self, project: str, release_id: str) -> tuple[str, str] | None: ...
```

- [ ] **Step 4: Add webhook custom route that enqueues/processes a sync request but never exposes ingestion through MCP tools**

```python
@mcp.custom_route("/hooks/azure-devops", methods=["POST"])
async def azure_hook(request: Request) -> JSONResponse:
    payload = await request.json()
    event = parse_push_event(payload)
    await webhook_handler.handle(event)
    return JSONResponse({"accepted": True}, status_code=202)
```

Protect this route using a separate shared secret/header or reverse-proxy policy; it is not authenticated as an MCP user and it must not be registered as an MCP tool.

- [ ] **Step 5: Implement reconciliation comparison**

```python
# src/know_your_project/ingestion/reconciliation.py
class ReconciliationService:
    def __init__(self, client, checkpoints, handler) -> None:
        self._client = client
        self._checkpoints = checkpoints
        self._handler = handler

    async def reconcile(self, *, project: str, repository: str, tracked_refs: set[str]) -> None:
        for ref in await self._client.list_refs(repository):
            if ref.name not in tracked_refs:
                continue
            known = await self._checkpoints.get(project, repository, ref.name)
            if known != ref.object_id:
                await self._handler.handle_ref(repository=repository, ref=ref.name, new_sha=ref.object_id)
```

- [ ] **Step 6: Run tests and commit**

```bash
uv run pytest tests/unit/ingestion -v
git add src/know_your_project/ingestion src/know_your_project/mcp/server.py tests/unit/ingestion
git commit -m "feat: add Azure DevOps webhook and reconciliation sync"
```

---

### Task 16: Final security, release-history, and end-to-end acceptance suite

**Files:**
- Create: `tests/integration/test_release_history.py`
- Create: `tests/integration/test_no_source_leak.py`
- Create: `tests/integration/test_project_isolation.py`
- Create: `tests/integration/test_missed_webhook_recovery.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: complete service.
- Produces: acceptance evidence for the design's four highest-risk properties: history, confidentiality, tenant/project isolation, and recovery.

- [ ] **Step 1: Add historical behavior acceptance test**

```python
async def test_old_release_remains_queryable_after_new_release(app_fixture) -> None:
    await app_fixture.index_release("v3.8.0", facts={"PaymentRetry.max_attempts": "3"})
    await app_fixture.index_release("v4.2.0", facts={"PaymentRetry.max_attempts": "5"})

    old = await app_fixture.search("PaymentRetry max attempts", release="v3.8.0")
    new = await app_fixture.search("PaymentRetry max attempts", release="v4.2.0")

    assert any("3" in result["summary"] for result in old)
    assert any("5" in result["summary"] for result in new)
```

- [ ] **Step 2: Add confidentiality acceptance test**

```python
async def test_mcp_never_returns_ingested_source_text(app_fixture) -> None:
    secret_source = "private void HighlySensitiveImplementationSecret() {}"
    await app_fixture.index_source("Secret.cs", secret_source)
    response = await app_fixture.mcp_search("sensitive implementation")
    assert secret_source not in str(response)
    assert "HighlySensitiveImplementationSecret() {}" not in str(response)
```

- [ ] **Step 3: Add project namespace isolation test**

```python
async def test_project_a_cannot_search_project_b(app_fixture) -> None:
    await app_fixture.index_fact(project="project-b", fact="Internal Billing Feature")
    response = await app_fixture.mcp_search("Billing", project="project-a", principal_projects={"project-a"})
    assert "Internal Billing Feature" not in str(response)
```

- [ ] **Step 4: Add reconciliation recovery test**

```python
async def test_reconciliation_recovers_missed_push(app_fixture) -> None:
    await app_fixture.set_checkpoint("repo", "refs/heads/main", "a" * 40)
    app_fixture.azure_ref("repo", "refs/heads/main", "b" * 40)
    await app_fixture.reconcile()
    assert await app_fixture.get_checkpoint("repo", "refs/heads/main") == "b" * 40
```

- [ ] **Step 5: Run the complete verification suite**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
docker compose config
```

For an environment with Neo4j + local LLM available:

```bash
RUN_INTEGRATION=1 uv run pytest tests/integration -v
```

Expected: all enabled tests pass, no MCP response contains raw source, release history remains queryable, and project namespaces remain isolated.

- [ ] **Step 6: Update README status and commit**

Document implemented MCP tools, supported artifact types, current local model configuration, release semantics, and exact integration-test command.

```bash
git add tests/integration README.md
git commit -m "test: verify release history confidentiality and recovery"
```

---

## Implementation Order and Review Gates

Execute Tasks 1-16 strictly in order. Reviewer gates are especially important after:

1. **Task 3** — domain/storage contract is stable before Graphiti coupling.
2. **Task 4** — Graphiti remains private and project namespacing is correct.
3. **Task 7** — LLM receives minimized parsed content and emits only validated facts.
4. **Task 10** — checkpoints cannot advance before graph persistence.
5. **Task 12** — MCP has only explicit read-only tools and safe projection.
6. **Task 16** — acceptance suite proves historical queries and no-source-leak behavior.

## Current-library notes verified during planning

- Graphiti's current core API supports `add_episode(..., reference_time=..., group_id=...)` and `search(query, group_id=...)`; JSON episodes are appropriate for normalized structured input.
- Graphiti project namespacing is based on `group_id`; use exactly one group ID per project for the initial design.
- Graphiti can use local OpenAI-compatible inference through `OpenAIGenericClient`; this avoids Graphiti's default OpenAI dependency.
- Graphiti requires Neo4j 5.26+ when using Neo4j.
- FastMCP supports async tools, read-only `ToolAnnotations`, JWT verification, and HTTP `@custom_route` endpoints such as `/health`.

## Definition of Done

The MVP is complete when all of the following are true:

- Azure DevOps Git changes can be synchronized incrementally and reconciled after missed events.
- Work item normalization is implemented and can enter the same extraction pipeline.
- Source/HTML/doc inputs are parsed deterministically before any LLM semantic extraction.
- A self-hosted OpenAI-compatible LLM generates validated semantic facts.
- Graphiti stores project-scoped, reference-time-aware knowledge through the private adapter.
- Software releases retain exact tag/SHA/effective-time identity and historical facts are queryable.
- MCP exposes only the approved seven read-only knowledge tools.
- JWT authentication and project authorization are enforced for HTTP MCP access.
- Raw source content, raw Graphiti episodes, credentials, and arbitrary graph access are absent from MCP responses/tools.
- Sync checkpoints advance only after knowledge persistence succeeds.
- `/health`, structured audit logging, and release indexing states exist.
- Unit, contract, and integration tests cover confidentiality, project isolation, revision history, and missed-webhook recovery.
- `uv run pytest -q`, `uv run ruff check .`, and `uv run mypy src` pass.
