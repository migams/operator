"""Replay persisted mutation intents, including container-level operations."""
import pytest

from dot_operator import MutationIntent
from test_operator_operation_matrix import Record, _operator


def _replay(target, field_name, operation, value, *, before=None, selector=None):
    field = target.DESCRIPTOR.fields_by_name[field_name]
    intent = MutationIntent(
        field=field,
        value=before,
        new_value=value,
        op=operation,
        parent_chain=[field] if selector is None else [field, selector],
    )
    result = _operator().apply_intents(target, [intent])
    assert result is target
    return result


@pytest.mark.parametrize("operation,expected", [
    ("merge", {"a": "updated", "b": "keep"}),
    ("replace", {"a": "updated"}),
    ("remove", {"b": "keep"}),
])
def test_map_container_level_replay(operation, expected):
    target = Record()
    target.attributes.update({"a": "old", "b": "keep"})
    _replay(target, "attributes", operation, {"a": "updated"})
    assert dict(target.attributes) == expected


def test_replayed_map_clear_all_entries_requires_explicit_none():
    target = Record()
    target.attributes["a"] = "old"
    _replay(target, "attributes", "remove", None)
    assert dict(target.attributes) == {}


def test_replayed_map_empty_selector_is_noop():
    target = Record()
    target.attributes["a"] = "keep"
    _replay(target, "attributes", "remove", {})
    assert dict(target.attributes) == {"a": "keep"}


@pytest.mark.parametrize("operation,values,expected", [
    ("merge", ["b", "c"], ["a", "b", "c"]),
    ("replace", ["b", "c"], ["b", "c"]),
    ("remove", ["b"], ["a", "c"]),
    ("remove", None, []),
    ("remove", [], ["a", "b", "c"]),
])
def test_repeated_scalar_container_level_replay(operation, values, expected):
    target = Record(tags=["a", "b", "c"])
    _replay(target, "tags", operation, values)
    assert list(target.tags) == expected


def test_repeated_message_merge_replay_updates_and_appends():
    target = Record()
    target.items.add(id="a", value="old")
    item_type = type(target.items[0])
    _replay(
        target, "items", "merge",
        [item_type(id="a", value="new"), item_type(id="b", value="added")],
    )
    assert [(x.id, x.value) for x in target.items] == [
        ("a", "new"), ("b", "added")
    ]


def test_replayed_implicit_identity_element_replace():
    target = Record()
    target.items.add(id="a", value="old")
    target.items.add(id="b", value="keep")
    item_type = type(target.items[0])
    _replay(
        target, "items", "replace",
        [item_type(id="a", value="new")],
        before=[item_type(id="a")],
    )
    assert [(x.id, x.value) for x in target.items] == [
        ("a", "new"), ("b", "keep")
    ]


def test_replayed_replace_unmatched_identity_appends_element():
    target = Record()
    target.items.add(id="a", value="existing")
    item_type = type(target.items[0])
    _replay(
        target, "items", "replace",
        [item_type(id="b", value="new")],
        before=[item_type(id="b")],
    )
    assert [(x.id, x.value) for x in target.items] == [
        ("a", "existing"), ("b", "new")
    ]


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_replayed_message_operations_keep_container_identity(operation):
    target = Record()
    target.profile.city = "Original"
    profile_type = type(target.profile)
    _replay(target, "profile", operation, profile_type(city="Updated"))
    assert target.profile.city == "Updated"


def test_replayed_message_remove_clears_field():
    target = Record()
    target.profile.city = "Original"
    _replay(target, "profile", "remove", None)
    assert not target.HasField("profile")


def test_unknown_replayed_operation_is_rejected_before_mutation():
    target = Record(name="old")
    field = target.DESCRIPTOR.fields_by_name["name"]
    intent = MutationIntent(
        field=field, value="old", new_value="new",
        op="upsert", parent_chain=[field],
    )
    with pytest.raises(ValueError, match="unsupported operator operation"):
        _operator().apply_intents(target, [intent])
    assert target.name == "old"



def test_remove_preserves_unrelated_duplicate_repeated_message_elements():
    target = Record()
    target.items.add(id="a", value="first")
    target.items.add(id="a", value="second")
    target.items.add(id="b", value="delete")
    item_type = type(target.items[0])
    _replay(target, "items", "remove", [item_type(id="b")])
    assert [(x.id, x.value) for x in target.items] == [
        ("a", "first"), ("a", "second")
    ]


def test_empty_repeated_message_selector_is_noop():
    target = Record()
    target.items.add(id="a", value="keep")
    _replay(target, "items", "remove", [])
    assert [(x.id, x.value) for x in target.items] == [("a", "keep")]
