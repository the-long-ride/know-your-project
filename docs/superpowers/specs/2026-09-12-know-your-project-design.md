# Know Your Project — Architecture Design

**Status:** Approved design, implementation planning pending review
**Date:** 2026-09-12

## 1. Purpose

Know Your Project is a self-hosted project-knowledge service for software teams. It continuously synchronizes Azure DevOps project artifacts, derives structured knowledge from source code and project documentation, stores release-aware temporal knowledge, and exposes a restricted read-only MCP interface for Claude, Codex, and other AI agents.

The product answers questions such as:

- How does feature X work in the current release?
- What changed between releases 3.8.0 and 4.2.0?
- Which PBI introduced or changed this behavior?
- Which component implements a requirement?
- What screen or mockup corresponds to a PBI?
- What was the behavior of a component in a previous deployed release?

The service must answer these questions without exposing proprietary source code to MCP users.

## 2. Goals

1. Synchronize Azure DevOps Git, work items, documents, and HTML mockups.
2. Detect incremental changes from configured branches and tags.
3. Build structured knowledge from those changes using deterministic parsers plus a small self-hosted extraction LLM.
4. Preserve provenance from knowledge back to repository, commit, work item, document, and release.
5. Preserve historical truth across software releases instead of overwriting changed facts.
6. Use Graphiti as an internal temporal knowledge module.
7. Expose only approved project knowledge through a custom read-only MCP server.
8. Keep raw source code, repository credentials, raw graph operations, and ingestion internals inaccessible to MCP users.
9. Support fully self-hosted operation for teams that cannot send proprietary code to external model providers.

## 3. Non-goals

The initial system will not:

- act as a general chat application;
- replace Azure DevOps as the source of truth;
- expose arbitrary Cypher or raw Graphiti episode access to MCP users;
- expose source files or source snippets through MCP;
- generate production code for the synchronized project;
- provide a general-purpose document management UI;
- infer every source-code relationship using an LLM when a deterministic parser can provide it;
- create independent full graph copies for every software release.

## 4. Core Architecture

```text
Azure DevOps
├── Git repositories / refs / commits
├── PBIs, bugs, user stories, tasks
├── project documents
└── HTML mockups/templates
        │
        ▼
┌────────────────────────┐
│ Sync / Ingestion       │
│ Azure DevOps adapter   │
│ change detector        │
│ release resolver       │
└───────────┬────────────┘
            ▼
┌────────────────────────┐
│ Knowledge Extraction   │
│ code parsers           │
│ document parsers       │
│ HTML parser            │
│ local extraction LLM   │
└───────────┬────────────┘
            │ normalized facts
            ▼
┌────────────────────────┐
│ Knowledge Module       │
│ KnowledgeRepository    │
│ Graphiti adapter       │
│ temporal facts         │
│ provenance             │
└───────────┬────────────┘
            ▼
       Graph database
            │
            ▼
┌────────────────────────┐
│ Restricted MCP Server  │
│ search/retrieve only   │
└───────────┬────────────┘
            ▼
       Claude / Codex
```

The application is a modular monolith initially. Module boundaries must be strong enough that ingestion, extraction, Graphiti, and MCP can later be deployed independently without changing their domain contracts.

## 5. Module Boundaries

Target source layout:

```text
src/
├── domain/
├── ingestion/
├── extraction/
├── revisions/
├── knowledge/
│   ├── interfaces.py
│   └── graphiti/
├── mcp/
└── infrastructure/
```

### 5.1 `domain`

Owns project concepts and normalized models. It must not depend on Graphiti, Azure DevOps SDKs, FastAPI, MCP libraries, or a specific database.

Core concepts include:

- Project
- Repository
- Branch
- Commit
- Release
- WorkItem
- Document
- Mockup
- Component
- Feature
- Requirement
- Behavior
- BusinessRule
- Screen
- ApiCapability
- KnowledgeFact
- Provenance

### 5.2 `ingestion`

Owns synchronization from external project systems.

Responsibilities:

- Azure DevOps API access;
- service-hook/webhook handling;
- scheduled reconciliation;
- branch and tag observation;
- commit-range calculation;
- changed-file detection;
- work-item synchronization;
- document and HTML discovery;
- idempotency and checkpointing.

It produces source artifacts and change sets; it does not write directly to Graphiti.

### 5.3 `extraction`

Converts source artifacts into normalized knowledge candidates.

Responsibilities:

- deterministic source-code parsing;
- symbol, dependency, call, and route extraction;
- document normalization;
- HTML/DOM semantic extraction;
- local LLM extraction of behavior, feature, requirement, rule, and relationship candidates;
- structured-output validation;
- confidence and provenance assignment.

