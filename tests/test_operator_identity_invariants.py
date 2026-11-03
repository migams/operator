import pytest
from google.protobuf import descriptor_pb2
from dot_operator.resource import IdentitySpec, ResourceMutationContext
from operator_harness import make_operator

def test_blank_identity_is_rejected():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add()
    desired = descriptor_pb2.FileDescriptorProto()
    desired.message_type.add().options.map_entry = True
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    with pytest.raises(ValueError):
        make_operator(current, context=context).apply(current, 'merge', desired)


def test_duplicate_existing_identity_is_rejected():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Same')
    current.message_type.add(name='Same')
    desired = descriptor_pb2.FileDescriptorProto()
    desired.message_type.add(name='Same').options.map_entry = True
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    with pytest.raises(ValueError):
        make_operator(current, context=context).apply(current, 'merge', desired)

from dot_operator.types import MutationIntent


def test_replayed_merge_rejects_missing_identity_before_mutation():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Valid')
    incoming = descriptor_pb2.DescriptorProto()
    incoming.options.map_entry = True
    field = current.DESCRIPTOR.fields_by_name['message_type']
    intent = MutationIntent(field=field, value=[], new_value=[incoming], op='merge',
                            parent_chain=[field])
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    before = current.SerializeToString(deterministic=True)
    with pytest.raises(ValueError):
        make_operator(current, context=context).apply_intents(current, [intent])
    assert current.SerializeToString(deterministic=True) == before


def test_replayed_merge_rejects_duplicate_existing_identity():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Same')
    current.message_type.add(name='Same')
    incoming = descriptor_pb2.DescriptorProto(name='Same')
    incoming.options.map_entry = True
    field = current.DESCRIPTOR.fields_by_name['message_type']
    intent = MutationIntent(field=field, value=[], new_value=[incoming], op='merge',
                            parent_chain=[field])
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    before = current.SerializeToString(deterministic=True)
    with pytest.raises(ValueError):
        make_operator(current, context=context).apply_intents(current, [intent])
    assert current.SerializeToString(deterministic=True) == before


def test_merge_valid_unique_identity_preserves_single_element():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Valid')
    desired = descriptor_pb2.FileDescriptorProto()
    desired.message_type.add(name='Valid').options.map_entry = True
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    result = make_operator(current, context=context).apply(current, 'merge', desired)
    assert len(result.message_type) == 1
    assert result.message_type[0].name == 'Valid'
    assert result.message_type[0].options.map_entry is True

def test_repeated_without_identity_uses_documented_list_semantics():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Same')
    desired = descriptor_pb2.FileDescriptorProto()
    desired.message_type.add(name='Same').options.map_entry = True
    context = ResourceMutationContext(identity=IdentitySpec(paths=('metadata.uid',)), immutable_paths=())
    first = make_operator(current, context=context).apply(current, 'merge', desired)
    assert len(first.message_type) == 2
    second = make_operator(first, context=context).apply(first, 'merge', desired)
    assert len(second.message_type) == 3


def test_repeated_with_unique_identity_is_merge_idempotent():
    current = descriptor_pb2.FileDescriptorProto()
    current.message_type.add(name='Unique')
    desired = descriptor_pb2.FileDescriptorProto()
    desired.message_type.add(name='Unique').options.map_entry = True
    context = ResourceMutationContext(identity=IdentitySpec(paths=('name',)), immutable_paths=())
    first = make_operator(current, context=context).apply(current, 'merge', desired)
    second = make_operator(first, context=context).apply(first, 'merge', desired)
    assert len(second.message_type) == 1
    assert second.message_type[0].options.map_entry is True

import warnings
from google.protobuf import struct_pb2
from dot_operator.resource import SpecIdentityResolver


def test_nested_repeated_path_detection_emits_no_deprecation_warning():
    resolver = SpecIdentityResolver(IdentitySpec(paths=('message_type.name',)))
    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        assert resolver.fields(descriptor_pb2.FileDescriptorProto()) == ()


def test_google_protobuf_struct_is_dispatched_as_atomic_field():
    current = struct_pb2.Value()
    current.struct_value.update({'priority': 1})
    desired = struct_pb2.Value()
    desired.struct_value.update({'priority': 2})
    context = ResourceMutationContext(identity=IdentitySpec(paths=('metadata.uid',)), immutable_paths=())
    result = make_operator(current, context=context).apply(current, 'replace', desired)
    assert result.struct_value.fields['priority'].number_value == 2


from dot_operator.engine import FieldKind, field_kind


def test_struct_merge_is_atomic_not_dict_patch():
    current = struct_pb2.Value()
    current.struct_value.update({'keep': 1, 'old': 2})
    desired = struct_pb2.Value()
    desired.struct_value.update({'new': 3})
    result = make_operator(current).apply(current, 'merge', desired)
    assert dict(result.struct_value) == {'new': 3}


def test_struct_replace_is_idempotent_and_preserves_siblings():
    current = struct_pb2.ListValue()
    first = current.values.add()
    first.struct_value.update({'old': 1})
    current.values.add().string_value = 'sibling'
    desired = struct_pb2.ListValue()
    desired.values.add().struct_value.update({'new': 2})
    desired.values.add().string_value = 'sibling'
    result = make_operator(current).apply(current, 'replace', desired)
    assert dict(result.values[0].struct_value) == {'new': 2}
    assert result.values[1].string_value == 'sibling'
    assert make_operator(result).plan(result, desired, op='replace') == []


@pytest.mark.parametrize('same_overlay', [True, False])
def test_struct_remove_clears_oneof_field(same_overlay):
    current = struct_pb2.Value()
    current.struct_value.update({'old': 1})
    overlay = struct_pb2.Value()
    overlay.struct_value.update({'old': 1} if same_overlay else {'different': 2})
    result = make_operator(current).apply(current, 'remove', overlay)
    assert result.WhichOneof('kind') is None
    assert not result.HasField('struct_value')


def test_struct_classification_uses_registered_message_kind():
    field = struct_pb2.Value.DESCRIPTOR.fields_by_name['struct_value']
    assert field_kind(field) is FieldKind.MESSAGE
    assert {item.name for item in FieldKind} == {'SCALAR', 'MESSAGE', 'REPEATED', 'MAP'}


def test_descriptor_path_does_not_access_deprecated_field_label():
    class Field:
        def __init__(self, message_type=None, *, repeated=False):
            self.message_type = message_type
            self.is_repeated = repeated

        @property
        def label(self):
            raise AssertionError("deprecated FieldDescriptor.label accessed")

    class Descriptor:
        def __init__(self, fields):
            self.fields_by_name = fields

    leaf = Descriptor({"uid": Field()})
    root = Descriptor({
        "items": Field(leaf, repeated=True),
        "single": Field(leaf, repeated=False),
    })
    assert SpecIdentityResolver._path_for_descriptor(root, "items.uid") is None
    assert SpecIdentityResolver._path_for_descriptor(root, "single.uid") == "single.uid"

