"""Replay must resolve nested message/map selectors or reject malformed paths."""
from types import SimpleNamespace

import pytest

from dot_operator import MutationIntent, OperatorContext, ProtobufOperator, ResourceIdentityResolver
from dot_operator.types import MapKeySelector
from test_operator_operation_matrix import Record, _operator


def _item_fixture(ids=("a",)):
    target = Record()
    for key in ids:
        target.items.add(id=key, value="old")
    items = Record.DESCRIPTOR.fields_by_name["items"]
    item_type = type(target.items[0])
    value_field = item_type.DESCRIPTOR.fields_by_name["value"]
    return target, items, item_type, value_field


def _apply(target, field, parent_chain, *, value="new", operation="replace"):
    intent = MutationIntent(
        field=field, value=None, new_value=value,
        op=operation, parent_chain=[*parent_chain, field],
    )
    _operator().apply_intents(target, [intent])


def test_replay_nested_scalar_update_targets_one_identity():
    target, items, item_type, value_field = _item_fixture(("a", "b"))
    _apply(target, value_field, [items, item_type(id="b")], value="updated")
    assert [(x.id, x.value) for x in target.items] == [
        ("a", "old"), ("b", "updated")
    ]


@pytest.mark.parametrize("selector_id,expected", [
    ("", "missing repeated message selector identity"),
    ("missing", "could not resolve element with identity"),
])
def test_replay_rejects_missing_or_unknown_identity(selector_id, expected):
    target, items, item_type, value_field = _item_fixture()
    with pytest.raises(ValueError, match=expected):
        _apply(target, value_field, [items, item_type(id=selector_id)])
    assert target.items[0].value == "old"


def test_replay_rejects_ambiguous_repeated_selector():
    target, items, item_type, value_field = _item_fixture(("a", "a"))
    with pytest.raises(ValueError, match="ambiguous repeated message selector identity"):
        _apply(target, value_field, [items, item_type(id="a")])
    assert all(x.value == "old" for x in target.items)


def test_replay_rejects_field_hop_without_repeated_selector():
    target, items, item_type, value_field = _item_fixture()
    with pytest.raises(ValueError, match="does not contain field"):
        _apply(target, value_field, [items])
    assert target.items[0].value == "old"


def test_replay_rejects_invalid_parent_chain_token():
    target, _, _, value_field = _item_fixture()
    with pytest.raises(TypeError, match="Invalid parent_chain token"):
        _apply(target, value_field, [object()])
    assert target.items[0].value == "old"


def test_replay_rejects_mismatched_target_parent():
    target, _, _, value_field = _item_fixture()
    with pytest.raises(ValueError, match="does not contain field"):
        _apply(target, value_field, [Record.DESCRIPTOR.fields_by_name["profile"]])
    assert target.items[0].value == "old"


def test_replay_map_message_value_with_existing_key():
    target = Record()
    target.notes["team"].city = "Old"
    notes_field = Record.DESCRIPTOR.fields_by_name["notes"]
    city_field = type(target.notes["team"]).DESCRIPTOR.fields_by_name["city"]
    _apply(target, city_field, [notes_field, MapKeySelector("team")], value="New")
    assert target.notes["team"].city == "New"


def test_replay_map_message_value_with_new_key():
    target = Record()
    notes_field = Record.DESCRIPTOR.fields_by_name["notes"]
    city_field = notes_field.message_type.fields_by_name["value"].message_type.fields_by_name["city"]
    _apply(target, city_field, [notes_field, MapKeySelector("team")], value="Paris", operation="merge")
    assert target.notes["team"].city == "Paris"