### 5.4 `revisions`

Owns software-version semantics.

Responsibilities:

- map Azure DevOps refs and tags to releases;
- identify the exact commit associated with a release;
- preserve branch-head state separately from deployed release state;
- determine which facts were introduced, changed, superseded, or removed;
- attach release identity and effective time to knowledge changes.

Graphiti provides temporal graph capabilities, but this module remains the authority for the meaning of `release`, `tag`, `branch`, and `deployment`.

### 5.5 `knowledge`

Owns the application-facing knowledge-store contract.

The rest of the application depends on `KnowledgeRepository`, not directly on Graphiti.

Initial conceptual interface:

```python
class KnowledgeRepository(Protocol):
    async def apply_changes(self, changes: KnowledgeChangeSet) -> None: ...
    async def search(self, query: KnowledgeQuery) -> list[KnowledgeResult]: ...
    async def get_feature(self, query: FeatureQuery) -> FeatureKnowledge | None: ...
    async def get_component(self, query: ComponentQuery) -> ComponentKnowledge | None: ...
    async def get_release_changes(self, release: ReleaseId) -> ReleaseChangeSet: ...
    async def compare_releases(self, query: ReleaseComparisonQuery) -> ReleaseComparison: ...
    async def trace_work_item(self, work_item_id: WorkItemId) -> WorkItemTrace: ...
```

Graphiti is implemented as an adapter under `knowledge/graphiti/`.

### 5.6 `mcp`

Owns the public AI-agent contract.

It may depend on domain/query contracts but must not expose Graphiti-specific primitives, graph-database query languages, source-code retrieval, or ingestion endpoints.

### 5.7 `infrastructure`

Owns configuration, authentication, logging, queues, database clients, health checks, and other technical adapters.

## 6. Azure DevOps Synchronization

Azure DevOps remains the authoritative project source.

### 6.1 Initial synchronization

For a configured project/repository:

1. resolve configured branches and release tags;
2. establish repository checkpoints;
3. backfill configured work-item types;
4. discover allowed project documents and HTML assets;
5. process the selected baseline release/current branch;
6. persist synchronization checkpoints only after successful knowledge application.

### 6.2 Incremental synchronization

The preferred mechanism is event-driven Azure DevOps service hooks plus periodic reconciliation.

For Git updates:

```text
previous observed SHA
       │
       ├── compare to new SHA
       ▼
changed paths
       │
       ▼
process changed/deleted artifacts only
```

The reconciliation job protects against missed webhook events and validates current refs against stored checkpoints.

### 6.3 Work items

Configurable work-item types include at minimum:

- Product Backlog Item / User Story;
- Bug;
- Task;
- Feature;
- Epic.

Normalized fields include ID, type, title, description, acceptance criteria, state, parent/child links, related work items, linked commits/PRs when available, tags, area/iteration path, and revision metadata.

## 7. Knowledge Extraction

### 7.1 Source code

Source code must be parsed deterministically before LLM processing.

Preferred parser strategy:

- Roslyn for .NET/C# when available;
- Tree-sitter for supported general-purpose languages;
- language-specific parsers may be added behind a common parser interface.

Deterministic extraction should cover as much as possible:

- files and symbols;
- classes/interfaces/functions/methods;
- imports/dependencies;
- calls and references where practical;
- API routes/controllers;
- configuration keys;
- database/model names where statically identifiable.

The extraction LLM receives minimized, structured context rather than an entire repository whenever possible.

### 7.2 LLM role

The local LLM is an ingestion tool, not the end-user answer model.

Its responsibilities are limited to structured extraction such as:

```json
{
  "entities": [],
  "relationships": [],
  "behaviors": [],
  "business_rules": [],
  "requirement_links": [],
  "change_summary": []
}
```

Claude/Codex performs user-facing synthesis after MCP retrieval.

The production configuration must support a self-hosted non-Chinese-origin model and local embeddings so proprietary source content does not need to leave the deployment environment.

### 7.3 Documents

Documents are normalized into sections with stable source references. Knowledge extraction must retain enough provenance to locate the originating document internally without exposing the raw document unless policy explicitly permits it.

### 7.4 HTML mockups/templates

HTML processing extracts semantic UI knowledge rather than raw markup for MCP exposure, including:

- screen/page identity;
- visible fields;
- actions;
- navigation targets;
- labels;
- forms;
- relationships to features and work items.

## 8. Confidentiality Boundary

The core security rule is:

> MCP users may receive semantic project knowledge, but not proprietary source code or unrestricted raw ingestion material.

### 8.1 Internal-only information

Never expose through the public MCP contract:

