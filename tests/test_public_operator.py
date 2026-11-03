"""Standalone operator contract; no import of private DOT packages."""
from types import SimpleNamespace

import pytest
from google.protobuf import descriptor_pb2, descriptor_pool, message_factory

from dot_operator import OperatorContext, ProtobufOperator, ResourceIdentityResolver


def _messages():
    spec = descriptor_pb2.FileDescriptorProto()
    spec.name = "dot_operator_oss_contract.proto"
    spec.package = "oss_contract"
    spec.syntax = "proto3"
    network = spec.message_type.add()
    network.name = "Network"
    for number, name in [(1, "name"), (2, "ipv4")]:
        field = network.field.add()
        field.number = number
        field.name = name
        field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
        field.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING

    host = spec.message_type.add()
    host.name = "Host"
    field = host.field.add()
    field.number = 1
    field.name = "networks"
    field.label = descriptor_pb2.FieldDescriptorProto.LABEL_REPEATED
    field.type = descriptor_pb2.FieldDescriptorProto.TYPE_MESSAGE
    field.type_name = ".oss_contract.Network"
    field = host.field.add()
    field.number = 2
    field.name = "hostname"
    field.label = descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
    field.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
    pool = descriptor_pool.DescriptorPool()
    pool.AddSerializedFile(spec.SerializeToString())
    return (
        message_factory.GetMessageClass(pool.FindMessageTypeByName("oss_contract.Host")),
        message_factory.GetMessageClass(pool.FindMessageTypeByName("oss_contract.Network")),
    )


def _operator(*, identity=None):
    resource = SimpleNamespace(identity={} if identity is None else {"network": identity})
    resolver = ResourceIdentityResolver(resource)
    return ProtobufOperator(OperatorContext(resource, resolver)), resolver


def test_unconfigured_identity_requires_no_private_core():
    _, Network = _messages()
    _, resolver = _operator()
    assert resolver.fields(Network()) == ()
    assert resolver.key(Network(name="local")) == ()


def test_unconfigured_networks_preserve_list_semantics():
    Host, _ = _messages()
    op, _ = _operator()
    target = Host()
    overlay = Host()
    overlay.networks.add(name="a", ipv4="127.0.0.1")
    overlay.networks.add(name="b", ipv4="10.0.0.2")
    result = op.apply(target, op="merge", overlay=overlay)
    assert [(n.name, n.ipv4) for n in result.networks] == [
        ("a", "127.0.0.1"),
        ("b", "10.0.0.2"),
    ]


def test_named_identity_merge_is_idempotent():
    Host, _ = _messages()
    op, _ = _operator(identity="name")
    target = Host()
    target.networks.add(name="local", ipv4="127.0.0.1")
    overlay = Host()
    overlay.networks.add(name="local", ipv4="127.0.0.1")
    overlay.networks.add(name="remote", ipv4="10.0.0.2")
    op.apply(target, op="merge", overlay=overlay)
    op.apply(target, op="merge", overlay=overlay)
    assert [(x.name, x.ipv4) for x in target.networks] == [
        ("local", "127.0.0.1"),
        ("remote", "10.0.0.2"),
    ]


def test_explicit_identity_rejects_duplicate_overlay():
    Host, _ = _messages()
    op, _ = _operator(identity="name")
    overlay = Host()
    overlay.networks.add(name="same", ipv4="127.0.0.1")
    overlay.networks.add(name="same", ipv4="10.0.0.2")
    with pytest.raises(ValueError, match="duplicate overlay message identity"):
        op.plan(Host(), overlay, op="merge")


def test_replayed_plan_matches_direct_apply():
    Host, _ = _messages()
    op, _ = _operator(identity="name")
    target = Host()
    overlay = Host(hostname="node")
    overlay.networks.add(name="public", ipv4="198.51.100.2")
    intents = op.plan(target, overlay, op="merge")
    replayed = op.apply_intents(Host(), intents)
    direct = op.apply(Host(), op="merge", overlay=overlay)
    assert replayed.SerializeToString(deterministic=True) == direct.SerializeToString(deterministic=True)


def test_equal_replacement_is_noop():
    Host, _ = _messages()
    op, _ = _operator()
    host = Host(hostname="same")
    assert op.plan(host, Host(hostname="same"), op="replace") == []
