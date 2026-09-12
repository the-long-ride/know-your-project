from know_your_project.domain.ids import ProjectId
from know_your_project.ingestion.azure_devops.mapper import work_item_artifact


def test_work_item_mapper_preserves_semantic_fields() -> None:
    artifact = work_item_artifact(ProjectId("p"), {
        "id": 1842,
        "rev": 7,
        "fields": {
            "System.WorkItemType": "Product Backlog Item",
            "System.Title": "Automatic Payment Retry",
            "System.State": "Active",
            "System.Description": "Retry failed payment",
            "Microsoft.VSTS.Common.AcceptanceCriteria": "Maximum 3 attempts",
        },
    })
    assert artifact.artifact_id == "work-item:1842"
    assert artifact.revision == "7"
    assert "Maximum 3 attempts" in artifact.content