- complete source files;
- arbitrary source snippets;
- repository credentials/tokens;
- raw parser AST bodies;
- raw Graphiti episodes when they can contain source-derived text;
- unrestricted entity/edge dumps;
- arbitrary Cypher/graph queries;
- internal ingestion prompts;
- synchronization credentials and checkpoints.

### 8.2 Allowed knowledge

The MCP layer may return approved semantic information such as:

- feature descriptions;
- component responsibilities;
- behavior and business rules;
- requirements;
- API capabilities at semantic level;
- relationships among components/features/work items;
- release-change descriptions;
- UI screen semantics;
- provenance identifiers that do not expose confidential raw content.

### 8.3 Defense in depth

1. Graphiti/database are private network resources.
2. MCP server uses internal service credentials; users never receive graph credentials.
3. Public tools use explicit query handlers instead of arbitrary graph execution.
4. Result projection strips internal/raw fields.
5. Authorization is checked before each project query.
6. Audit logs record principal, project, tool, release scope, and result count without logging proprietary payloads by default.

## 9. Temporal and Release Model

Software history has two related dimensions:

1. **Temporal truth** — when a fact became valid or invalid.
2. **Release identity** — which project release/tag contains or changed that fact.

Both must be preserved.

Example:

```text
Release v3.8.0
└── PaymentRetry.maxAttempts = 3

Release v4.2.0
└── PaymentRetry.maxAttempts = 5
```

The old fact is not overwritten. Conceptually:

```text
PaymentRetry --max_attempts=3-->
    valid_from: v3.8.0
    invalidated_by: v4.2.0

PaymentRetry --max_attempts=5-->
    valid_from: v4.2.0
    invalidated_by: null
```

Explicit release entities are required even when Graphiti stores temporal timestamps.

Each release should retain at least:

- project ID;
- release/version name;
- source tag when applicable;
- resolved commit SHA;
- branch/ref source;
- observed/deployed timestamp when available;
- predecessor release when known.

### 9.1 Current branch state

Branch state is not treated as a release.

The system may represent:

```text
main@<sha>
develop@<sha>
release:v4.2.0@<sha>
```

MCP queries default to the configured current production release unless the caller explicitly requests branch/current-development context.

### 9.2 Deletions/removals

Removed behaviors and components must be invalidated/superseded, not silently deleted from history. Physical cleanup is a separate retention concern.

## 10. Graphiti Integration

Graphiti is an internal module implementing `KnowledgeRepository`.

Graphiti responsibilities:

- temporal entity/relationship storage;
- incremental knowledge updates;
- provenance relationships;
- semantic/hybrid retrieval supported by the selected backend;
- historical fact preservation.

Graphiti does not own:

- Azure DevOps synchronization;
- software release semantics;
- user authentication;
- MCP authorization;
- public MCP schemas;
- source-code parsing;
- source-disclosure policy.

The adapter must translate domain knowledge changes into Graphiti operations and translate Graphiti query results back into safe domain DTOs.

No application module outside `knowledge/graphiti/` may import Graphiti-specific classes except composition/bootstrap code.

## 11. MCP Contract

Initial public tools:

```text
search_project_knowledge(query, release?, project?)
get_feature(name, release?, project?)
get_component(name, release?, project?)
get_release_changes(release, project?)
compare_releases(from_release, to_release, component?, project?)
trace_work_item(work_item_id, release?, project?)
get_screen_spec(screen, release?, project?)
```

All tools are read-only.

### 11.1 Search behavior

`search_project_knowledge` returns ranked semantic knowledge records with stable identifiers, type, summary/facts, release scope, and safe provenance references.

It does not return arbitrary raw chunks from source code.

### 11.2 Agent responsibility

The MCP response is evidence/context, not a final natural-language answer. Claude/Codex is responsible for synthesis, explanation, and conversational formatting.

## 12. Authentication and Authorization

The MCP service must support organization-controlled authentication. The initial design keeps the identity provider abstract; Entra ID/OIDC is the preferred enterprise deployment path.

Authorization is project-scoped.

A principal can only query projects it has been granted access to. Future role distinctions may include:

- knowledge reader;
- project administrator;
- ingestion operator.

MCP read access never implies access to raw-source administration APIs.

## 13. Idempotency, Failure Handling, and Recovery

### 13.1 Idempotency

Every ingestion unit must have a stable identity derived from source system identity and revision, for example:

```text
project + repo + commit SHA + path
project + work item ID + revision
project + document ID + content revision/hash
```

Reprocessing the same revision must not duplicate graph facts.

### 13.2 Checkpoints

Synchronization checkpoints are advanced only after successful extraction and knowledge persistence.

### 13.3 Partial failure

