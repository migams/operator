"""Keep the independently executable service example in the release contract."""

from pathlib import Path
import runpy

from dot_operator import IdentitySpec, ResourceDeltaApplier, ResourceMutationContext, SpecIdentityResolver


ROOT = Path(__file__).resolve().parents[1]


def test_example_changes_only_identity_selected_service_and_adds_new_one():
    namespace = runpy.run_path(str(ROOT / "examples/service_configuration.py"))
    final, intents = namespace["demonstrate"]()
    assert final.environment == "production"
    assert len(final.services) == 3
    assert len(intents) >= 1
    billing = next(x for x in final.services if x.name == "billing")
    assert billing.replicas == 4
    assert billing.owner == "payments"


def test_resource_api_is_available_from_package_root():
    assert IdentitySpec
    assert ResourceMutationContext
    assert ResourceDeltaApplier
    assert SpecIdentityResolver


def test_production_release_metadata_is_stable():
    project = (ROOT / "pyproject.toml").read_text()
    assert 'requires = ["setuptools>=77"]' in project
    assert 'version = "0.1.0"' in project
    assert "examples/service_configuration.py" in (ROOT / "README.md").read_text()
