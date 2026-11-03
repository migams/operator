"""Behavior matrix across the public protobuf mutation operations.

Uses a generated schema and no private application types or services.
"""
from types import SimpleNamespace

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from dot_operator import OperatorContext, ProtobufOperator, ResourceIdentityResolver


def _schema():
    file = descriptor_pb2.FileDescriptorProto(
        name="oss_operator_operations.proto", package="oss_operations", syntax="proto3"
    )
    profile = file.message_type.add(name="Profile")
    item = file.message_type.add(name="Item")
    record = file.message_type.add(name="Record")

    def field(msg, name, number, kind, repeated=False, type_name="", oneof=None):
        f = msg.field.add(name=name, number=number, type=kind)
        f.label = (
            descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
            if repeated else descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        )
        if type_name:
            f.type_name = type_name
        if oneof is not None:
            f.oneof_index = oneof
        return f

    STRING = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    MESSAGE = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
    INT = descriptor_pb2.FieldDescriptorProto.TYPE_INT32
    field(profile, "city", 1, STRING)
    field(profile, "timezone", 2, STRING)
    field(item, "id", 1, STRING)
    field(item, "value", 2, STRING)
    field(item, "labels", 3, STRING, repeated=True)
    field(item, "profile", 4, MESSAGE, type_name=".oss_operations.Profile")
    field(item, "history", 5, MESSAGE, repeated=True,
          type_name=".oss_operations.Profile")
    note_entry = item.nested_type.add(name="MetaEntry")
    note_entry.options.map_entry = True
    field(note_entry, "key", 1, STRING)
    field(note_entry, "value", 2, STRING)
    field(item, "meta", 6, MESSAGE, repeated=True,
          type_name=".oss_operations.Item.MetaEntry")
    profile_entry = item.nested_type.add(name="ProfilesEntry")
    profile_entry.options.map_entry = True
    field(profile_entry, "key", 1, STRING)
    field(profile_entry, "value", 2, MESSAGE, type_name=".oss_operations.Profile")
    field(item, "profiles", 7, MESSAGE, repeated=True,
          type_name=".oss_operations.Item.ProfilesEntry")
    attachment = file.message_type.add(name="Attachment")
    field(attachment, "id", 1, STRING)
    field(attachment, "value", 2, STRING)
    field(item, "attachments", 8, MESSAGE, repeated=True,
          type_name=".oss_operations.Attachment")
    field(record, "name", 1, STRING)
    field(record, "count", 2, INT)
    field(record, "profile", 3, MESSAGE, type_name=".oss_operations.Profile")
    field(record, "tags", 4, STRING, repeated=True)
    field(record, "items", 5, MESSAGE, repeated=True, type_name=".oss_operations.Item")
    entry = record.nested_type.add(name="AttributesEntry")
    entry.options.map_entry = True
    field(entry, "key", 1, STRING)
    field(entry, "value", 2, STRING)
    field(record, "attributes", 6, MESSAGE, repeated=True,
          type_name=".oss_operations.Record.AttributesEntry")
    record.oneof_decl.add(name="contact")
    field(record, "email", 7, STRING, oneof=0)
    field(record, "phone", 8, STRING, oneof=0)
    field(record, "contact_profile", 9, MESSAGE, type_name=".oss_operations.Profile", oneof=0)
    entry = record.nested_type.add(name="NotesEntry")
    entry.options.map_entry = True
    field(entry, "key", 1, STRING)
    field(entry, "value", 2, MESSAGE, type_name=".oss_operations.Profile")
    field(record, "notes", 10, MESSAGE, repeated=True,
          type_name=".oss_operations.Record.NotesEntry")
    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(file.SerializeToString())
    return message_factory.GetMessageClass(
        pool.FindMessageTypeByName("oss_operations.Record")
    )


Record = _schema()


def _operator():
    resource = SimpleNamespace(identity={"id": "id"})
    return ProtobufOperator(
        OperatorContext(resource, ResourceIdentityResolver(resource))
    )


def _run(operation, original, overlay):
    result = Record()
    result.CopyFrom(original)
    op = _operator()
    plan = op.plan(result, overlay, op=operation)
    applied = op.apply_intents(result, plan)
    assert applied is result
    return result, plan


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_scalar_updates(operation):
    result, _ = _run(operation, Record(name="before"), Record(name="after"))
    assert result.name == "after"


