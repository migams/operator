"""Public resource delta, identity resolution, and immutable-path contracts."""
import pytest

from dot_operator import MutationIntent
from dot_operator.resource import (
    IdentitySpec,
    ResourceDeltaApplier,
    ResourceMutationContext,
    SpecIdentityResolver,
)
from test_operator_operation_matrix import Record, _operator


def _context(immutable=("name",)):
    return ResourceMutationContext(
        identity=IdentitySpec(paths=("id",)),
        identities={"oss_operations.Item": IdentitySpec(paths=("id",))},
        immutable_paths=immutable,
    )


def test_delta_diff_is_pure_and_replayable():
    before = Record(name="stable", count=1)
    desired = Record(name="stable", count=3)
    delta = ResourceDeltaApplier()
    plan = delta.diff(before, desired, context=_context())
    assert plan
    assert before.count == 1
    target = Record()
    target.CopyFrom(before)
    result = delta.apply(target, intents=plan, context=_context())
    assert result is target
    assert target == desired


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_delta_updates_scalar_fields(operation):
    before = Record(name="stable", count=1)
    desired = Record(count=3)
    delta = ResourceDeltaApplier()
    result = getattr(delta, operation)(before, value=desired, context=_context())
    assert result is before
    assert result.name == "stable"
    assert result.count == 3


def test_delta_remove_selected_map_entry():
    before = Record(name="stable")
    before.attributes.update({"selected": "delete", "other": "retain"})
    overlay = Record()
    overlay.attributes["selected"] = "selector"
    result = ResourceDeltaApplier().remove(before, value=overlay, context=_context())
    assert dict(result.attributes) == {"other": "retain"}


def test_delta_rejects_mutation_of_immutable_path_atomically():
    before = Record(name="stable", count=1)
    attempt = Record(name="forbidden", count=3)
    with pytest.raises(ValueError, match="immutable protobuf path"):
        ResourceDeltaApplier().merge(before, value=attempt, context=_context())
    assert before == Record(name="stable", count=1)


def test_delta_replayed_plan_cannot_bypass_immutable_guard():
    before = Record(name="stable", count=1)
    attempted = Record(name="forbidden", count=3)
    original = Record()
    original.CopyFrom(before)
    unguarded = ResourceDeltaApplier().diff(before, attempted, context=_context(()))
    with pytest.raises(ValueError, match="immutable protobuf path"):
        ResourceDeltaApplier().apply(before, intents=unguarded, context=_context())
    assert before == original


def test_identity_match_and_find_reject_unknown_or_missing_keys():
    spec = SpecIdentityResolver(IdentitySpec(paths=("id",)))
    target = Record()
    selected = target.items.add(id="a", value="first")
    target.items.add(id="b", value="second")
    assert spec.fields(selected) == ("id",)
    assert spec.key(selected) == ("a",)
    lookup = type(selected)(id="a")
    assert spec.matches(selected, lookup)
    assert spec.find(target.items, lookup) is selected
    assert spec.find(target.items, type(selected)(id="missing")) is None
    assert spec.find(target.items, type(selected)()) is None
    assert spec.key(type(selected)()) == ()


def test_invalid_descriptor_identity_paths_are_ignored():
    spec = SpecIdentityResolver(
        IdentitySpec(paths=("does_not_exist", "items.id", "name.absent"))
    )
    assert spec.fields(Record()) == ()


def test_root_replacement_intent_uses_no_field_selector():
    target = Record(name="old", count=1)
    replacement = Record(name="new", count=2)
    intent = MutationIntent(
        field=None, value=target, new_value=replacement,
        op="replace", parent_chain=[],
    )
    _operator().apply_intents(target, [intent])
    assert target == replacement
