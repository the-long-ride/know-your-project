# Know Your Project Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted service that synchronizes Azure DevOps source code, PBIs, repository documents, and HTML mockups; converts changes into release-aware semantic facts; persists those facts through a private Graphiti module; and exposes only safe read-only knowledge through MCP.

**Architecture:** Build a Python modular monolith with explicit contracts between Azure DevOps ingestion, deterministic parsing, local semantic extraction, release/revision logic, Graphiti persistence/search, authorization, and MCP. The application—not Graphiti—owns release semantics and fact invalidation. Graphiti is used as a private graph/search module and is never exposed directly to MCP users.

**Tech Stack:** Python 3.12, uv, Pydantic 2, httpx, FastMCP 2.x, `graphiti-core>=0.28.2,<1`, Neo4j 5.26+, tree-sitter, BeautifulSoup4/lxml, SQLite via aiosqlite for synchronization/revision state, pytest/pytest-asyncio, respx, Ruff, mypy. Local semantic extraction uses an OpenAI-compatible self-hosted endpoint such as Ollama/vLLM with a non-Chinese-origin model (default example: `gpt-oss:20b`). Embeddings are local and configurable.

**Spec:** `docs/superpowers/specs/2026-09-12-know-your-project-design.md`

## Global Constraints

- Azure DevOps remains the authoritative source of project state.
- Graphiti is internal. Only `src/know_your_project/knowledge/graphiti/` and composition/bootstrap code may import Graphiti classes.
- Pin `graphiti-core>=0.28.2,<1`; versions through 0.28.1 contain a patched Cypher-injection vulnerability.
- Do **not** use Graphiti `add_episode()` or `add_triplet()` for canonical release facts. Current Graphiti automatic contradiction/invalidation behavior can retire unrelated semantically similar facts. Our revision engine must decide exactly which fact version is superseded.
- Persist canonical Graphiti nodes/edges directly with deterministic UUIDs. Generate embeddings through Graphiti clients, then save nodes/edges through Graphiti model APIs.
- Source code must be deterministically parsed before semantic LLM extraction.
- The local LLM is an ingestion/extraction worker only. Claude/Codex performs final user-facing synthesis.
- Production supports fully self-hosted inference and embeddings; proprietary code must not require an external model provider.
- Historical fact versions are invalidated with an effective timestamp; they are not overwritten or hard-deleted during normal synchronization.
- Explicit releases are separate from live branch heads.
- A synchronization checkpoint advances only after graph mutations and revision-state persistence succeed.
- Raw source code, source snippets, raw Graphiti episodes, arbitrary graph dumps, Cypher, credentials, parser AST bodies, and ingestion prompts must never be exposed by public MCP tools.
- MCP query parameters never become Graphiti node-label filters or arbitrary graph expressions.
- Use exactly one Graphiti `group_id` per project for MVP isolation.
- Logs/audit events exclude proprietary artifact payloads by default.

---

## Target File Map

```text
pyproject.toml
.env.example
Dockerfile
docker-compose.yml
README.md
src/know_your_project/
├── __init__.py
├── app.py
├── settings.py
├── domain/
│   ├── __init__.py
│   ├── ids.py
│   ├── artifacts.py
│   └── queries.py
├── revisions/
│   ├── __init__.py
│   ├── models.py
│   ├── engine.py
│   ├── store.py
│   └── queries.py
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
│       ├── document.py
│       └── work_item.py
├── ingestion/
│   ├── __init__.py
│   ├── models.py
│   ├── checkpoints.py
│   ├── pipeline.py
│   ├── reconciliation.py
│   ├── webhooks.py
│   └── azure_devops/
│       ├── __init__.py
│       ├── client.py
│       └── mapper.py
├── knowledge/
│   ├── __init__.py
│   ├── dto.py
│   ├── interfaces.py
│   └── graphiti/
│       ├── __init__.py
│       ├── client.py
│       ├── ids.py
│       ├── repository.py
│       └── temporal.py
├── security/
│   ├── __init__.py
│   ├── principal.py
│   ├── authorization.py
│   └── projection.py
├── infrastructure/
│   ├── __init__.py
│   └── logging.py
└── mcp/
    ├── __init__.py
    ├── tools.py
    └── server.py
tests/
├── unit/
├── contract/
└── integration/
```

---

### Task 1: Bootstrap the Python service and quality gates

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/know_your_project/__init__.py`
- Test: `tests/unit/test_package.py`

**Interfaces:**
- Consumes: none.
- Produces: installable package and common test/lint/type-check commands.

- [ ] **Step 1: Write the package smoke test**

```python
# tests/unit/test_package.py
import know_your_project


def test_package_version() -> None:
    assert know_your_project.__version__ == "0.1.0"
```

- [ ] **Step 2: Create project metadata**

```toml
# pyproject.toml
[project]
name = "know-your-project"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "aiosqlite>=0.20,<1",
  "beautifulsoup4>=4.12,<5",
  "fastmcp>=2.13,<3",
  "graphiti-core>=0.28.2,<1",
  "httpx>=0.28,<1",
  "lxml>=5,<7",
  "pydantic>=2.10,<3",
  "pydantic-settings>=2.7,<3",
  "tree-sitter>=0.24,<1",
  "tree-sitter-language-pack>=0.7,<1",
]

