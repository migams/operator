"""Keep public docs executable and independent of internal project terminology."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_readme_stays_standalone_and_describes_actual_package():
    doc = (ROOT / "README.md").read_text(encoding="utf-8")
    assert doc.startswith("# Protobuf Mutation Operator\n")
    assert "protobuf>=6.31.1,<7" in doc
    assert "dot_operator" in doc
    for old in ("DOT Core", "private history", "source provenance", "OSS-only", "Release preparation"):
        assert old.casefold() not in doc.casefold()
    assert "## Quick start" in doc
    assert "## Behavior" in doc
    assert "## License" in doc


def test_readme_quick_start_runs_without_private_runtime():
    doc = (ROOT / "README.md").read_text(encoding="utf-8")
    match = re.search(r"## Quick start[\s\S]*?\x60\x60\x60python\n(.*?)\n\x60\x60\x60", doc, re.DOTALL)
    assert match is not None, "README must contain an executable Python quick start"
    namespace = {"__name__": "__readme_example__"}
    exec(compile(match.group(1), "README.md", "exec"), namespace)
    assert namespace["current"].message_type[0].options.map_entry is True


def test_internal_release_documents_not_in_public_checkout():
    assert not (ROOT / "RELEASE_CHECKLIST.md").exists()
    assert not (ROOT / "SOURCE_PROVENANCE.md").exists()