A failed artifact does not make an entire repository permanently unsynchronizable. Failures are recorded and retryable. A release is marked fully indexed only after all required artifacts for that release reach a terminal successful/accepted state.

### 13.4 Poison artifacts

Repeatedly failing artifacts enter a dead-letter/error state with diagnostic metadata available to operators, not MCP users.

## 14. Observability

Minimum operational telemetry:

- sync runs by project/repository;
- observed refs and release tags;
- artifacts discovered/changed/skipped/failed;
- extraction latency;
- LLM calls/tokens when available;
- Graphiti write latency/failure count;
- MCP query latency and result count;
- authorization failures;
- stale-project/index-age metric.

Logs must avoid raw source content by default.

## 15. Testing Strategy

### 15.1 Unit tests

Cover:

- release resolution;
- diff/change-set generation;
- idempotency keys;
- parser normalization;
- structured extraction validation;
- result-projection/redaction;
- authorization decisions;
- domain-to-Graphiti mapping.

### 15.2 Contract tests

Define contracts for:

- Azure DevOps adapter;
- source parser interface;
- extraction LLM interface;
- `KnowledgeRepository`;
- MCP tool schemas.

Graphiti contract tests run against an ephemeral supported graph backend.

### 15.3 Integration tests

Use fixture repositories/work items to validate:

```text
initial sync
→ incremental commit
→ release tag
→ changed fact
→ historical query
→ compare releases
```

### 15.4 Security tests

Explicitly assert that MCP responses cannot retrieve:

- raw source bodies;
- raw episodes containing source content;
- arbitrary graph queries;
- credentials/internal metadata;
- another unauthorized project.

## 16. Configuration

Configuration should be environment/file driven and typed.

Initial categories:

- Azure DevOps organization/project/repository mappings;
- monitored branches;
- release-tag patterns;
- allowed document paths/sources;
- allowed HTML paths;
- local LLM endpoint/model;
- embedding endpoint/model;
- Graphiti/backend settings;
- authentication/OIDC settings;
- reconciliation interval;
- concurrency/rate limits;
- logging/telemetry settings.

Secrets must use secret stores/environment injection, never repository configuration files.

## 17. MVP Scope

The first usable release is intentionally narrow.

### Included

- one Azure DevOps organization with multiple configured projects/repos;
- Git branch synchronization;
- release tags matching configured patterns;
- PBI/User Story/Bug synchronization;
- Markdown/text/HTML project documents;
- deterministic code parsing for the first supported language set;
- self-hosted extraction LLM integration;
- Graphiti-backed temporal knowledge storage;
- custom read-only MCP server;
- release-specific search;
- release comparison;
- work-item traceability;
- project-scoped authorization;
- incremental reconciliation and retries.

### Deferred

- graphical administration UI;
- editing Azure DevOps data from MCP;
- arbitrary user-defined ontologies;
- automatic fine-tuning of extraction models;
- cross-organization federation;
- full visual screenshot understanding;
- source-code display through MCP;
- microservice decomposition.

## 18. Acceptance Criteria

The MVP is acceptable when all of the following are demonstrated on a fixture project:

1. Initial sync creates searchable knowledge from code, work items, documents, and HTML.
2. A new commit causes only affected artifacts to be reprocessed.
3. A release tag creates/resolves an explicit release associated with its commit SHA.
4. Changing a behavior in a later release preserves the previous release's behavior.
5. `get_feature(..., release=A)` and `get_feature(..., release=B)` can return different historically correct facts.
6. `compare_releases(A, B)` returns the semantic project changes between those releases.
7. A PBI can be traced to related feature/component/release knowledge when evidence exists.
8. MCP users cannot retrieve raw source code, arbitrary raw Graphiti episodes, or execute arbitrary graph queries.
9. An unauthorized user/project combination is rejected before knowledge retrieval.
10. Reprocessing an already-indexed source revision is idempotent.
11. A missed webhook can be corrected by reconciliation without duplicating facts.
12. The complete ingestion path can be deployed using self-hosted LLM/embedding services.

## 19. Key Design Decisions

- **Graphiti is a module, not the product boundary.** All Graphiti access is behind `KnowledgeRepository`.
- **Azure DevOps remains authoritative.** The knowledge graph is a derived read model.
- **Release semantics belong to the application.** Graphiti temporal capabilities complement rather than replace Git/tag/release identity.
- **Deterministic parsing precedes LLM extraction.** The LLM enriches structured facts rather than replacing compilers/parsers.
- **MCP is a safe projection.** It exposes semantic knowledge, never arbitrary graph or source retrieval.
- **History is append/supersede, not overwrite.** Historical release queries are first-class.
- **Start as a modular monolith.** Keep boundaries extractable, but avoid premature distributed-system complexity.
