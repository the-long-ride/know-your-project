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
        actions = [
            e.get_text(" ", strip=True)
            for e in soup.find_all(["button", "a"])
            if e.get_text(" ", strip=True)
        ]
        text = "\n".join([
            *(f"label: {x}" for x in labels),
            *(f"field: {x}" for x in fields if x),
            *(f"action: {x}" for x in actions),
        ])
        return ParsedArtifact(
            title=artifact.path or str(artifact.artifact_id), semantic_text=text,
            provenance=Provenance(
                source_kind="html", source_id=str(artifact.artifact_id), path=artifact.path
            ),
        )
