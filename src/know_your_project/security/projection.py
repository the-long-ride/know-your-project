from hashlib import sha256

from know_your_project.knowledge.dto import KnowledgeResult


def _opaque_reference(result_id: str, source_kind: str, index: int) -> str:
    raw = f"{result_id}\0{source_kind}\0{index}".encode()
    return f"ref:{sha256(raw).hexdigest()[:20]}"


def project_result(result: KnowledgeResult) -> dict[str, object]:
    return {
        "id": result.id,
        "kind": result.kind,
        "summary": result.summary,
        "score": result.score,
        "valid_from": result.valid_from.isoformat() if result.valid_from else None,
        "valid_to": result.valid_to.isoformat() if result.valid_to else None,
        "provenance": [
            {
                "source_kind": provenance.source_kind,
                "reference_id": _opaque_reference(result.id, provenance.source_kind, index),
                "release_id": provenance.release_id,
            }
            for index, provenance in enumerate(result.provenance)
        ],
    }