[dependency-groups]
dev = [
  "mypy>=1.14,<2",
  "pytest>=8.3,<9",
  "pytest-asyncio>=0.25,<1",
  "respx>=0.22,<1",
  "ruff>=0.9,<1",
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
AZDO_WEBHOOK_SECRET=replace-me
NEO4J_URI=bolt://neo4j:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=replace-me
LOCAL_LLM_BASE_URL=http://host.docker.internal:11434/v1
LOCAL_LLM_API_KEY=ollama
LOCAL_LLM_MODEL=gpt-oss:20b
LOCAL_EMBEDDING_MODEL=nomic-embed-text
MCP_JWT_JWKS_URI=https://login.example/.well-known/jwks.json
MCP_JWT_ISSUER=https://login.example/
MCP_JWT_AUDIENCE=know-your-project
CHECKPOINT_DB=./data/state.db
GRAPHITI_TELEMETRY_ENABLED=false
```

- [ ] **Step 3: Verify the bootstrap**

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
git commit -m "build: bootstrap project knowledge service"
```

---

### Task 2: Define artifacts, semantic facts, releases, mutations, and queries

**Files:**
- Create: `src/know_your_project/domain/ids.py`
- Create: `src/know_your_project/domain/artifacts.py`
- Create: `src/know_your_project/domain/queries.py`
- Create: `src/know_your_project/revisions/models.py`
- Test: `tests/unit/domain/test_models.py`

**Interfaces:**
- Produces: all framework-independent domain types used by later tasks.

- [ ] **Step 1: Write invariants**

```python
# tests/unit/domain/test_models.py
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ProjectId, ReleaseId
from know_your_project.revisions.models import Release


def test_fact_candidate_rejects_empty_value() -> None:
    with pytest.raises(ValidationError):
        FactCandidate(
            subject="PaymentRetry",
            predicate="max_attempts",
            value="",
            confidence=1.0,
            provenance=Provenance(source_kind="git", source_id="src:payment"),
        )


def test_release_is_bound_to_exact_commit() -> None:
    release = Release(
        project_id=ProjectId("payments"),
        release_id=ReleaseId("v3.8.0"),
        tag="v3.8.0",
        commit_sha="a" * 40,
        effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    assert release.commit_sha == "a" * 40
```

- [ ] **Step 2: Implement IDs and artifact models**

```python
# src/know_your_project/domain/ids.py
from typing import NewType

ProjectId = NewType("ProjectId", str)
ArtifactId = NewType("ArtifactId", str)
ReleaseId = NewType("ReleaseId", str)
WorkItemId = NewType("WorkItemId", int)
```

```python
# src/know_your_project/domain/artifacts.py
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


class SourceArtifact(BaseModel):
    project_id: ProjectId
    artifact_id: ArtifactId
    kind: Literal["source", "work_item", "document", "html"]
    revision: str
    content: str
    observed_at: datetime
    path: str | None = None
    repository: str | None = None
    commit_sha: str | None = None


class FactCandidate(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1)
    object_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    provenance: Provenance
```

- [ ] **Step 3: Implement release/version and mutation models**

```python
# src/know_your_project/revisions/models.py
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId


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


class FactVersion(BaseModel):
    edge_uuid: str
    artifact_id: ArtifactId
    subject: str
    predicate: str
    value: str
    object_ref: str | None = None
    confidence: float
    valid_from: datetime
    valid_to: datetime | None = None
    provenance: Provenance


class UpsertFact(BaseModel):
    kind: Literal["upsert"] = "upsert"
    fact: FactVersion


class InvalidateFact(BaseModel):
    kind: Literal["invalidate"] = "invalidate"
    edge_uuid: str
    invalid_at: datetime


GraphMutation = UpsertFact | InvalidateFact


class RevisionPlan(BaseModel):
    mutations: list[GraphMutation]
    active_versions: list[FactVersion]
```

- [ ] **Step 4: Define public query types using `as_of`, not Graphiti-specific filters**

```python
# src/know_your_project/domain/queries.py
from datetime import datetime

from pydantic import BaseModel, Field

from .ids import ProjectId, ReleaseId, WorkItemId


class KnowledgeQuery(BaseModel):
    project_id: ProjectId
    text: str = Field(min_length=1)
    as_of: datetime | None = None
    limit: int = Field(default=10, ge=1, le=50)


class ReleaseKnowledgeQuery(BaseModel):
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

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/domain/test_models.py -v
uv run mypy src/know_your_project/domain src/know_your_project/revisions
git add src/know_your_project/domain src/know_your_project/revisions tests/unit/domain
git commit -m "feat: define temporal project knowledge domain"
```

---

### Task 3: Build durable release/fact state and the deterministic revision engine

**Files:**
- Create: `src/know_your_project/revisions/store.py`
- Create: `src/know_your_project/revisions/engine.py`
- Test: `tests/unit/revisions/test_store.py`
- Test: `tests/unit/revisions/test_engine.py`

**Interfaces:**
- Consumes: current `FactCandidate` list per artifact and exact effective time.
- Produces: explicit `UpsertFact`/`InvalidateFact` mutations. No LLM and no Graphiti automatic contradiction logic decides invalidation.

- [ ] **Step 1: Write changed/removed/unchanged fact tests**

```python
# tests/unit/revisions/test_engine.py
from datetime import UTC, datetime

from know_your_project.domain.artifacts import FactCandidate, Provenance
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.revisions.engine import RevisionEngine


def fact(value: str) -> FactCandidate:
    return FactCandidate(
        subject="PaymentRetry",
        predicate="max_attempts",
        value=value,
        confidence=1.0,
        provenance=Provenance(source_kind="git", source_id="payment.cs"),
    )


def test_changed_fact_invalidates_only_same_artifact_subject_predicate() -> None:
    engine = RevisionEngine()
    at1 = datetime(2026, 9, 1, tzinfo=UTC)
    at2 = datetime(2026, 9, 2, tzinfo=UTC)
    first = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("git:r:/Payment.cs"),
        previous=[], current=[fact("3")], effective_at=at1,
    )
    second = engine.plan(
        project_id=ProjectId("p"), artifact_id=ArtifactId("git:r:/Payment.cs"),
        previous=first.active_versions, current=[fact("5")], effective_at=at2,
    )
    assert [m.kind for m in second.mutations] == ["invalidate", "upsert"]
    assert second.active_versions[0].value == "5"
```

- [ ] **Step 2: Implement deterministic fact keys and version UUIDs**

```python
# src/know_your_project/revisions/engine.py
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from know_your_project.domain.artifacts import FactCandidate
from know_your_project.domain.ids import ArtifactId, ProjectId
from .models import FactVersion, InvalidateFact, RevisionPlan, UpsertFact


def _slot(subject: str, predicate: str) -> tuple[str, str]:
    return subject.strip().casefold(), predicate.strip().casefold()


def _version_uuid(
    project_id: ProjectId,
    artifact_id: ArtifactId,
    candidate: FactCandidate,
    effective_at: datetime,
) -> str:
    raw = "|".join([
        str(project_id), str(artifact_id), candidate.subject.strip().casefold(),
        candidate.predicate.strip().casefold(), candidate.value.strip(),
        candidate.object_ref or "", effective_at.isoformat(),
    ])
    return str(uuid5(NAMESPACE_URL, raw))


class RevisionEngine:
    def plan(
        self,
        *,
        project_id: ProjectId,
        artifact_id: ArtifactId,
        previous: list[FactVersion],
        current: list[FactCandidate],
        effective_at: datetime,
    ) -> RevisionPlan:
        old = {_slot(f.subject, f.predicate): f for f in previous if f.valid_to is None}
        new = {_slot(f.subject, f.predicate): f for f in current}
        mutations = []
        active: list[FactVersion] = []

        for key, old_fact in old.items():
            candidate = new.get(key)
            same = candidate is not None and (
                candidate.value == old_fact.value and candidate.object_ref == old_fact.object_ref
            )
            if same:
                active.append(old_fact)
            else:
                mutations.append(InvalidateFact(edge_uuid=old_fact.edge_uuid, invalid_at=effective_at))

        for key, candidate in new.items():
            old_fact = old.get(key)
            same = old_fact is not None and (
                old_fact.value == candidate.value and old_fact.object_ref == candidate.object_ref
            )
            if same:
                continue
            version = FactVersion(
                edge_uuid=_version_uuid(project_id, artifact_id, candidate, effective_at),
                artifact_id=artifact_id,
                subject=candidate.subject,
                predicate=candidate.predicate,
                value=candidate.value,
                object_ref=candidate.object_ref,
                confidence=candidate.confidence,
                valid_from=effective_at,
                provenance=candidate.provenance,
            )
            active.append(version)
            mutations.append(UpsertFact(fact=version))

        return RevisionPlan(mutations=mutations, active_versions=active)
```

- [ ] **Step 3: Write state-store round-trip test**

```python
# tests/unit/revisions/test_store.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId
from know_your_project.revisions.models import Release
from know_your_project.revisions.store import SqliteRevisionStore


async def test_release_round_trip(tmp_path) -> None:
    store = SqliteRevisionStore(str(tmp_path / "state.db"))
    await store.initialize()
    release = Release(
        project_id=ProjectId("p"), release_id=ReleaseId("v1"), tag="v1",
        commit_sha="a" * 40, effective_at=datetime(2026, 9, 1, tzinfo=UTC),
    )
    await store.save_release(release)
    assert (await store.get_release(ProjectId("p"), ReleaseId("v1"))).commit_sha == "a" * 40
    assert await store.get_active_facts(ProjectId("p"), ArtifactId("x")) == []
```

- [ ] **Step 4: Implement SQLite state tables and methods**

Use these tables exactly:

```sql
CREATE TABLE IF NOT EXISTS releases (
  project TEXT NOT NULL,
  release_id TEXT NOT NULL,
  tag TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  effective_at TEXT NOT NULL,
  predecessor TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  PRIMARY KEY(project, release_id)
);
CREATE TABLE IF NOT EXISTS active_facts (
  project TEXT NOT NULL,
  artifact_id TEXT NOT NULL,
  edge_uuid TEXT NOT NULL,
  fact_json TEXT NOT NULL,
  PRIMARY KEY(project, artifact_id, edge_uuid)
);
```

```python
# src/know_your_project/revisions/store.py
import json
import aiosqlite

from know_your_project.domain.ids import ArtifactId, ProjectId, ReleaseId
from .models import FactVersion, Release


class SqliteRevisionStore:
    def __init__(self, path: str) -> None:
        self._path = path

    async def initialize(self) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.executescript("""
            CREATE TABLE IF NOT EXISTS releases (
              project TEXT NOT NULL, release_id TEXT NOT NULL, tag TEXT NOT NULL,
              commit_sha TEXT NOT NULL, effective_at TEXT NOT NULL, predecessor TEXT,
              status TEXT NOT NULL DEFAULT 'pending', PRIMARY KEY(project, release_id));
            CREATE TABLE IF NOT EXISTS active_facts (
              project TEXT NOT NULL, artifact_id TEXT NOT NULL, edge_uuid TEXT NOT NULL,
              fact_json TEXT NOT NULL, PRIMARY KEY(project, artifact_id, edge_uuid));
            """)
            await db.commit()

    async def save_release(self, release: Release) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT OR REPLACE INTO releases VALUES(?,?,?,?,?,?,COALESCE((SELECT status FROM releases WHERE project=? AND release_id=?),'pending'))",
                (str(release.project_id), str(release.release_id), release.tag, release.commit_sha,
                 release.effective_at.isoformat(), str(release.predecessor) if release.predecessor else None,
                 str(release.project_id), str(release.release_id)),
            )
            await db.commit()

    async def get_release(self, project: ProjectId, release_id: ReleaseId) -> Release | None:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT tag,commit_sha,effective_at,predecessor FROM releases WHERE project=? AND release_id=?",
                (str(project), str(release_id)),
            )
            row = await cur.fetchone()
        if row is None:
            return None
        from datetime import datetime
        return Release(
            project_id=project, release_id=release_id, tag=row[0], commit_sha=row[1],
            effective_at=datetime.fromisoformat(row[2]),
            predecessor=ReleaseId(row[3]) if row[3] else None,
        )

    async def get_active_facts(self, project: ProjectId, artifact_id: ArtifactId) -> list[FactVersion]:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT fact_json FROM active_facts WHERE project=? AND artifact_id=?",
                (str(project), str(artifact_id)),
            )
            return [FactVersion.model_validate(json.loads(row[0])) for row in await cur.fetchall()]

    async def replace_active_facts(
        self, project: ProjectId, artifact_id: ArtifactId, facts: list[FactVersion]
    ) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "DELETE FROM active_facts WHERE project=? AND artifact_id=?",
                (str(project), str(artifact_id)),
            )
            await db.executemany(
                "INSERT INTO active_facts(project,artifact_id,edge_uuid,fact_json) VALUES(?,?,?,?)",
                [(str(project), str(artifact_id), f.edge_uuid, f.model_dump_json()) for f in facts],
            )
            await db.commit()

    async def set_release_status(self, project: ProjectId, release_id: ReleaseId, status: str) -> None:
        if status not in {"pending", "indexing", "ready", "failed"}:
            raise ValueError(status)
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "UPDATE releases SET status=? WHERE project=? AND release_id=?",
                (status, str(project), str(release_id)),
            )
            await db.commit()
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/revisions -v
uv run mypy src/know_your_project/revisions
git add src/know_your_project/revisions tests/unit/revisions
git commit -m "feat: add deterministic release revision engine"
```

---

### Task 4: Add deterministic artifact parsers

**Files:**
- Create: `src/know_your_project/extraction/models.py`
- Create: `src/know_your_project/extraction/parsers/base.py`
- Create: `src/know_your_project/extraction/parsers/source.py`
- Create: `src/know_your_project/extraction/parsers/html.py`
- Create: `src/know_your_project/extraction/parsers/document.py`
- Create: `src/know_your_project/extraction/parsers/work_item.py`
- Test: `tests/unit/extraction/parsers/test_parsers.py`

**Interfaces:**
- Consumes: `SourceArtifact`.
- Produces: `ParsedArtifact` with deterministic structure and bounded internal semantic text. Parser output remains private.

- [ ] **Step 1: Define parsed types**

```python
# src/know_your_project/extraction/models.py
from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import Provenance


class ParsedSymbol(BaseModel):
    kind: str
    name: str


class ParsedArtifact(BaseModel):
    title: str
    semantic_text: str = Field(max_length=30000)
    symbols: list[ParsedSymbol] = Field(default_factory=list)
    provenance: Provenance
```

```python
# src/know_your_project/extraction/parsers/base.py
from typing import Protocol
from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class ArtifactParser(Protocol):
    def supports(self, artifact: SourceArtifact) -> bool: ...
    def parse(self, artifact: SourceArtifact) -> ParsedArtifact: ...
```

- [ ] **Step 2: Test code/HTML/work-item redaction boundaries**

```python
# tests/unit/extraction/parsers/test_parsers.py
from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.parsers.html import HtmlParser
from know_your_project.extraction.parsers.source import TreeSitterSourceParser


def artifact(kind: str, path: str, content: str) -> SourceArtifact:
    return SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId(path), kind=kind,
        revision="1", content=content, observed_at=datetime.now(UTC), path=path,
    )


def test_source_parser_finds_symbols_without_exposing_ast() -> None:
    parsed = TreeSitterSourceParser().parse(artifact(
        "source", "PaymentService.cs",
        "public class PaymentService { public void RetryPayment() { Retry(); } }",
    ))
    assert {s.name for s in parsed.symbols} >= {"PaymentService", "RetryPayment"}
    assert "syntax_tree" not in parsed.model_dump()


def test_html_parser_returns_semantics_not_markup() -> None:
    parsed = HtmlParser().parse(artifact(
        "html", "retry.html",
        '<form><label>Amount</label><input name="amount"><button>Retry Payment</button></form>',
    ))
    assert "Retry Payment" in parsed.semantic_text
    assert "<form" not in parsed.semantic_text
```

- [ ] **Step 3: Implement Tree-sitter parser**

```python
# src/know_your_project/extraction/parsers/source.py
from tree_sitter_language_pack import get_parser

from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact, ParsedSymbol

_LANGUAGE = {
    ".cs": "c_sharp", ".py": "python", ".ts": "typescript", ".tsx": "tsx",
    ".js": "javascript", ".java": "java", ".go": "go", ".rs": "rust",
}
_SYMBOL_TYPES = {
    "class_declaration": "class", "interface_declaration": "interface",
    "method_declaration": "method", "function_definition": "function",
    "function_declaration": "function",
}


class TreeSitterSourceParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return bool(artifact.path and any(artifact.path.endswith(s) for s in _LANGUAGE))

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        if artifact.path is None:
            raise ValueError("source path required")
        suffix = next(s for s in _LANGUAGE if artifact.path.endswith(s))
        raw = artifact.content.encode("utf-8")
        tree = get_parser(_LANGUAGE[suffix]).parse(raw)
        symbols: list[ParsedSymbol] = []
        stack = [tree.root_node]
        while stack:
            node = stack.pop()
            kind = _SYMBOL_TYPES.get(node.type)
            if kind:
                name = node.child_by_field_name("name")
                if name:
                    symbols.append(ParsedSymbol(
                        kind=kind, name=raw[name.start_byte:name.end_byte].decode("utf-8")
                    ))
            stack.extend(node.children)
        # Internal-only context: symbol inventory plus a bounded source window for behavior extraction.
        inventory = "\n".join(f"{s.kind}: {s.name}" for s in symbols)
        semantic_text = f"{inventory}\n\nSOURCE_WINDOW:\n{artifact.content[:20000]}"
        return ParsedArtifact(
            title=artifact.path, semantic_text=semantic_text, symbols=symbols,
            provenance=Provenance(
                source_kind="git", source_id=str(artifact.artifact_id),
                repository=artifact.repository, path=artifact.path, commit_sha=artifact.commit_sha,
            ),
        )
```

- [ ] **Step 4: Implement HTML/document/work-item parsers**

```python
# src/know_your_project/extraction/parsers/html.py
from bs4 import BeautifulSoup
from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class HtmlParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "html"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        soup = BeautifulSoup(artifact.content, "lxml")
        labels = [e.get_text(" ", strip=True) for e in soup.find_all("label")]
        fields = [e.get("name") or e.get("id") for e in soup.find_all(["input", "select", "textarea"])]
        actions = [e.get_text(" ", strip=True) for e in soup.find_all(["button", "a"]) if e.get_text(" ", strip=True)]
        text = "\n".join([
            *(f"label: {x}" for x in labels),
            *(f"field: {x}" for x in fields if x),
            *(f"action: {x}" for x in actions),
        ])
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id), semantic_text=text,
            provenance=Provenance(source_kind="html", source_id=str(artifact.artifact_id), path=artifact.path),
        )
```

```python
# src/know_your_project/extraction/parsers/document.py
import re
from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class DocumentParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "document"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        text = re.sub(r"\n{3,}", "\n\n", artifact.content).strip()[:30000]
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id), semantic_text=text,
            provenance=Provenance(source_kind="document", source_id=str(artifact.artifact_id), path=artifact.path),
        )
```

```python
# src/know_your_project/extraction/parsers/work_item.py
from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact


class WorkItemParser:
    def supports(self, artifact: SourceArtifact) -> bool:
        return artifact.kind == "work_item"

    def parse(self, artifact: SourceArtifact) -> ParsedArtifact:
        return ParsedArtifact(
            title=str(artifact.artifact_id), semantic_text=artifact.content[:30000],
            provenance=Provenance(source_kind="work_item", source_id=str(artifact.artifact_id)),
        )
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/extraction/parsers -v
uv run mypy src/know_your_project/extraction
git add src/know_your_project/extraction tests/unit/extraction
git commit -m "feat: add deterministic artifact parsers"
```

---

### Task 5: Add strict local semantic extraction

**Files:**
- Create: `src/know_your_project/extraction/llm.py`
- Create: `src/know_your_project/extraction/service.py`
- Test: `tests/unit/extraction/test_llm.py`
- Test: `tests/unit/extraction/test_service.py`

**Interfaces:**
- Consumes: `ParsedArtifact` private context.
- Produces: validated `FactCandidate` values only. No free-form model response reaches persistence.

- [ ] **Step 1: Write strict JSON extraction test**

```python
# tests/unit/extraction/test_llm.py
import httpx
import respx

from know_your_project.domain.artifacts import Provenance
from know_your_project.extraction.llm import LocalKnowledgeExtractor
from know_your_project.extraction.models import ParsedArtifact


@respx.mock
async def test_extractor_validates_fact_schema() -> None:
    respx.post("http://llm/v1/chat/completions").mock(return_value=httpx.Response(200, json={
        "choices": [{"message": {"content":
            '{"facts":[{"subject":"PaymentRetry","predicate":"behavior",'
            '"value":"Retries failed payments","confidence":0.9}]}'
        }}]
    }))
    extractor = LocalKnowledgeExtractor(base_url="http://llm/v1", api_key="x", model="gpt-oss:20b")
    facts = await extractor.extract(ParsedArtifact(
        title="PaymentService.cs", semantic_text="method: RetryPayment",
        provenance=Provenance(source_kind="git", source_id="x"),
    ))
    assert facts[0].predicate == "behavior"
```

- [ ] **Step 2: Implement local OpenAI-compatible extractor**

```python
# src/know_your_project/extraction/llm.py
import json
import httpx
from pydantic import BaseModel, Field

from know_your_project.domain.artifacts import FactCandidate
from .models import ParsedArtifact


class _Fact(BaseModel):
    subject: str = Field(min_length=1)
    predicate: str = Field(min_length=1)
    value: str = Field(min_length=1, max_length=2000)
    object_ref: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class _Payload(BaseModel):
    facts: list[_Fact]


class LocalKnowledgeExtractor:
    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._url = base_url.rstrip("/") + "/chat/completions"
        self._key = api_key
        self._model = model

    async def extract(self, parsed: ParsedArtifact) -> list[FactCandidate]:
        instruction = (
            "Extract semantic project facts only. Do not quote or reproduce source code. "
            "Use stable subjects and predicates. Return JSON object {facts:[...]}; each fact has "
            "subject,predicate,value,object_ref,confidence. Values describe behavior, responsibility, "
            "requirement, dependency, screen semantics, or business rules."
        )
        async with httpx.AsyncClient(timeout=90) as client:
            response = await client.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model,
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "system", "content": instruction},
                                 {"role": "user", "content": f"{parsed.title}\n{parsed.semantic_text}"}],
                },
            )
            response.raise_for_status()
        payload = _Payload.model_validate(json.loads(response.json()["choices"][0]["message"]["content"]))
        return [FactCandidate(
            subject=f.subject, predicate=f.predicate, value=f.value,
            object_ref=f.object_ref, confidence=f.confidence, provenance=parsed.provenance,
        ) for f in payload.facts]
```

- [ ] **Step 3: Implement parser routing and ensure unsupported data is never sent to the LLM**

```python
# src/know_your_project/extraction/service.py
from know_your_project.domain.artifacts import FactCandidate, SourceArtifact
from .llm import LocalKnowledgeExtractor
from .parsers.base import ArtifactParser


class ExtractionService:
    def __init__(self, parsers: list[ArtifactParser], extractor: LocalKnowledgeExtractor) -> None:
        self._parsers = parsers
        self._extractor = extractor

    async def extract(self, artifact: SourceArtifact) -> list[FactCandidate]:
        parser = next((p for p in self._parsers if p.supports(artifact)), None)
        if parser is None:
            return []
        return await self._extractor.extract(parser.parse(artifact))
```

```python
# tests/unit/extraction/test_service.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.service import ExtractionService


async def test_unsupported_binary_is_not_sent_to_llm() -> None:
    extractor = AsyncMock()
    service = ExtractionService([], extractor)
    result = await service.extract(SourceArtifact(
        project_id=ProjectId("p"), artifact_id=ArtifactId("asset"), kind="source",
        revision="1", content="SECRET", observed_at=datetime.now(UTC), path="asset.bin",
    ))
    assert result == []
    extractor.extract.assert_not_called()
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/extraction -v
uv run mypy src/know_your_project/extraction
git add src/know_your_project/extraction tests/unit/extraction
git commit -m "feat: add local structured semantic extraction"
```

---

### Task 6: Implement the Azure DevOps read adapter

**Files:**
- Create: `src/know_your_project/ingestion/models.py`
- Create: `src/know_your_project/ingestion/azure_devops/client.py`
- Create: `src/know_your_project/ingestion/azure_devops/mapper.py`
- Test: `tests/unit/ingestion/azure_devops/test_client.py`
- Test: `tests/unit/ingestion/azure_devops/test_mapper.py`

**Interfaces:**
- Consumes: Azure DevOps REST API 7.1.
- Produces: refs, changed paths, file contents, and normalized work-item revisions.

- [ ] **Step 1: Define ingestion transport models**

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

- [ ] **Step 2: Write HTTP tests**

```python
# tests/unit/ingestion/azure_devops/test_client.py
import httpx
import respx

from know_your_project.ingestion.azure_devops.client import AzureDevOpsClient


@respx.mock
async def test_list_refs() -> None:
    respx.get("https://dev.azure.com/acme/P/_apis/git/repositories/r/refs").mock(
        return_value=httpx.Response(200, json={"value": [
            {"name": "refs/heads/main", "objectId": "a" * 40}
        ]})
    )
    client = AzureDevOpsClient(base_url="https://dev.azure.com/acme", project="P", token="t")
    refs = await client.list_refs("r")
    assert refs[0].object_id == "a" * 40
```

- [ ] **Step 3: Implement Git/work-item calls**

```python
# src/know_your_project/ingestion/azure_devops/client.py
import base64
import httpx

from know_your_project.ingestion.models import ChangedFile, GitRef


class AzureDevOpsClient:
    def __init__(self, *, base_url: str, project: str, token: str) -> None:
        self._root = f"{base_url.rstrip('/')}/{project}/_apis"
        encoded = base64.b64encode(f":{token}".encode()).decode()
        self._headers = {"Authorization": f"Basic {encoded}"}

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> dict:
        query = {"api-version": "7.1", **(params or {})}
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(f"{self._root}/{path}", params=query)
            response.raise_for_status()
            return response.json()

    async def list_refs(self, repository: str) -> list[GitRef]:
        body = await self._get_json(f"git/repositories/{repository}/refs")
        return [GitRef(name=x["name"], object_id=x["objectId"]) for x in body["value"]]

    async def changed_files(self, repository: str, base: str, target: str) -> list[ChangedFile]:
        body = await self._get_json(
            f"git/repositories/{repository}/diffs/commits",
            {"baseVersion": base, "targetVersion": target},
        )
        return [ChangedFile(path=x["item"]["path"], change_type=x["changeType"])
                for x in body.get("changes", [])]

    async def file_text(self, repository: str, path: str, version: str) -> str:
        async with httpx.AsyncClient(headers=self._headers, timeout=60) as client:
            response = await client.get(
                f"{self._root}/git/repositories/{repository}/items",
                params={"path": path, "versionDescriptor.version": version,
                        "includeContent": "true", "api-version": "7.1"},
            )
            response.raise_for_status()
            return response.text

    async def get_work_item(self, work_item_id: int) -> dict:
        return await self._get_json(f"wit/workitems/{work_item_id}", {"$expand": "relations"})
```

- [ ] **Step 4: Normalize a work item into a source artifact**

```python
# src/know_your_project/ingestion/azure_devops/mapper.py
from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId


def work_item_artifact(project_id: ProjectId, payload: dict) -> SourceArtifact:
    f = payload["fields"]
    content = "\n".join([
        f"type: {f.get('System.WorkItemType', '')}",
        f"title: {f.get('System.Title', '')}",
        f"state: {f.get('System.State', '')}",
        f"description: {f.get('System.Description', '')}",
        f"acceptance criteria: {f.get('Microsoft.VSTS.Common.AcceptanceCriteria', '')}",
    ])
    return SourceArtifact(
        project_id=project_id,
        artifact_id=ArtifactId(f"work-item:{payload['id']}"),
        kind="work_item",
        revision=str(payload["rev"]),
        content=content,
        observed_at=datetime.now(UTC),
    )
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/ingestion/azure_devops -v
uv run mypy src/know_your_project/ingestion
git add src/know_your_project/ingestion tests/unit/ingestion
git commit -m "feat: add Azure DevOps read adapter"
```

---

### Task 7: Implement Graphiti persistence with explicit temporal mutations

**Files:**
- Create: `src/know_your_project/knowledge/dto.py`
- Create: `src/know_your_project/knowledge/interfaces.py`
- Create: `src/know_your_project/knowledge/graphiti/client.py`
- Create: `src/know_your_project/knowledge/graphiti/ids.py`
- Create: `src/know_your_project/knowledge/graphiti/repository.py`
- Test: `tests/unit/knowledge/graphiti/test_repository.py`
- Test: `tests/integration/knowledge/test_graphiti_neo4j.py`

**Interfaces:**
- Consumes: explicit `GraphMutation` list.
- Produces: graph persistence and safe search results.
- Critical rule: this adapter never calls `Graphiti.add_episode()` or `Graphiti.add_triplet()` for canonical facts.

- [ ] **Step 1: Define repository contract and safe DTO**

```python
# src/know_your_project/knowledge/dto.py
from datetime import datetime
from pydantic import BaseModel, Field


class SafeProvenance(BaseModel):
    source_kind: str
    source_id: str
    release_id: str | None = None


class KnowledgeResult(BaseModel):
    id: str
    kind: str = "fact"
    summary: str
    score: float | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    provenance: list[SafeProvenance] = Field(default_factory=list)
```

```python
# src/know_your_project/knowledge/interfaces.py
from typing import Protocol

from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.revisions.models import GraphMutation
from .dto import KnowledgeResult


class KnowledgeRepository(Protocol):
    async def apply(self, project_id: str, mutations: list[GraphMutation]) -> None: ...
    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
```

- [ ] **Step 2: Implement deterministic entity IDs**

```python
# src/know_your_project/knowledge/graphiti/ids.py
from uuid import NAMESPACE_URL, uuid5


def entity_uuid(project: str, canonical_name: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"kyp:{project}:entity:{canonical_name.strip().casefold()}"))
```

- [ ] **Step 3: Construct Graphiti using only local model/embedding endpoints**

```python
# src/know_your_project/knowledge/graphiti/client.py
from graphiti_core import Graphiti
from graphiti_core.cross_encoder.openai_reranker_client import OpenAIRerankerClient
from graphiti_core.embedder.openai import OpenAIEmbedder, OpenAIEmbedderConfig
from graphiti_core.llm_client.config import LLMConfig
from graphiti_core.llm_client.openai_generic_client import OpenAIGenericClient


def create_graphiti(*, uri: str, user: str, password: str, base_url: str,
                     api_key: str, llm_model: str, embedding_model: str) -> Graphiti:
    llm_config = LLMConfig(api_key=api_key, model=llm_model, small_model=llm_model, base_url=base_url)
    llm = OpenAIGenericClient(config=llm_config)
    embedder = OpenAIEmbedder(config=OpenAIEmbedderConfig(
        api_key=api_key, embedding_model=embedding_model, base_url=base_url,
    ))
    return Graphiti(
        uri, user, password,
        llm_client=llm,
        embedder=embedder,
        cross_encoder=OpenAIRerankerClient(client=llm, config=llm_config),
        store_raw_episode_content=False,
    )
```

- [ ] **Step 4: Write persistence test proving explicit invalidation**

```python
# tests/unit/knowledge/graphiti/test_repository.py
from datetime import UTC, datetime
from unittest.mock import AsyncMock

from know_your_project.knowledge.graphiti.repository import GraphitiKnowledgeRepository
from know_your_project.revisions.models import InvalidateFact


async def test_invalidation_updates_exact_edge_only() -> None:
    graphiti = AsyncMock()
    graphiti.driver = object()
    repo = GraphitiKnowledgeRepository(graphiti)
    edge = AsyncMock()
    edge.invalid_at = None
    edge.expired_at = None
    repo._get_edge = AsyncMock(return_value=edge)  # type: ignore[method-assign]
    at = datetime(2026, 9, 2, tzinfo=UTC)
    await repo.apply("payments", [InvalidateFact(edge_uuid="edge-1", invalid_at=at)])
    assert edge.invalid_at == at
    edge.save.assert_awaited_once()
```

- [ ] **Step 5: Implement direct node/edge persistence**

```python
# src/know_your_project/knowledge/graphiti/repository.py
from datetime import UTC
from typing import Any

from graphiti_core.edges import EntityEdge
from graphiti_core.helpers import utc_now
from graphiti_core.nodes import EntityNode

from know_your_project.domain.queries import KnowledgeQuery
from know_your_project.revisions.models import GraphMutation, InvalidateFact, UpsertFact
from .ids import entity_uuid


class GraphitiKnowledgeRepository:
    def __init__(self, graphiti: Any) -> None:
        self._graphiti = graphiti

    async def _get_edge(self, uuid: str) -> EntityEdge:
        return await EntityEdge.get_by_uuid(self._graphiti.driver, uuid)

    async def apply(self, project_id: str, mutations: list[GraphMutation]) -> None:
        for mutation in mutations:
            if isinstance(mutation, InvalidateFact):
                edge = await self._get_edge(mutation.edge_uuid)
                edge.invalid_at = mutation.invalid_at
                edge.expired_at = utc_now()
                await edge.save(self._graphiti.driver)
                continue

            if not isinstance(mutation, UpsertFact):
                raise TypeError(type(mutation))

            fact = mutation.fact
            target_name = fact.object_ref or fact.value
            source = EntityNode(
                uuid=entity_uuid(project_id, fact.subject), name=fact.subject,
                group_id=project_id, created_at=fact.valid_from,
            )
            target = EntityNode(
                uuid=entity_uuid(project_id, target_name), name=target_name,
                group_id=project_id, created_at=fact.valid_from,
            )
            await source.generate_name_embedding(self._graphiti.embedder)
            await target.generate_name_embedding(self._graphiti.embedder)
            await source.save(self._graphiti.driver)
            await target.save(self._graphiti.driver)

            edge = EntityEdge(
                uuid=fact.edge_uuid,
                source_node_uuid=source.uuid,
                target_node_uuid=target.uuid,
                name=fact.predicate.upper().replace(" ", "_"),
                group_id=project_id,
                fact=f"{fact.subject} {fact.predicate}: {fact.value}",
                created_at=fact.valid_from,
                valid_at=fact.valid_from,
                invalid_at=fact.valid_to,
                reference_time=fact.valid_from,
                attributes={
                    "artifact_id": str(fact.artifact_id),
                    "source_kind": fact.provenance.source_kind,
                    "source_id": fact.provenance.source_id,
                    "release_id": str(fact.provenance.release_id) if fact.provenance.release_id else "",
                    "confidence": fact.confidence,
                },
            )
            await edge.generate_embedding(self._graphiti.embedder)
            await edge.save(self._graphiti.driver)
```

`source.save`, `target.save`, and `edge.save` use deterministic UUIDs, so replaying the same mutation is idempotent. No Graphiti contradiction-resolution path participates.

- [ ] **Step 6: Add integration initialization test**

```python
# tests/integration/knowledge/test_graphiti_neo4j.py
import os
import pytest

from know_your_project.knowledge.graphiti.client import create_graphiti


@pytest.mark.skipif(os.getenv("RUN_GRAPHITI_INTEGRATION") != "1", reason="Graphiti integration disabled")
async def test_graphiti_indices_can_be_created() -> None:
    graph = create_graphiti(
        uri=os.environ["NEO4J_URI"], user=os.environ["NEO4J_USER"],
        password=os.environ["NEO4J_PASSWORD"], base_url=os.environ["LOCAL_LLM_BASE_URL"],
        api_key=os.environ["LOCAL_LLM_API_KEY"], llm_model=os.environ["LOCAL_LLM_MODEL"],
        embedding_model=os.environ["LOCAL_EMBEDDING_MODEL"],
    )
    try:
        await graph.build_indices_and_constraints()
    finally:
        await graph.close()
```

- [ ] **Step 7: Run tests and commit**

```bash
uv run pytest tests/unit/knowledge -v
uv run mypy src/know_your_project/knowledge
git add src/know_your_project/knowledge tests/unit/knowledge tests/integration/knowledge
git commit -m "feat: persist explicit temporal facts through Graphiti"
```

---

### Task 8: Add temporal Graphiti search and release resolution

**Files:**
- Create: `src/know_your_project/knowledge/graphiti/temporal.py`
- Modify: `src/know_your_project/knowledge/graphiti/repository.py`
- Create: `src/know_your_project/revisions/queries.py`
- Test: `tests/unit/knowledge/graphiti/test_temporal.py`
- Test: `tests/unit/revisions/test_queries.py`

**Interfaces:**
- Repository search accepts only `KnowledgeQuery(text, project_id, as_of, limit)`.
- Release query service translates `release_id -> effective_at`; Graphiti never decides what a software release means.

- [ ] **Step 1: Test exact historical filter shape**

```python
# tests/unit/knowledge/graphiti/test_temporal.py
from datetime import UTC, datetime

from graphiti_core.search.search_filters import ComparisonOperator
from know_your_project.knowledge.graphiti.temporal import temporal_filters


def test_as_of_filter_includes_not_yet_invalidated_edges() -> None:
    at = datetime(2026, 9, 1, tzinfo=UTC)
    filters = temporal_filters(at)
    assert filters.valid_at[0][0].comparison_operator == ComparisonOperator.less_than_equal
    assert filters.invalid_at[0][0].comparison_operator == ComparisonOperator.greater_than
    assert filters.invalid_at[1][0].comparison_operator == ComparisonOperator.is_null
```

- [ ] **Step 2: Implement temporal filters**

```python
# src/know_your_project/knowledge/graphiti/temporal.py
from datetime import datetime
from graphiti_core.search.search_filters import ComparisonOperator, DateFilter, SearchFilters


def temporal_filters(as_of: datetime | None) -> SearchFilters:
    if as_of is None:
        return SearchFilters(invalid_at=[[
            DateFilter(comparison_operator=ComparisonOperator.is_null)
        ]])
    return SearchFilters(
        valid_at=[[
            DateFilter(date=as_of, comparison_operator=ComparisonOperator.less_than_equal)
        ]],
        invalid_at=[
            [DateFilter(date=as_of, comparison_operator=ComparisonOperator.greater_than)],
            [DateFilter(comparison_operator=ComparisonOperator.is_null)],
        ],
    )
```

- [ ] **Step 3: Complete Graphiti search projection**

Append this method to `GraphitiKnowledgeRepository`:

```python
from know_your_project.knowledge.dto import KnowledgeResult, SafeProvenance
from .temporal import temporal_filters

async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]:
    edges = await self._graphiti.search(
        query.text,
        group_ids=[str(query.project_id)],
        num_results=query.limit,
        search_filter=temporal_filters(query.as_of),
    )
    results: list[KnowledgeResult] = []
    for edge in edges:
        attrs = edge.attributes or {}
        results.append(KnowledgeResult(
            id=edge.uuid,
            summary=edge.fact,
            score=getattr(edge, "score", None),
            valid_from=edge.valid_at,
            valid_to=edge.invalid_at,
            provenance=[SafeProvenance(
                source_kind=str(attrs.get("source_kind", "unknown")),
                source_id=str(attrs.get("source_id", "unknown")),
                release_id=str(attrs["release_id"]) if attrs.get("release_id") else None,
            )],
        ))
    return results
```

No user-controlled node labels, edge types, property filters, or Cypher are accepted.

- [ ] **Step 4: Implement release-aware query service**

```python
# src/know_your_project/revisions/queries.py
from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import KnowledgeQuery, ReleaseComparisonQuery, ReleaseKnowledgeQuery


class ReleaseQueryService:
    def __init__(self, repository, revision_store) -> None:
        self._repository = repository
        self._store = revision_store

    async def search(self, query: ReleaseKnowledgeQuery):
        as_of = None
        if query.release_id is not None:
            release = await self._store.get_release(query.project_id, query.release_id)
            if release is None:
                raise KeyError(f"unknown release: {query.release_id}")
            as_of = release.effective_at
        return await self._repository.search(KnowledgeQuery(
            project_id=query.project_id, text=query.text, as_of=as_of, limit=query.limit,
        ))

    async def release_changes(self, project: ProjectId, release_id: ReleaseId):
        release = await self._store.get_release(project, release_id)
        if release is None:
            raise KeyError(f"unknown release: {release_id}")
        return await self._repository.search(KnowledgeQuery(
            project_id=project, text="changed introduced removed behavior",
            as_of=release.effective_at, limit=50,
        ))

    async def compare(self, query: ReleaseComparisonQuery):
        before = await self.search(ReleaseKnowledgeQuery(
            project_id=query.project_id, text=query.component or "feature behavior requirement",
            release_id=query.from_release, limit=50,
        ))
        after = await self.search(ReleaseKnowledgeQuery(
            project_id=query.project_id, text=query.component or "feature behavior requirement",
            release_id=query.to_release, limit=50,
        ))
        before_map = {r.summary: r for r in before}
        after_map = {r.summary: r for r in after}
        return {
            "from_release": str(query.from_release),
            "to_release": str(query.to_release),
            "removed": list(before_map.keys() - after_map.keys()),
            "added": list(after_map.keys() - before_map.keys()),
        }

    async def trace_work_item(self, project: ProjectId, work_item_id: WorkItemId, release_id: ReleaseId | None):
        return await self.search(ReleaseKnowledgeQuery(
            project_id=project, text=f"work-item:{int(work_item_id)} PBI-{int(work_item_id)}",
            release_id=release_id, limit=50,
        ))
```

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/knowledge/graphiti tests/unit/revisions -v
uv run mypy src
git add src/know_your_project/knowledge src/know_your_project/revisions tests/unit
git commit -m "feat: add release-aware temporal knowledge search"
```

---

### Task 9: Add checkpoints and transaction-ordered ingestion pipeline

**Files:**
- Create: `src/know_your_project/ingestion/checkpoints.py`
- Create: `src/know_your_project/ingestion/pipeline.py`
- Test: `tests/unit/ingestion/test_checkpoints.py`
- Test: `tests/unit/ingestion/test_pipeline.py`

**Interfaces:**
- Consumes: `SourceArtifact` batches and optional `Release`.
- Produces: extraction -> revision plan -> Graphiti mutation -> active-state persistence -> checkpoint advancement in that order.

- [ ] **Step 1: Implement checkpoint store**

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
                project TEXT NOT NULL, repository TEXT NOT NULL, ref TEXT NOT NULL,
                sha TEXT NOT NULL, PRIMARY KEY(project, repository, ref))
            """)
            await db.commit()

    async def get(self, project: str, repository: str, ref: str) -> str | None:
        async with aiosqlite.connect(self._path) as db:
            cur = await db.execute(
                "SELECT sha FROM checkpoints WHERE project=? AND repository=? AND ref=?",
                (project, repository, ref),
            )
            row = await cur.fetchone()
            return row[0] if row else None

    async def set(self, project: str, repository: str, ref: str, sha: str) -> None:
        async with aiosqlite.connect(self._path) as db:
            await db.execute(
                "INSERT INTO checkpoints VALUES(?,?,?,?) ON CONFLICT(project,repository,ref) DO UPDATE SET sha=excluded.sha",
                (project, repository, ref, sha),
            )
            await db.commit()
```

- [ ] **Step 2: Test failure ordering**

```python
# tests/unit/ingestion/test_pipeline.py
from unittest.mock import AsyncMock
import pytest

from know_your_project.ingestion.pipeline import IngestionPipeline


async def test_checkpoint_not_advanced_when_graph_write_fails() -> None:
    repository = AsyncMock()
    repository.apply.side_effect = RuntimeError("graph failed")
    pipeline = IngestionPipeline(
        extraction=AsyncMock(), revision_engine=AsyncMock(), revision_store=AsyncMock(),
        repository=repository, checkpoints=AsyncMock(),
    )
    with pytest.raises(RuntimeError):
        await pipeline.persist(project_id="p", repository_name="r", ref="main", sha="a" * 40,
                               artifacts=[], release=None)
    pipeline._checkpoints.set.assert_not_awaited()
```

- [ ] **Step 3: Implement ordered persistence**

```python
# src/know_your_project/ingestion/pipeline.py
from datetime import UTC, datetime

from know_your_project.domain.ids import ArtifactId, ProjectId


class IngestionPipeline:
    def __init__(self, *, extraction, revision_engine, revision_store, repository, checkpoints) -> None:
        self._extraction = extraction
        self._engine = revision_engine
        self._revision_store = revision_store
        self._repository = repository
        self._checkpoints = checkpoints

    async def persist(self, *, project_id: str, repository_name: str, ref: str, sha: str,
                      artifacts: list, release) -> None:
        project = ProjectId(project_id)
        effective_at = release.effective_at if release else datetime.now(UTC)
        all_plans = []
        for artifact in artifacts:
            candidates = await self._extraction.extract(artifact)
            if release:
                candidates = [c.model_copy(update={
                    "provenance": c.provenance.model_copy(update={"release_id": release.release_id})
                }) for c in candidates]
            previous = await self._revision_store.get_active_facts(project, artifact.artifact_id)
            plan = self._engine.plan(
                project_id=project, artifact_id=artifact.artifact_id,
                previous=previous, current=candidates, effective_at=effective_at,
            )
            all_plans.append((artifact.artifact_id, plan))

        for _, plan in all_plans:
            await self._repository.apply(project_id, plan.mutations)
        for artifact_id, plan in all_plans:
            await self._revision_store.replace_active_facts(project, artifact_id, plan.active_versions)
        await self._checkpoints.set(project_id, repository_name, ref, sha)
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/ingestion/test_checkpoints.py tests/unit/ingestion/test_pipeline.py -v
git add src/know_your_project/ingestion tests/unit/ingestion
git commit -m "feat: add checkpointed ingestion pipeline"
```

---

### Task 10: Build Git, document, HTML, and work-item sync planning

**Files:**
- Create: `src/know_your_project/ingestion/reconciliation.py`
- Modify: `src/know_your_project/ingestion/azure_devops/client.py`
- Test: `tests/unit/ingestion/test_reconciliation.py`

**Interfaces:**
- Consumes: tracked repository/ref and Azure DevOps events/current refs.
- Produces: changed `SourceArtifact`s. MVP documents are text/Markdown/HTML files stored in synchronized Azure DevOps Git repos; PBIs are synchronized separately.

- [ ] **Step 1: Test file classification and incremental fetch**

```python
# tests/unit/ingestion/test_reconciliation.py
from unittest.mock import AsyncMock

from know_your_project.ingestion.reconciliation import ReconciliationService


async def test_markdown_and_html_are_classified_before_pipeline() -> None:
    client = AsyncMock()
    client.changed_files.return_value = [
        type("C", (), {"path": "/docs/spec.md", "change_type": "edit"})(),
        type("C", (), {"path": "/mockups/retry.html", "change_type": "edit"})(),
    ]
    client.file_text.side_effect = ["# Spec", "<button>Retry</button>"]
    svc = ReconciliationService(client=client, checkpoints=AsyncMock(), pipeline=AsyncMock())
    artifacts = await svc.collect_git_artifacts("p", "r", "main", "a" * 40, "b" * 40)
    assert [a.kind for a in artifacts] == ["document", "html"]
```

- [ ] **Step 2: Implement Git artifact collection**

```python
# src/know_your_project/ingestion/reconciliation.py
from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId


_DOC_SUFFIXES = (".md", ".txt", ".rst")
_HTML_SUFFIXES = (".html", ".htm")
_SOURCE_SUFFIXES = (".cs", ".py", ".ts", ".tsx", ".js", ".java", ".go", ".rs")


class ReconciliationService:
    def __init__(self, *, client, checkpoints, pipeline) -> None:
        self._client = client
        self._checkpoints = checkpoints
        self._pipeline = pipeline

    async def collect_git_artifacts(self, project: str, repository: str, ref: str,
                                    old_sha: str, new_sha: str) -> list[SourceArtifact]:
        items = await self._client.changed_files(repository, old_sha, new_sha)
        output = []
        for item in items:
            if item.change_type.casefold() == "delete":
                continue
            if item.path.endswith(_DOC_SUFFIXES): kind = "document"
            elif item.path.endswith(_HTML_SUFFIXES): kind = "html"
            elif item.path.endswith(_SOURCE_SUFFIXES): kind = "source"
            else: continue
            output.append(SourceArtifact(
                project_id=ProjectId(project),
                artifact_id=ArtifactId(f"git:{repository}:{item.path}"),
                kind=kind,
                revision=new_sha,
                content=await self._client.file_text(repository, item.path, new_sha),
                observed_at=datetime.now(UTC), path=item.path,
                repository=repository, commit_sha=new_sha,
            ))
        return output
```

- [ ] **Step 3: Add work-item synchronization entrypoint**

Extend `ReconciliationService`:

```python
from know_your_project.ingestion.azure_devops.mapper import work_item_artifact

async def sync_work_item(self, project: str, work_item_id: int) -> SourceArtifact:
    payload = await self._client.get_work_item(work_item_id)
    return work_item_artifact(ProjectId(project), payload)
```

- [ ] **Step 4: Run tests and commit**

```bash
uv run pytest tests/unit/ingestion -v
uv run mypy src/know_your_project/ingestion
git add src/know_your_project/ingestion tests/unit/ingestion
git commit -m "feat: reconcile code PBIs documents and mockups"
```

---

### Task 11: Add project authorization and explicit safe projection

**Files:**
- Create: `src/know_your_project/security/principal.py`
- Create: `src/know_your_project/security/authorization.py`
- Create: `src/know_your_project/security/projection.py`
- Test: `tests/unit/security/test_security.py`

**Interfaces:**
- Consumes: validated JWT claims and `KnowledgeResult`.
- Produces: project-scoped principal and an allowlisted MCP representation.

- [ ] **Step 1: Write deny-by-default tests**

```python
# tests/unit/security/test_security.py
import pytest
from know_your_project.domain.ids import ProjectId
from know_your_project.knowledge.dto import KnowledgeResult
from know_your_project.security.authorization import AuthorizationError, AuthorizationService
from know_your_project.security.principal import Principal
from know_your_project.security.projection import project_result


def test_project_access_denied_by_default() -> None:
    with pytest.raises(AuthorizationError):
        AuthorizationService().require_project(
            Principal(subject="alice", projects={ProjectId("a")}), ProjectId("b")
        )


def test_projection_is_allowlist_only() -> None:
    value = project_result(KnowledgeResult(id="x", summary="semantic behavior"))
    assert set(value) == {"id", "kind", "summary", "score", "valid_from", "valid_to", "provenance"}
```

- [ ] **Step 2: Implement principal, claim parsing, and authorization**

```python
# src/know_your_project/security/principal.py
from pydantic import BaseModel
from know_your_project.domain.ids import ProjectId


class Principal(BaseModel):
    subject: str
    projects: set[ProjectId]


def principal_from_claims(claims: dict) -> Principal:
    subject = str(claims.get("sub") or "")
    projects = claims.get("projects") or []
    if not subject:
        raise PermissionError("missing subject")
    if not isinstance(projects, list):
        raise PermissionError("projects claim must be a list")
    return Principal(subject=subject, projects={ProjectId(str(p)) for p in projects})
```

```python
# src/know_your_project/security/authorization.py
from know_your_project.domain.ids import ProjectId
from .principal import Principal


class AuthorizationError(PermissionError):
    pass


class AuthorizationService:
    def require_project(self, principal: Principal, project: ProjectId) -> None:
        if project not in principal.projects:
            raise AuthorizationError(f"project access denied: {project}")
```

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

- [ ] **Step 3: Run tests and commit**

```bash
uv run pytest tests/unit/security -v
git add src/know_your_project/security tests/unit/security
git commit -m "feat: enforce project-scoped safe knowledge projection"
```

---

### Task 12: Expose exactly seven read-only MCP tools with JWT identity

**Files:**
- Create: `src/know_your_project/mcp/tools.py`
- Create: `src/know_your_project/mcp/server.py`
- Test: `tests/contract/mcp/test_tools.py`

**Interfaces:**
- Consumes: `ReleaseQueryService`, JWT token claims, authorization.
- Produces exactly: `search_project_knowledge`, `get_feature`, `get_component`, `get_release_changes`, `compare_releases`, `trace_work_item`, `get_screen_spec`.

- [ ] **Step 1: Implement authenticated principal resolution from FastMCP request context**

```python
# src/know_your_project/mcp/tools.py
from fastmcp.server.dependencies import get_access_token

from know_your_project.domain.ids import ProjectId, ReleaseId, WorkItemId
from know_your_project.domain.queries import ReleaseComparisonQuery, ReleaseKnowledgeQuery
from know_your_project.security.principal import principal_from_claims
from know_your_project.security.projection import project_result


class KnowledgeTools:
    def __init__(self, *, revisions, authorization) -> None:
        self._revisions = revisions
        self._authorization = authorization

    def _principal(self):
        token = get_access_token()
        if token is None:
            raise PermissionError("authentication required")
        return principal_from_claims(token.claims)

    def _authorize(self, project: str) -> ProjectId:
        project_id = ProjectId(project)
        self._authorization.require_project(self._principal(), project_id)
        return project_id

    async def search_project_knowledge(self, query: str, project: str, release: str | None = None):
        project_id = self._authorize(project)
        results = await self._revisions.search(ReleaseKnowledgeQuery(
            project_id=project_id, text=query,
            release_id=ReleaseId(release) if release else None,
        ))
        return [project_result(r) for r in results]

    async def get_feature(self, name: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"feature {name}", project, release)

    async def get_component(self, name: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"component {name}", project, release)

    async def get_screen_spec(self, screen: str, project: str, release: str | None = None):
        return await self.search_project_knowledge(f"screen {screen}", project, release)

    async def get_release_changes(self, release: str, project: str):
        project_id = self._authorize(project)
        results = await self._revisions.release_changes(project_id, ReleaseId(release))
        return [project_result(r) for r in results]

    async def compare_releases(self, from_release: str, to_release: str, project: str,
                               component: str | None = None):
        project_id = self._authorize(project)
        return await self._revisions.compare(ReleaseComparisonQuery(
            project_id=project_id, from_release=ReleaseId(from_release),
            to_release=ReleaseId(to_release), component=component,
        ))

    async def trace_work_item(self, work_item_id: int, project: str, release: str | None = None):
        project_id = self._authorize(project)
        results = await self._revisions.trace_work_item(
            project_id, WorkItemId(work_item_id), ReleaseId(release) if release else None
        )
        return [project_result(r) for r in results]
```

- [ ] **Step 2: Register only allowed tools and JWT verification**

```python
# src/know_your_project/mcp/server.py
from fastmcp import FastMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier
from mcp.types import ToolAnnotations


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
```

- [ ] **Step 3: Contract-test tool inventory and source-leak boundary**

```python
# tests/contract/mcp/test_tools.py
import inspect

from know_your_project.mcp.tools import KnowledgeTools


def test_public_tool_methods_are_exact_allowlist() -> None:
    public = {name for name, fn in inspect.getmembers(KnowledgeTools, inspect.iscoroutinefunction)
              if not name.startswith("_")}
    assert public == {
        "search_project_knowledge", "get_feature", "get_component",
        "get_release_changes", "compare_releases", "trace_work_item", "get_screen_spec",
    }


def test_no_source_or_graph_admin_tool_name_exists() -> None:
    names = " ".join(dir(KnowledgeTools)).lower()
    for forbidden in ["cypher", "source_file", "raw_episode", "graph_dump", "mutate"]:
        assert forbidden not in names
```

- [ ] **Step 4: Run contract tests and commit**

```bash
uv run pytest tests/contract/mcp -v
uv run mypy src/know_your_project/mcp
git add src/know_your_project/mcp tests/contract/mcp
git commit -m "feat: expose restricted authenticated MCP tools"
```

---

### Task 13: Add authenticated Azure DevOps webhook handling and missed-event reconciliation

**Files:**
- Create: `src/know_your_project/ingestion/webhooks.py`
- Modify: `src/know_your_project/ingestion/reconciliation.py`
- Modify: `src/know_your_project/mcp/server.py`
- Test: `tests/unit/ingestion/test_webhooks.py`
- Test: `tests/unit/ingestion/test_ref_reconciliation.py`

**Interfaces:**
- Webhook route is HTTP-only, not an MCP tool.
- Webhook uses a dedicated shared secret and does not trust MCP JWT identity.

- [ ] **Step 1: Implement push-event parser and constant-time secret check**

```python
# src/know_your_project/ingestion/webhooks.py
import hmac
from pydantic import BaseModel


class PushEvent(BaseModel):
    repository: str
    ref: str
    old_sha: str
    new_sha: str


def verify_webhook_secret(actual: str | None, expected: str) -> None:
    if actual is None or not hmac.compare_digest(actual, expected):
        raise PermissionError("invalid webhook secret")


def parse_push_event(payload: dict) -> PushEvent:
    resource = payload["resource"]
    update = resource["refUpdates"][0]
    return PushEvent(
        repository=resource["repository"]["id"], ref=update["name"],
        old_sha=update["oldObjectId"], new_sha=update["newObjectId"],
    )
```

- [ ] **Step 2: Add webhook tests**

```python
# tests/unit/ingestion/test_webhooks.py
import pytest
from know_your_project.ingestion.webhooks import parse_push_event, verify_webhook_secret


def test_bad_secret_is_rejected() -> None:
    with pytest.raises(PermissionError):
        verify_webhook_secret("wrong", "expected")


def test_push_event_extracts_ref() -> None:
    event = parse_push_event({"resource": {
        "repository": {"id": "repo"},
        "refUpdates": [{"name": "refs/heads/main", "oldObjectId": "a" * 40, "newObjectId": "b" * 40}],
    }})
    assert event.new_sha == "b" * 40
```

- [ ] **Step 3: Add HTTP route without registering an MCP tool**

```python
# inside create_mcp() after tool registration
from starlette.requests import Request
from starlette.responses import JSONResponse
from know_your_project.ingestion.webhooks import parse_push_event, verify_webhook_secret


@mcp.custom_route("/hooks/azure-devops", methods=["POST"])
async def azure_devops_hook(request: Request) -> JSONResponse:
    verify_webhook_secret(request.headers.get("x-kyp-webhook-secret"), webhook_secret)
    event = parse_push_event(await request.json())
    await webhook_handler.handle_push(event)
    return JSONResponse({"accepted": True}, status_code=202)
```

Update `create_mcp` signature to receive `webhook_secret: str` and `webhook_handler`.

- [ ] **Step 4: Implement scheduled ref reconciliation**

Add to `ReconciliationService`:

```python
async def reconcile_refs(self, project: str, repository: str, tracked_refs: set[str]) -> None:
    for ref in await self._client.list_refs(repository):
        if ref.name not in tracked_refs:
            continue
        known = await self._checkpoints.get(project, repository, ref.name)
        if known != ref.object_id:
            await self.sync_ref(project, repository, ref.name, known, ref.object_id)
```

`sync_ref` calls `collect_git_artifacts`, resolves release/tag context when present, calls `pipeline.persist`, and therefore advances the checkpoint only after graph/state persistence.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/ingestion -v
git add src/know_your_project/ingestion src/know_your_project/mcp/server.py tests/unit/ingestion
git commit -m "feat: add webhook and reconciliation synchronization"
```

---

### Task 14: Add typed configuration, safe logging, health, and composition root

**Files:**
- Create: `src/know_your_project/settings.py`
- Create: `src/know_your_project/infrastructure/logging.py`
- Create: `src/know_your_project/app.py`
- Modify: `src/know_your_project/mcp/server.py`
- Test: `tests/unit/test_settings.py`
- Test: `tests/contract/mcp/test_health.py`

**Interfaces:**
- Produces one composition root that wires local LLM, Graphiti, Azure DevOps, revision state, security, and MCP.

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
    azdo_webhook_secret: str
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
    checkpoint_db: str = "./data/state.db"
```

- [ ] **Step 2: Implement audit logger that refuses sensitive payload keys**

```python
# src/know_your_project/infrastructure/logging.py
import json
import logging

logger = logging.getLogger("know_your_project")
_FORBIDDEN = {"content", "source_content", "episode_body", "token", "password", "azdo_token"}


def audit(event: str, **fields: object) -> None:
    bad = _FORBIDDEN.intersection(fields)
    if bad:
        raise ValueError(f"sensitive audit fields: {sorted(bad)}")
    logger.info(json.dumps({"event": event, **fields}, default=str, sort_keys=True))
```

- [ ] **Step 3: Add health route**

```python
# inside create_mcp()
from starlette.requests import Request
from starlette.responses import JSONResponse

@mcp.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "healthy", "service": "know-your-project"})
```

- [ ] **Step 4: Wire the application composition root**

`src/know_your_project/app.py` constructs exactly one instance of each dependency: settings, SQLite stores, Azure client, parsers, local extractor, revision engine, Graphiti client/repository, release query service, authorization service, tools, webhook handler, and FastMCP server. Initialization calls `revision_store.initialize()`, `checkpoint_store.initialize()`, and `graphiti.build_indices_and_constraints()` before serving. Shutdown calls `graphiti.close()`.

Use concrete imports from Tasks 1-13; no module outside this composition root and `knowledge/graphiti/` imports Graphiti.

- [ ] **Step 5: Run tests and commit**

```bash
uv run pytest tests/unit/test_settings.py tests/contract/mcp/test_health.py -v
uv run ruff check .
uv run mypy src
git add src/know_your_project tests/unit/test_settings.py tests/contract/mcp/test_health.py
git commit -m "feat: wire runtime configuration health and auditing"
```

---

### Task 15: Add self-hosted deployment documentation and containers

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Create: `README.md`
- Test: `tests/integration/test_runtime_config.py`

**Interfaces:**
- Neo4j remains private; only the application HTTP/MCP port is intended for team access.
- Local model endpoint is provided separately by Ollama/vLLM and configured through environment variables.

- [ ] **Step 1: Add application container**

```dockerfile
# Dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev
CMD ["uv", "run", "python", "-m", "know_your_project.app"]
```

- [ ] **Step 2: Add Neo4j + application compose stack**

```yaml
# docker-compose.yml
services:
  neo4j:
    image: neo4j:5.26-community
    environment:
      NEO4J_AUTH: neo4j/local-development-password
    volumes:
      - neo4j-data:/data
    expose:
      - "7687"

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

- [ ] **Step 3: Document security boundary and startup**

`README.md` must state verbatim:

```markdown
## Security boundary

MCP exposes semantic project knowledge only. It does not expose source files, source snippets,
raw Graphiti episodes, arbitrary graph queries, Cypher, Azure DevOps credentials, or raw parser output.

Graphiti and Neo4j are private infrastructure. MCP clients connect only to the Know Your Project
HTTP MCP endpoint. Semantic extraction and embeddings can run entirely on self-hosted model services.
```

Document:

```bash
cp .env.example .env
uv sync --all-groups
docker compose up -d neo4j
uv run pytest
uv run python -m know_your_project.app
```

- [ ] **Step 4: Validate deployment files and commit**

```bash
docker compose config
uv run pytest -q
uv run ruff check .
uv run mypy src
git add Dockerfile docker-compose.yml README.md tests/integration/test_runtime_config.py
git commit -m "docs: add self-hosted deployment"
```

---

### Task 16: Add release-history, confidentiality, isolation, and recovery acceptance tests

**Files:**
- Create: `tests/integration/conftest.py`
- Create: `tests/integration/test_release_history.py`
- Create: `tests/integration/test_no_source_leak.py`
- Create: `tests/integration/test_project_isolation.py`
- Create: `tests/integration/test_missed_webhook_recovery.py`
- Modify: `README.md`

**Interfaces:**
- Produces executable acceptance evidence for the four highest-risk requirements.

- [ ] **Step 1: Build an `AppHarness` fixture with in-memory/fake external boundaries**

```python
# tests/integration/conftest.py
import pytest
from know_your_project.domain.ids import ProjectId


class AppHarness:
    def __init__(self, services) -> None:
        self.services = services

    async def search(self, text: str, project: str, release: str | None = None):
        return await self.services.tools.search_project_knowledge(text, project, release)


@pytest.fixture
def app_harness(app_services) -> AppHarness:
    return AppHarness(app_services)
```

The `app_services` fixture uses a fake authenticated FastMCP access-token dependency, a real revision engine, SQLite temp databases, and an in-memory `KnowledgeRepository` implementing the same `apply/search` contract. A separate Graphiti integration test from Task 7 validates the actual Neo4j adapter.

- [ ] **Step 2: Verify historical truth**

```python
# tests/integration/test_release_history.py
async def test_old_release_remains_queryable_after_new_release(app_harness) -> None:
    await app_harness.services.index_release("v3.8.0", {"PaymentRetry.max_attempts": "3"})
    await app_harness.services.index_release("v4.2.0", {"PaymentRetry.max_attempts": "5"})
    old = await app_harness.search("PaymentRetry max attempts", "payments", "v3.8.0")
    new = await app_harness.search("PaymentRetry max attempts", "payments", "v4.2.0")
    assert any("3" in x["summary"] for x in old)
    assert any("5" in x["summary"] for x in new)
```

- [ ] **Step 3: Verify no raw source disclosure**

```python
# tests/integration/test_no_source_leak.py
async def test_source_text_never_appears_in_mcp_response(app_harness) -> None:
    raw = "private void HighlySensitiveImplementationSecret() {}"
    await app_harness.services.index_source("Secret.cs", raw)
    response = await app_harness.search("sensitive implementation", "payments")
    assert raw not in str(response)
    assert "HighlySensitiveImplementationSecret() {}" not in str(response)
```

- [ ] **Step 4: Verify project isolation**

```python
# tests/integration/test_project_isolation.py
import pytest


async def test_principal_cannot_query_ungranted_project(app_harness) -> None:
    app_harness.services.authenticate(projects={"project-a"})
    with pytest.raises(PermissionError):
        await app_harness.search("billing", "project-b")
```

- [ ] **Step 5: Verify reconciliation recovers a missed push**

```python
# tests/integration/test_missed_webhook_recovery.py
async def test_reconciliation_processes_changed_remote_ref(app_harness) -> None:
    await app_harness.services.set_checkpoint("repo", "refs/heads/main", "a" * 40)
    app_harness.services.set_remote_ref("repo", "refs/heads/main", "b" * 40)
    await app_harness.services.reconcile()
    assert await app_harness.services.get_checkpoint("repo", "refs/heads/main") == "b" * 40
```

- [ ] **Step 6: Run complete verification**

```bash
uv run pytest -q
uv run ruff check .
uv run mypy src
docker compose config
```

With Neo4j and the configured local model/embedding endpoint available:

```bash
RUN_GRAPHITI_INTEGRATION=1 uv run pytest tests/integration/knowledge -v
```

Expected: all enabled tests pass; no raw source content is returned; historical release queries return their own fact versions; project access is isolated; missed webhook state is reconciled.

- [ ] **Step 7: Update README implementation status and commit**

Document the seven MCP tools, supported source extensions, work-item ingestion, release semantics, Graphiti version floor, local-model configuration, webhook header name, and integration-test command.

```bash
git add tests/integration README.md
git commit -m "test: verify history confidentiality isolation and recovery"
```

---

## Review Gates

Review after these tasks before continuing:

1. **Task 3:** fact identity and supersession must be deterministic; unrelated facts cannot invalidate one another.
2. **Task 5:** local LLM emits validated semantic facts and does not intentionally copy raw code.
3. **Task 7:** Graphiti adapter must not call `add_episode` or `add_triplet` for canonical facts.
4. **Task 8:** historical search must use `valid_at <= as_of` and `(invalid_at > as_of OR invalid_at IS NULL)`.
5. **Task 9:** checkpoints cannot advance before graph + active-fact persistence.
6. **Task 12:** public MCP inventory is exactly seven read-only tools; no raw graph/source API exists.
7. **Task 16:** acceptance suite proves history, confidentiality, isolation, and missed-event recovery.

## Verified Graphiti/FastMCP Assumptions

- Graphiti `EntityEdge` stores `valid_at`, `invalid_at`, `expired_at`, `reference_time`, and attributes.
- `EntityEdge.get_by_uuid(driver, uuid)` plus `edge.save(driver)` can explicitly invalidate one exact persisted fact version.
- Graphiti `search()` accepts `group_ids`, `num_results`, and `SearchFilters`.
- `SearchFilters` supports `valid_at` and `invalid_at` comparisons including `<=`, `>`, and `IS NULL`, which is sufficient for release-time queries.
- Graphiti `add_triplet()` currently performs duplicate/contradiction resolution and broad invalidation candidate search; this project intentionally bypasses that path for canonical facts.
- `graphiti-core<=0.28.1` is affected by a Cypher-injection advisory; the dependency floor is 0.28.2.
- FastMCP exposes authenticated token claims through `fastmcp.server.dependencies.get_access_token()`.
- FastMCP supports `JWTVerifier`, read-only `ToolAnnotations`, and HTTP `custom_route` handlers.

## Definition of Done

The MVP is complete only when all conditions below are true:

- Azure DevOps Git refs can be incrementally synchronized and reconciled after missed service-hook events.
- Azure DevOps work items can enter the same semantic extraction pipeline.
- Repository source files, Markdown/text documents, and HTML mockups are classified and parsed before LLM extraction.
- A self-hosted OpenAI-compatible LLM produces validated semantic facts.
- Fact supersession is deterministic and artifact-scoped; Graphiti automatic contradiction invalidation is not used for canonical project facts.
- Graphiti persists deterministic project-scoped nodes/edges with local embeddings.
- Release identity retains exact tag, SHA, and effective timestamp.
- Current and historical knowledge queries apply correct temporal filters.
- MCP exposes exactly the approved seven read-only tools.
- JWT authentication and project authorization are enforced.
- MCP cannot return raw source, raw Graphiti episodes, arbitrary graph queries, Cypher, or credentials.
- Checkpoints advance only after persistence succeeds.
- Webhooks are protected independently from MCP authentication, and reconciliation recovers missed events.
- Neo4j/Graphiti remain private infrastructure in the documented deployment.
- `uv run pytest -q`, `uv run ruff check .`, `uv run mypy src`, and `docker compose config` pass.