def test_scalar_remove_clears_a_populated_field():
    result, _ = _run("remove", Record(name="before"), Record(name="selector"))
    assert result.name == ""


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_nested_message_updates(operation):
    initial = Record()
    initial.profile.city = "Old"
    overlay = Record()
    overlay.profile.city = "New"
    result, _ = _run(operation, initial, overlay)
    assert result.profile.city == "New"


def test_map_merge_preserves_other_entries():
    initial = Record()
    initial.attributes.update({"alpha": "old", "beta": "keep"})
    overlay = Record()
    overlay.attributes["alpha"] = "new"
    overlay.attributes["gamma"] = "added"
    result, _ = _run("merge", initial, overlay)
    assert dict(result.attributes) == {
        "alpha": "new", "beta": "keep", "gamma": "added"
    }


def test_map_scoped_replace_preserves_unmentioned_entries():
    initial = Record()
    initial.attributes.update({"alpha": "old", "beta": "keep"})
    overlay = Record()
    overlay.attributes["alpha"] = "new"
    result, _ = _run("replace", initial, overlay)
    assert dict(result.attributes) == {"alpha": "new", "beta": "keep"}


def test_map_container_replace_removes_old_keys():
    initial = Record()
    initial.attributes["old"] = "x"
    overlay = Record()
    overlay.attributes.update({"new": "y", "other": "z"})
    result, _ = _run("replace", initial, overlay)
    assert dict(result.attributes) == {"new": "y", "other": "z"}


def test_map_remove_selected_key_only():
    initial = Record()
    initial.attributes.update({"alpha": "remove", "beta": "keep"})
    overlay = Record()
    overlay.attributes["alpha"] = "anything"
    result, _ = _run("remove", initial, overlay)
    assert dict(result.attributes) == {"beta": "keep"}


def test_repeated_scalar_merge_is_idempotent():
    initial = Record(tags=["a", "b"])
    overlay = Record(tags=["b", "c"])
    first, _ = _run("merge", initial, overlay)
    second, _ = _run("merge", first, overlay)
    assert list(first.tags) == ["a", "b", "c"]
    assert list(second.tags) == list(first.tags)


def test_repeated_scalar_replace_is_authoritative():
    result, _ = _run("replace", Record(tags=["a", "b"]), Record(tags=["b", "c"]))
    assert list(result.tags) == ["b", "c"]


def test_repeated_scalar_remove_selected_elements():
    result, _ = _run("remove", Record(tags=["a", "b", "c"]), Record(tags=["b"]))
    assert list(result.tags) == ["a", "c"]


def test_repeated_message_identity_merge_updates_in_place():
    initial = Record()
    initial.items.add(id="one", value="old")
    initial.items.add(id="two", value="keep")
    overlay = Record()
    overlay.items.add(id="one", value="new")
    overlay.items.add(id="three", value="added")
    result, _ = _run("merge", initial, overlay)
    assert [(x.id, x.value) for x in result.items] == [
        ("one", "new"), ("two", "keep"), ("three", "added")
    ]


def test_repeated_message_remove_by_identity():
    initial = Record()
    initial.items.add(id="one", value="old")
    initial.items.add(id="two", value="keep")
    overlay = Record()
    overlay.items.add(id="one")
    result, _ = _run("remove", initial, overlay)
    assert [(x.id, x.value) for x in result.items] == [("two", "keep")]


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_oneof_switch_is_atomic(operation):
    result, _ = _run(
        operation, Record(email="first@example.invalid"),
        Record(phone="12345")
    )
    assert result.WhichOneof("contact") == "phone"
    assert result.phone == "12345"
    assert result.email == ""


def test_oneof_remove_clears_the_selected_branch():
    result, _ = _run("remove", Record(phone="12345"), Record(phone="12345"))
    assert result.WhichOneof("contact") is None


def test_plan_does_not_mutate_target():
    target = Record(name="old", tags=["a"])
    snapshot = Record()
    snapshot.CopyFrom(target)
    _operator().plan(target, Record(name="new", tags=["b"]), op="merge")
    assert target == snapshot


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_oneof_updates_same_branch(operation):
    result, _ = _run(operation, Record(phone="old"), Record(phone="new"))
    assert result.WhichOneof("contact") == "phone"
    assert result.phone == "new"


def test_oneof_remove_ignores_inactive_branch():
    result, _ = _run(
        "remove", Record(email="keep@example.invalid"), Record(phone="unused")
    )
    assert result.WhichOneof("contact") == "email"
    assert result.email == "keep@example.invalid"


