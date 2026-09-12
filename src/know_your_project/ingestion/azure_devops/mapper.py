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
