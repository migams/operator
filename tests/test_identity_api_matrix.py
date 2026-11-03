"""Identity API and replay selector contracts for public protobuf models."""
from types import SimpleNamespace

import pytest
from google.protobuf import descriptor_pb2

from dot_operator import MutationIntent, ResourceIdentityResolver, identity_key
from dot_operator.utils import (
    _chain_contains_descriptor,
    _is_message_repeated,
    _selector_after_field,
    _strip_selector_for_field,
    messages_equal,
)
from test_operator_operation_matrix import Record


@pytest.fixture
def resolver():
    return ResourceIdentityResolver(SimpleNamespace(identity={"entry": "id"}))


@pytest.mark.parametrize("value", [
    "oss_operations.Item",
    Record,
    Record.DESCRIPTOR,
    Record(),
])
def test_public_identity_key_accepts_string_type_descriptor_and_message(value):
    expected = "oss_operations.Item" if isinstance(value, str) else "oss_operations.Record"
    assert identity_key(value) == expected


def test_public_identity_key_rejects_non_protobuf_objects():
    with pytest.raises(TypeError):
        identity_key(object())


def test_identity_resolver_supports_message_or_descriptor(resolver):
    items = Record.DESCRIPTOR.fields_by_name["items"]
    assert resolver.fields(items.message_type) == ("id",)
    item = Record().items.add(id="a")
    assert resolver.fields(item) == ("id",)
    assert resolver.key(item) == ("a",)
    assert resolver.key(type(item)) == ()


def test_identity_resolver_detects_keyed_and_unkeyed_collections(resolver):
    fields = Record.DESCRIPTOR.fields_by_name
    assert resolver.container_mode(fields["items"]) == "set"
    assert resolver.container_mode(fields["tags"]) == "list"
    assert resolver.container_mode(fields["profile"]) == "list"


def test_identity_resolver_classifies_identity_only_payload(resolver):
    item = Record().items.add(id="a")
    assert resolver.is_identity_only(item)
    assert not resolver.is_message_authoritative(item)
    item.value = "changed"
    assert not resolver.is_identity_only(item)
    assert resolver.is_message_authoritative(item)


def test_identity_resolver_rejects_incomplete_or_absent_identity(resolver):
    empty = Record().items.add()
    assert resolver.key(empty) == ()
    assert not resolver.is_message_authoritative(Record())


def test_identity_resolver_finds_overlay_parent_for_root_container(resolver):
    overlay = Record()
    overlay.items.add(id="a")
    f = Record.DESCRIPTOR.fields_by_name["items"]
    intent = MutationIntent(
        field=f, value=None, op="merge", new_value=list(overlay.items),
        overlay=overlay, parent_chain=[f],
    )
    assert resolver.find_overlay_parent_message(intent, f) is overlay


def test_identity_resolver_finds_overlay_parent_for_identity_selector(resolver):
    overlay = Record()
    overlay.items.add(id="a", value="new")
    f = Record.DESCRIPTOR.fields_by_name["items"]
    item = overlay.items[0]
    value_field = item.DESCRIPTOR.fields_by_name["value"]
    selector = type(item)(id="a")
    intent = MutationIntent(
        field=value_field, value=None, op="merge", new_value="new",
        overlay=overlay, parent_chain=[f, selector, value_field],
    )
    assert resolver.find_overlay_parent_message(intent, value_field) == item


def test_overlay_parent_lookup_fails_closed_on_missing_selector(resolver):
    overlay = Record()
    overlay.items.add(id="a")
    f = Record.DESCRIPTOR.fields_by_name["items"]
    item = overlay.items[0]
    value_field = item.DESCRIPTOR.fields_by_name["value"]
    intent = MutationIntent(
        field=value_field, value=None, op="merge", new_value="new",
        overlay=overlay, parent_chain=[f, type(item)(id="missing"), value_field],
    )
    assert resolver.find_overlay_parent_message(intent, value_field) is None


def test_selector_helpers_preserve_repeated_context():
    record = Record()
    item = record.items.add(id="a")
    field = record.DESCRIPTOR.fields_by_name["items"]
    assert _is_message_repeated(record.items)
    assert not _is_message_repeated(record.tags if record.tags else ["string"])
    chain = [field, item, item.DESCRIPTOR.fields_by_name["value"]]
    assert _strip_selector_for_field(chain, field) == [field]
    intent = MutationIntent(
        field=field, value=None, new_value=[], parent_chain=[field, item],
    )
    assert _selector_after_field(intent) is item
    assert _chain_contains_descriptor(chain, item)
    assert not _chain_contains_descriptor([field], item)


def test_message_equality_is_value_based():
    a = Record(name="same")
    b = Record(name="same")
    assert messages_equal(a, b)
    b.name = "different"
    assert not messages_equal(a, b)


def test_metadata_descriptor_works_without_private_domain_types():
    # A public protobuf type works as input even when no identity matches.
    resolver = ResourceIdentityResolver(SimpleNamespace(identity={}))
    assert resolver.fields(descriptor_pb2.DescriptorProto()) == ()
