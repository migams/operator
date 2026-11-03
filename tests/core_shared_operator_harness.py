"""Public protobuf test harness for the independent operator package."""
from __future__ import annotations

from google.protobuf.message import Message

from dot_operator import OperatorContext, ProtobufOperator
from dot_operator.resource import (
    ResourceDeltaApplier,
    ResourceMutationContext,
    SpecIdentityResolver,
)


def clone(value: Message):
    copied = type(value)()
    copied.CopyFrom(value)
    return copied


def make_operator(resource, *, context: ResourceMutationContext | None = None):
    policy = context or ResourceMutationContext()
    identity = SpecIdentityResolver(policy.identity, identities=policy.identities)
    return ProtobufOperator(
        OperatorContext(
            resource=resource, identity=identity,
            immutable_paths=policy.immutable_paths,
        )
    )


def plan(current, desired, *, op="replace", context=None):
    return make_operator(current, context=context).plan(current, desired, op=op)


def replay(current, intents, *, context=None):
    target = clone(current)
    return make_operator(target, context=context).apply_intents(target, intents)


def apply_direct(current, desired, *, op="replace", context=None):
    target = clone(current)
    return make_operator(target, context=context).apply(target, op, desired)


def apply_resource_delta(current, desired, *, context=None):
    target = clone(current)
    return ResourceDeltaApplier().replace(
        target, value=desired, context=context or ResourceMutationContext()
    )
