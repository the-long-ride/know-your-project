from typing import Literal

from tree_sitter_language_pack import get_parser

from know_your_project.domain.artifacts import Provenance, SourceArtifact
from know_your_project.extraction.models import ParsedArtifact, ParsedSymbol

SourceLanguage = Literal[
    "csharp", "python", "typescript", "tsx", "javascript", "java", "go", "rust"
]
_LANGUAGE: dict[str, SourceLanguage] = {
    ".cs": "csharp", ".py": "python", ".ts": "typescript", ".tsx": "tsx",
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
        inventory = "\n".join(f"{s.kind}: {s.name}" for s in symbols)
        semantic_text = f"{inventory}\n\nSOURCE_WINDOW:\n{artifact.content[:20000]}"
        return ParsedArtifact(
            title=artifact.path, semantic_text=semantic_text, symbols=symbols,
            provenance=Provenance(
                source_kind="git", source_id=str(artifact.artifact_id),
                repository=artifact.repository, path=artifact.path, commit_sha=artifact.commit_sha,
            ),
        )