def test_oneof_equal_merge_produces_no_mutations():
    _, plan = _run("merge", Record(phone="same"), Record(phone="same"))
    assert plan == []


def test_scalar_remove_with_equal_selector_value():
    result, _ = _run("remove", Record(name="selected"), Record(name="selected"))
    assert result.name == ""


def test_nested_message_remove_clears_only_targeted_scalar():
    current = Record()
    current.profile.city = "London"
    current.profile.timezone = "UTC"
    overlay = Record()
    overlay.profile.city = "chosen"
    result, _ = _run("remove", current, overlay)
    assert result.profile.city == ""
    assert result.profile.timezone == "UTC"


def test_repeated_message_scoped_replace_preserves_siblings():
    current = Record()
    current.items.add(id="one", value="old")
    current.items.add(id="two", value="keep")
    overlay = Record()
    overlay.items.add(id="one", value="updated")
    result, _ = _run("replace", current, overlay)
    assert [(x.id, x.value) for x in result.items] == [
        ("one", "updated"), ("two", "keep")
    ]


def test_map_merge_message_values_preserves_unmentioned_fields():
    current = Record()
    current.notes["work"].city = "Amsterdam"
    overlay = Record()
    overlay.notes["work"].timezone = "CET"
    result, _ = _run("merge", current, overlay)
    assert result.notes["work"].city == "Amsterdam"
    assert result.notes["work"].timezone == "CET"


def test_map_replace_message_value_clears_unmentioned_fields():
    current = Record()
    current.notes["work"].city = "Amsterdam"
    current.notes["work"].timezone = "CET"
    overlay = Record()
    overlay.notes["work"].city = "Berlin"
    result, _ = _run("replace", current, overlay)
    assert result.notes["work"].city == "Berlin"
    assert result.notes["work"].timezone == ""


def test_map_remove_message_value():
    current = Record()
    current.notes["work"].city = "Amsterdam"
    current.notes["home"].city = "Berlin"
    overlay = Record()
    overlay.notes["work"].city = "selected"
    result, _ = _run("remove", current, overlay)
    assert set(result.notes) == {"home"}


def test_map_remove_absent_key_is_noop():
    current = Record()
    current.attributes["keep"] = "value"
    overlay = Record()
    overlay.attributes["absent"] = "ignored"
    result, plan = _run("remove", current, overlay)
    assert result == current
    assert plan == []


@pytest.mark.parametrize("operation", ["merge", "replace"])
def test_oneof_same_message_branch(operation):
    current = Record()
    current.contact_profile.city = "Rome"
    overlay = Record()
    overlay.contact_profile.timezone = "CET"
    result, _ = _run(operation, current, overlay)
    assert result.WhichOneof("contact") == "contact_profile"
    assert result.contact_profile.timezone == "CET"
    assert result.contact_profile.city == ("Rome" if operation == "merge" else "")


def test_invalid_overlay_type_is_rejected():
    with pytest.raises(TypeError):
        _operator().plan(Record(), object(), op="merge")


def test_dict_overlay_is_supported():
    result, _ = _run("merge", Record(name="old"), {"name": "new"})
    assert result.name == "new"


def test_repeated_message_identity_only_replace_is_element_scoped():
    current = Record()
    current.items.add(id="one", value="previous")
    current.items.add(id="two", value="untouched")
    overlay = Record()
    overlay.items.add(id="one")
    result, _ = _run("replace", current, overlay)
    assert [(x.id, x.value) for x in result.items] == [
        ("one", ""), ("two", "untouched")
    ]


def test_repeated_message_identity_only_replace_unknown_single_element():
    current = Record()
    current.items.add(id="one", value="old")
    overlay = Record()
    overlay.items.add(id="three")
    result, _ = _run("replace", current, overlay)
    assert [(x.id, x.value) for x in result.items] == [("three", "")]


def test_repeated_message_remove_unknown_identity_is_noop():
    current = Record()
    current.items.add(id="one", value="keep")
    overlay = Record()
    overlay.items.add(id="missing")
    result, _ = _run("remove", current, overlay)
    assert result == current


def test_unknown_operation_is_rejected_during_planning():
    target = Record(name="old")
    before = Record()
    before.CopyFrom(target)
    with pytest.raises(ValueError, match="unsupported operator operation"):
        _operator().plan(target, Record(name="new"), op="upsert")
    assert target == before
