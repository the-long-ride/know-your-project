from datetime import UTC, datetime

from know_your_project.domain.artifacts import SourceArtifact
from know_your_project.domain.ids import ArtifactId, ProjectId
from know_your_project.extraction.parsers.document import DocumentParser
from know_your_project.extraction.parsers.html import HtmlParser
from know_your_project.extraction.parsers.source import TreeSitterSourceParser
from know_your_project.extraction.parsers.work_item import WorkItemParser


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


def test_document_parser_normalizes_blank_lines() -> None:
    parsed = DocumentParser().parse(artifact("document", "spec.md", "A\n\n\n\nB"))
    assert parsed.semantic_text == "A\n\nB"


def test_work_item_parser_preserves_semantic_text() -> None:
    parsed = WorkItemParser().parse(artifact("work_item", "work-item:1", "title: Retry"))
    assert parsed.semantic_text == "title: Retry"
