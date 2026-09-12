from datetime import UTC, datetime
from typing import Any, cast

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId


def _changed_at(fields: dict[str, Any]) -> datetime:
    raw = fields.get("System.ChangedDate")
    if raw:
        text = str(raw)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            pass
    return datetime.now(UTC)


def work_item_artifact(project_id: ProjectId, payload: dict[str, Any]) -> SourceArtifact:
    f = cast(dict[str, Any], payload["fields"])
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
        observed_at=_changed_at(f),
    )
