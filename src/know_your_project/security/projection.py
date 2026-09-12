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
