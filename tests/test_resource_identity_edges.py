"""Descriptor-driven identity contracts, including nested paths and fail-closed lookup."""
from types import SimpleNamespace

import pytest
from google.protobuf import descriptor_pb2

from dot_operator import MutationIntent
from dot_operator.resource import IdentitySpec, SpecIdentityResolver
from test_operator_operation_matrix import Record


def _resolver(*paths, overrides=None):
    return SpecIdentityResolver(
        IdentitySpec(paths=tuple(paths)), identities=overrides or {}
    )


def test_descriptor_resolution_accepts_instance_class_and_descriptor():
    resolver = _resolver("name")
    assert resolver.fields(Record()) == ("name",)
    assert resolver.fields(Record.DESCRIPTOR) == ("name",)
    assert resolver.fields(Record) == ("name",)


def test_descriptor_resolution_rejects_non_protobuf_object():
    with pytest.raises(TypeError, match="unsupported type"):
        _resolver("id").fields(object())


@pytest.mark.parametrize(
    "path", ["", "unknown", "name.field", "items.id", "profile.unknown", "."]
)
def test_identity_path_validation_rejects_invalid_routes(path):
    assert _resolver(path).fields(Record()) == ()


def test_descriptor_specific_override_selects_separate_identity():
    items = Record().items
    item = items.add(id="a", value="payload")
    resolver = _resolver(
        "name",
        overrides={"oss_operations.Item": IdentitySpec(paths=("id",))},
    )
    assert resolver.fields(Record()) == ("name",)
    assert resolver.fields(item) == ("id",)
    assert resolver.key(item) == ("a",)


def test_nested_identity_path_is_supported_and_normalized():
    resolver = _resolver("profile.city")
    record = Record()
    record.profile.city = "Paris"
    assert resolver.fields(record) == ("profile.city",)
    assert resolver.key(record) == ("Paris",)


def test_missing_identity_and_empty_identity_are_rejected():
    resolver = _resolver("profile.city")
    assert resolver.key(Record()) == ()
    assert resolver.key(object()) == ()
    assert _resolver("unknown").key(Record()) == ()


def test_message_valued_identity_uses_stable_serialization():
    resolver = _resolver("profile")
    a = Record()
    b = Record()
    a.profile.city = "Paris"
    b.profile.city = "Paris"
    assert resolver.key(a)
    assert resolver.matches(a, b)
    b.profile.city = "Berlin"
    assert not resolver.matches(a, b)


def test_type_mismatch_or_missing_identity_is_never_a_match():
    resolver = _resolver("name")
    assert not resolver.matches(Record(name="a"), descriptor_pb2.DescriptorProto(name="a"))
    assert not resolver.matches(Record(), Record())
    assert not resolver.matches(Record(name="a"), Record(name="b"))


def test_find_skips_non_message_wrong_type_and_wrong_key():
    resolver = _resolver("name")
    expected = Record(name="chosen")
    found = Record(name="chosen")
    assert resolver.find(
        [None, object(), descriptor_pb2.DescriptorProto(name="chosen"),
         Record(name="other"), found],
        expected,
    ) is found
    assert resolver.find([Record(name="other")], expected) is None
    assert resolver.find([found], Record()) is None


def test_identity_only_classification_allows_nested_repeated_messages():
    resolver = _resolver("name")
    record = Record(name="selector")
    record.items.add(id="a", value="payload")
    assert resolver.is_identity_only(record)
    record.count = 2
    assert not resolver.is_identity_only(record)
    assert resolver.is_message_authoritative(record)


def test_authoritative_classification_ignores_messages_and_repeated_scalars():
    resolver = _resolver("name")
    record = Record(name="selector")
    record.profile.city = "Paris"
    record.tags.append("x")
    assert not resolver.is_message_authoritative(record)
    assert not resolver.is_identity_only(record)
    no_identity = _resolver("unknown")
    assert not no_identity.is_message_authoritative(record)
    assert not no_identity.is_identity_only(record)


def test_find_overlay_parent_resolves_root_and_nested_message():
    resolver = _resolver("name")
    overlay = Record(name="root")
    overlay.profile.city = "Paris"
    profile = Record.DESCRIPTOR.fields_by_name["profile"]
    city = overlay.profile.DESCRIPTOR.fields_by_name["city"]
    nested_intent = MutationIntent(
        field=city, value=None, new_value="Paris", op="merge",
        overlay=overlay, parent_chain=[profile, city],
    )
    root_intent = MutationIntent(
        field=profile, value=None, new_value=overlay.profile, op="merge",
        overlay=overlay, parent_chain=[profile],
    )
    assert resolver.find_overlay_parent_message(root_intent, profile) is overlay
    assert resolver.find_overlay_parent_message(nested_intent, city) is overlay.profile


def test_overlay_parent_identity_selection_skips_unmatched_and_finds_correct_element():
    resolver = _resolver("id", overrides={"oss_operations.Item": IdentitySpec(paths=("id",))})
    overlay = Record()
    overlay.items.add(id="a", value="first")
    overlay.items.add(id="b", value="second")
    items_field = Record.DESCRIPTOR.fields_by_name["items"]
    item_type = type(overlay.items[0])
    value_field = item_type.DESCRIPTOR.fields_by_name["value"]
    intent = MutationIntent(
        field=value_field, value=None, new_value="second", op="merge",
        overlay=overlay,
        parent_chain=[items_field, item_type(id="b"), value_field],
    )
    assert resolver.find_overlay_parent_message(intent, value_field) is overlay.items[1]


@pytest.mark.parametrize("selector_id", ["", "missing"])
def test_overlay_parent_unresolvable_selector_fails_closed(selector_id):
    resolver = _resolver("id")
    overlay = Record()
    overlay.items.add(id="a", value="payload")
    field = Record.DESCRIPTOR.fields_by_name["items"]
    item_type = type(overlay.items[0])
    value_field = item_type.DESCRIPTOR.fields_by_name["value"]
    intent = MutationIntent(
        field=value_field, value=None, new_value="payload", op="merge",
        overlay=overlay,
        parent_chain=[field, item_type(id=selector_id), value_field],
    )
    assert resolver.find_overlay_parent_message(intent, value_field) is None


def test_overlay_parent_invalid_token_and_wrong_message_type_fail_closed():
    resolver = _resolver("name")
    overlay = Record(name="root")
    field = Record.DESCRIPTOR.fields_by_name["name"]
    unknown = MutationIntent(
        field=field, value=None, new_value="new", op="merge",
        overlay=overlay, parent_chain=[object(), field],
    )
    wrong_overlay = MutationIntent(
        field=field, value=None, new_value="new", op="merge",
        overlay=object(), parent_chain=[field],
    )
    assert resolver.find_overlay_parent_message(unknown, field) is None
    assert resolver.find_overlay_parent_message(wrong_overlay, field) is None


def test_normalized_list_identity_values_are_hashable_tuples():
    assert SpecIdentityResolver._normalize_identity_value(["a", "b"]) == ("a", "b")
    assert SpecIdentityResolver._normalize_identity_value(("a", "b")) == ("a", "b")
