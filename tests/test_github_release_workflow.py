"""A tagged release must be gated on the public 6-job CI matrix."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_is_a_tag_gated_downstream_job_with_writable_token():
    workflow = (ROOT / ".github/workflows/tests.yml").read_text()
    assert "release:" in workflow
    assert "needs: public-protobuf-contract" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
    assert "contents: write" in workflow
    assert "gh release create" in workflow
    assert "--verify-tag" in workflow
    assert "GITHUB_REF_NAME" in workflow
    assert 'version = "0.1.0"' in (ROOT / "pyproject.toml").read_text()
