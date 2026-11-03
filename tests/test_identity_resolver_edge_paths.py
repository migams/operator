"""Identity paths remain canonical, including nested and tuple-form selectors."""
from types import SimpleNamespace

import pytest

from dot_operator import MutationIntent, ResourceIdentityResolver
from dot_operator.utils import _strip_selector_for_field, _selector_after_field
from test_operator_operation_matrix import Record


def _resolver(**config):
    return ResourceIdentityResolver(SimpleNamespace(identity=config))


def test_nested_identity_tuple_resolves_same_as_dotted_string():
    msg = Record()
    msg.profile.city = "Berlin"
    tuples = _resolver(key=("profile", "city"))
    dotted = _resolver(key="profile.city")
    assert tuples.fields(msg) == dotted.fields(msg) == ("profile.city",)
    assert tuples.key(msg) == dotted.key(msg) == ("Berlin",)


def test_nonexistent_or_scalar_traversal_path_is_not_an_identity():
    msg = Record(name="hello")
    identity = _resolver(key="name.subfield")
    assert identity.fields(msg) == ()
    assert identity.key(msg) == ()


def test_repeated_message_traversal_is_not_a_parent_identity():
    msg = Record()
    msg.items.add(id="a")
    identity = _resolver(key="items.id")
    assert identity.fields(msg) == ()


def test_missing_or_empty_nested_identity_fails_closed():
    identity = _resolver(key="profile.city")
    msg = Record()
    assert identity.key(msg) == ()
    msg.profile.city = "Berlin"
    assert identity.key(msg) == ("Berlin",)
    msg.profile.ClearField("city")
    assert identity.key(msg) == ()


def test_nested_identity_rejects_extra_scalar_payload():
    identity = _resolver(key="profile.city")
    msg = Record()
    msg.profile.city = "Berlin"
    assert identity.is_identity_only(msg)
    msg.name = "changed"
    assert not identity.is_identity_only(msg)
    assert identity.is_message_authoritative(msg)


def test_selector_stripping_stops_at_field_even_with_trailing_tokens():
    items = Record.DESCRIPTOR.fields_by_name["items"]
    after = Record.DESCRIPTOR.fields_by_name["tags"]
    selector = Record().items.add(id="x")
    assert _strip_selector_for_field([after, items, selector, after], items) == [
        after, items
    ]
    assert _strip_selector_for_field([], items) == []


def test_selector_lookup_rejects_non_message_following_field():
    items = Record.DESCRIPTOR.fields_by_name["items"]
    intent = MutationIntent(
        field=items, value=None, op="remove", new_value=None,
        parent_chain=[items, "invalid-selector"],
    )
    assert _selector_after_field(intent) is None


@pytest.mark.parametrize("bad_overlay", [None, object(), "incorrect"])
def test_overlay_parent_lookup_rejects_non_protobuf_overlay(bad_overlay):
    identity = _resolver(key="id")
    items = Record.DESCRIPTOR.fields_by_name["items"]
    intent = MutationIntent(
        field=items, value=None, op="merge", new_value=[],
        parent_chain=[items], overlay=bad_overlay,
    )
    assert identity.find_overlay_parent_message(intent, items) is None


def test_nested_identity_selector_rejects_unrelated_nested_payload():
    identity = _resolver(key="profile.city")
    record = Record()
    record.profile.city = "Berlin"
    record.profile.timezone = "CET"
    assert not identity.is_identity_only(record)


def test_composite_identity_across_parent_and_nested_scalar_fields():
    identity = _resolver(account="name", region=("profile", "city"))
    record = Record(name="node")
    record.profile.city = "Berlin"
    assert identity.fields(record) == ("name", "profile.city")
    assert identity.key(record) == ("node", "Berlin")
    assert identity.is_identity_only(record)
    record.profile.timezone = "CET"
    assert not identity.is_identity_only(record)
