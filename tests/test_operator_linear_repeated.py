from unittest.mock import patch
from google.protobuf import descriptor_pb2
from dot_operator.resource import IdentitySpec, ResourceMutationContext
from dot_operator.handlers.repeated import RepeatedHandler
from operator_harness import make_operator

def inputs(n=24):
    target = descriptor_pb2.FileDescriptorProto()
    overlay = descriptor_pb2.FileDescriptorProto()
    for i in range(n):
        target.message_type.add(name="M%03d" % i)
        overlay.message_type.add(name="M%03d" % i).options.map_entry = True
    ctx = ResourceMutationContext(identity=IdentitySpec(paths=("name",)), immutable_paths=())
    return make_operator(target, context=ctx), target, overlay

def test_plan_uses_bounded_identity_comparisons():
    op, target, overlay = inputs()
    original = RepeatedHandler._score_identity_match
    calls = [0]
    def spy(self, *args, **kwargs):
        calls[0] += 1
        return original(self, *args, **kwargs)
    with patch.object(RepeatedHandler, "_score_identity_match", spy):
        intents = op.plan(target, overlay, op="merge")
    assert intents
    assert calls[0] <= 8 * 24, "quadratic repeated-element matching: %s" % calls[0]

def test_apply_uses_bounded_identity_resolutions():
    op, target, overlay = inputs()
    intents = op.plan(target, overlay, op="merge")
    with patch.object(op.identity, "key", wraps=op.identity.key) as spy:
        result = op.apply_intents(target, intents)
    assert len(result.message_type) == 24
    assert all(item.options.map_entry for item in result.message_type)
    assert spy.call_count <= 5 * 24, "quadratic repeated-merge identity lookup: %s" % spy.call_count

from dot_operator.types import MutationIntent

def test_selector_index_invalidated_after_identity_update():
    op, target, _ = inputs(1)
    original = descriptor_pb2.DescriptorProto(name="M000")
    changed = descriptor_pb2.DescriptorProto(name="Renamed")
    root_field = target.DESCRIPTOR.fields_by_name["message_type"]
    name_field = original.DESCRIPTOR.fields_by_name["name"]
    options_field = original.DESCRIPTOR.fields_by_name["options"]
    map_field = original.options.DESCRIPTOR.fields_by_name["map_entry"]
    intents = [
        MutationIntent(
            field=name_field, value="M000", new_value="Renamed",
            op="replace", parent_chain=[root_field, original, name_field],
        ),
        MutationIntent(
            field=map_field, value=False, new_value=True,
            op="replace", parent_chain=[root_field, changed, options_field, map_field],
        ),
    ]
    result = op.apply_intents(target, intents)
    assert len(result.message_type) == 1
    assert result.message_type[0].name == "Renamed"
    assert result.message_type[0].options.map_entry is True

