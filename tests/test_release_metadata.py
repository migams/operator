"""Guardrails for releasing the independent MIT-licensed distribution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_release_uses_mit_license_and_embeds_license_file():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert 'license = "MIT"' in metadata
    assert 'license-files = ["LICENSE"]' in metadata
    assert license_text.startswith("MIT License")
    assert "Copyright (c) 2026 Michael Gams" in license_text


def test_protobuf_6_security_floor_prevents_known_affected_ranges():
    metadata = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert 'dependencies = ["protobuf>=6.31.1,<7"]' in metadata
    assert "protobuf>=6.31.1,<7" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_ci_enforces_branch_coverage_floor():
    project = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/tests.yml").read_text(encoding="utf-8")
    assert "pytest-cov>=7,<8" in project
    for flag in ("--cov=dot_operator", "--cov-branch", "--cov-fail-under=80"):
        assert flag in workflow
